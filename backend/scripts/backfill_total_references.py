#!/usr/bin/env python3
"""
Backfill script to update existing Cosmos DB documents with totalReferences field.

This script:
1. Queries for documents missing the totalReferences field
2. Calculates totalReferences for each document
3. Updates documents in batches to avoid memory issues
4. Provides progress reporting and error handling
5. Can be run safely multiple times (idempotent)

USAGE (Local Development):
    python scripts/backfill_total_references.py [--batch-size 100] [--dry-run]

USAGE (Azure Container App):
    # Connect to the running container app instance
    az containerapp exec --name <container-app-name> --resource-group <resource-group> --command "/bin/bash"

    # Inside the container, run:
    cd /app
    python scripts/backfill_total_references.py --batch-size 50

    # For dry-run validation first:
    python scripts/backfill_total_references.py --dry-run

    # Monitor logs:
    az containerapp logs show --name <container-app-name> --resource-group <resource-group> --follow

AZURE CONTAINER APP CONSIDERATIONS:
    - Use smaller batch sizes (50-100) to avoid timeouts
    - Monitor memory usage during execution
    - Ensure the container has sufficient CPU/memory allocation
    - Set appropriate environment variables for Cosmos DB connection
    - Consider running during off-peak hours to minimize impact
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from azure.cosmos.exceptions import CosmosHttpResponseError

# Add the backend directory to Python path so we can import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.container import container
from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo


logger = logging.getLogger(__name__)


def compute_total_references_from_doc(doc: Dict[str, Any]) -> int:
    """Calculate total reference count from raw document data.

    Args:
        doc: Raw document from Cosmos DB

    Returns:
        Total reference count
    """
    # Count refs in all history turns
    history = doc.get("history", []) or []
    history_refs = 0

    for turn in history:
        if isinstance(turn, dict):
            refs = turn.get("refs", []) or []
            history_refs += len(refs)

    # If no turn refs, return item-level refs count
    if history_refs == 0:
        refs = doc.get("refs", []) or []
        return len(refs)

    return history_refs


async def get_documents_missing_total_references(batch_size: int = 100) -> list[Dict[str, Any]]:
    """Query for documents that don't have totalReferences field.

    Args:
        batch_size: Maximum number of documents to return

    Returns:
        List of documents missing totalReferences field
    """
    # Initialize the Cosmos repository if not already done
    if container.repo is None:
        container.init_cosmos_repo()

    repo = container.repo
    if isinstance(repo, CosmosGroundTruthRepo):
        await repo._ensure_initialized()

        # Query for documents without totalReferences field
        query = """
            SELECT * FROM c 
            WHERE c.docType = 'ground-truth-item' 
            AND NOT IS_DEFINED(c.totalReferences)
        """

        container_client = repo._gt_container
        if not container_client:
            raise ValueError("Cosmos container not initialized")
    else:
        raise ValueError("This script only works with CosmosGroundTruthRepo")
    query_iterator = container_client.query_items(
        query=query, enable_scan_in_query=True, max_item_count=batch_size
    )

    documents = []
    try:
        async for item in query_iterator:
            documents.append(item)
            if len(documents) >= batch_size:
                break
    except Exception as e:
        logger.error(f"Error querying documents: {e}")
        raise

    return documents


async def update_document_with_total_references(
    doc: Dict[str, Any], dry_run: bool = False, max_retries: int = 3
) -> bool:
    """Update a single document with totalReferences field.

    Args:
        doc: Document to update
        dry_run: If True, don't actually update the document

    Returns:
        True if update was successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            # Calculate totalReferences
            total_refs = compute_total_references_from_doc(doc)

            if dry_run:
                logger.info(
                    f"DRY RUN: Would update document {doc.get('id')} with totalReferences={total_refs}"
                )
                return True

            # Add totalReferences to document
            doc["totalReferences"] = total_refs
            doc["updatedAt"] = datetime.now(timezone.utc).isoformat()

            # Update in Cosmos DB
            repo = container.repo
            if isinstance(repo, CosmosGroundTruthRepo):
                container_client = repo._gt_container
                if not container_client:
                    raise ValueError("Cosmos container not initialized")
            else:
                raise ValueError("This script only works with CosmosGroundTruthRepo")

            # Use replace_item to update the document
            await container_client.replace_item(item=doc["id"], body=doc)

            logger.info(f"Updated document {doc.get('id')} with totalReferences={total_refs}")
            return True

        except CosmosHttpResponseError as e:
            if e.status_code == 429:  # Rate limited
                wait_time = 2**attempt
                logger.warning(f"Rate limited, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
            elif e.status_code == 412:  # Precondition failed (etag mismatch)
                logger.warning(f"Document {doc['id']} was updated by another process")
                return False
            else:
                raise
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Final attempt failed for {doc['id']}: {e}")
                return False
            logger.warning(f"Attempt {attempt + 1} failed, retrying: {e}")

    return False


async def update_documents_batch(
    documents: list[Dict[str, Any]], batch_size: int = 10, max_ru_per_second: int = 400
) -> Dict[str, int]:
    """Optimized batch processing with rate limiting."""

    stats = {"processed": 0, "updated": 0, "errors": 0, "skipped": 0}

    # Process in smaller batches to control RU consumption
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]

        # Execute batch operations concurrently with semaphore
        semaphore = asyncio.Semaphore(5)  # Limit concurrent operations

        async def process_document(doc):
            async with semaphore:
                return await update_document_with_total_references(doc)

        # Process batch concurrently
        batch_tasks = [process_document(doc) for doc in batch]
        results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Update statistics
        for result in results:
            if isinstance(result, Exception):
                stats["errors"] += 1
            elif result:
                stats["updated"] += 1
            stats["processed"] += 1

        # Rate limiting: pause between batches
        await asyncio.sleep(0.1)  # 100ms pause

        # Log progress
        logger.info(f"Processed batch {i // batch_size + 1}, Progress: {stats}")

    return stats


async def backfill_total_references_batch(
    batch_size: int = 100, dry_run: bool = False
) -> Dict[str, int]:
    """Process a batch of documents and update them with totalReferences.

    Args:
        batch_size: Number of documents to process in this batch
        dry_run: If True, don't actually update documents

    Returns:
        Dictionary with processing statistics
    """
    stats = {"processed": 0, "updated": 0, "errors": 0, "skipped": 0}

    try:
        # Get documents missing totalReferences
        documents = await get_documents_missing_total_references(batch_size)

        if not documents:
            logger.info("No documents found missing totalReferences field")
            return stats

        logger.info(f"Found {len(documents)} documents to update")

        batch_stats = await update_documents_batch(documents, batch_size=10)

        # Update the main stats with batch results
        for key in ["processed", "updated", "errors", "skipped"]:
            stats[key] = batch_stats[key]

        return stats

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        stats["errors"] += 1
        return stats


async def run_full_migration(
    batch_size: int = 100, max_batches: int | None = None, dry_run: bool = False
) -> None:
    """Run the complete migration process.

    Args:
        batch_size: Number of documents to process per batch
        max_batches: Maximum number of batches to process (None = unlimited)
        dry_run: If True, don't actually update documents
    """
    logger.info("Starting totalReferences backfill migration")
    logger.info(f"Batch size: {batch_size}, Max batches: {max_batches}, Dry run: {dry_run}")

    total_stats = {"processed": 0, "updated": 0, "errors": 0, "skipped": 0, "batches": 0}

    batch_count = 0

    while True:
        batch_count += 1

        if max_batches and batch_count > max_batches:
            logger.info(f"Reached maximum batch limit of {max_batches}")
            break

        logger.info(f"Processing batch {batch_count}...")

        # Process batch
        batch_stats = await backfill_total_references_batch(batch_size, dry_run)

        # Update totals
        for key in ["processed", "updated", "errors", "skipped"]:
            total_stats[key] += batch_stats[key]
        total_stats["batches"] = batch_count

        # Log batch results
        logger.info(f"Batch {batch_count} complete: {batch_stats}")

        # If no documents were processed, we're done
        if batch_stats["processed"] == 0:
            logger.info("No more documents to process")
            break

        # In dry-run mode, stop after first batch to avoid infinite loop
        # (since we're not actually updating documents, the query will keep finding the same ones)
        if dry_run:
            logger.info("Dry-run mode: stopping after first batch to prevent infinite loop")
            break

    # Final summary
    logger.info("Migration complete!")
    logger.info(f"Total statistics: {total_stats}")


async def main() -> None:
    """Main function to handle command line arguments and execute migration."""
    parser = argparse.ArgumentParser(
        description="Backfill totalReferences field in Cosmos DB documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to process per batch (default: 100)",
    )

    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum number of batches to process (default: unlimited)",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without actually updating documents"
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        await run_full_migration(
            batch_size=args.batch_size, max_batches=args.max_batches, dry_run=args.dry_run
        )
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
