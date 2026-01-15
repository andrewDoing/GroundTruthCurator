#!/usr/bin/env python3
"""
Cosmos DB Greetings Answer Update Script
=========================================

This script updates the answer field from NO_ANSWER to GREETING for all items
in the ground_truth container that have a tag set to "intent:greetings".

FEATURES:
- Connects to Azure Cosmos DB using DefaultAzureCredential
- Supports local Cosmos DB emulator for dev environment
- Uses Cosmos DB patch operations for Azure (cost-efficient, lower RU consumption)
- Uses upsert operations for emulator (patch not supported on emulator)
- Concurrent batch processing for efficient bulk updates
- Dry-run mode to preview changes without modifying data
- Automatic retry with exponential backoff for 429 throttling
- Progress reporting and statistics

USAGE:
1. Configure environment variables in '.env' file
2. Run: python update_greetings_answer.py

CONFIGURATION:
Environment variables (set in .env):
- COSMOS_ACCOUNT_URI: Cosmos DB endpoint URL
- COSMOS_DATABASE: Database name
- COSMOS_CONTAINER: Container name (default: ground_truth)
- COSMOS_EMULATOR_KEY: Required if using local emulator (localhost/127.0.0.1)
- DRY_RUN: Set to "true" to preview without modifying (default: false)
- CONCURRENCY: Number of parallel updates (default: 32)
- BATCH_SIZE: Items per progress update (default: 100)

EXAMPLES:
# Preview changes (dry-run)
DRY_RUN=true python update_greetings_answer.py

# Execute actual update
DRY_RUN=false python update_greetings_answer.py

COST OPTIMIZATION:
- Uses patch operations for Azure instead of upsert (typically 50% less RUs)
- Automatically falls back to upsert for emulator (patch not supported)
- Query selects only required fields (id, datasetName, bucket, answer)
- Concurrent processing maximizes throughput without extra cost
"""

import os
import time
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from azure.identity import DefaultAzureCredential
from concurrent.futures import ThreadPoolExecutor, as_completed


# ------------- Configuration -------------


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:  # catches None and empty string
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


DOTENV_PATH = Path(".env")
load_dotenv(dotenv_path=DOTENV_PATH)

COSMOS_ACCOUNT_URI = require_env("COSMOS_ACCOUNT_URI")
COSMOS_DATABASE = require_env("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "ground_truth")

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# Retry/backoff settings
MAX_RETRY_ATTEMPTS = 10
RETRY_BACKOFF_BASE = 0.5  # seconds

# Concurrency settings
CONCURRENCY = int(os.getenv("CONCURRENCY", "32"))  # parallel updates
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))  # items per progress update


# ------------- Helpers -------------


def is_cosmos_emulator_in_use() -> bool:
    """Detect if Cosmos DB emulator is in use based on endpoint URL."""
    return "localhost" in COSMOS_ACCOUNT_URI or "127.0.0.1" in COSMOS_ACCOUNT_URI


def log(msg: str):
    """Log message with prefix."""
    print(f"[update-greetings] {msg}")


def extract_partition_key(item: dict[str, Any]) -> list[Any]:
    """
    Extract hierarchical partition key values from item.
    Assumes HPK structure: [datasetName, bucket]
    """
    dataset_name = item.get("datasetName")
    bucket = item.get("bucket")
    return [dataset_name, bucket]


def patch_item_with_retry(container, item_id: str, partition_key: list[Any]) -> bool:
    """
    Patch a single item's answer field with retry logic for 429 throttling.
    Uses patch operation for cost efficiency (lower RU consumption than upsert).
    Returns True if successful.
    """
    attempts = 0
    while True:
        try:
            # Patch operation - only updates the 'answer' field
            container.patch_item(
                item=item_id,
                partition_key=partition_key,
                patch_operations=[{"op": "replace", "path": "/answer", "value": "GREETING"}],
            )
            return True
        except CosmosHttpResponseError as e:
            # 429 (throttled) -> backoff, then retry
            if getattr(e, "status_code", None) == 429 and attempts < MAX_RETRY_ATTEMPTS:
                attempts += 1
                delay = min(RETRY_BACKOFF_BASE * (2**attempts), 30.0)
                log(
                    f"Throttled (429) on id={item_id}. "
                    f"Backing off {delay:.1f}s (attempt {attempts}/{MAX_RETRY_ATTEMPTS})"
                )
                time.sleep(delay)
                continue
            else:
                # Bubble up any non-retryable errors
                log(f"Failed to patch item id={item_id}: {e}")
                raise


def upsert_item_with_retry(container, item: dict[str, Any]) -> bool:
    """
    Upsert a single item with retry logic for 429 throttling.
    Used for emulator since patch operations are not supported.
    Returns True if successful.
    """
    attempts = 0
    while True:
        try:
            container.upsert_item(item)
            return True
        except CosmosHttpResponseError as e:
            # 429 (throttled) -> backoff, then retry
            if getattr(e, "status_code", None) == 429 and attempts < MAX_RETRY_ATTEMPTS:
                attempts += 1
                delay = min(RETRY_BACKOFF_BASE * (2**attempts), 30.0)
                log(
                    f"Throttled (429) on id={item.get('id')}. "
                    f"Backing off {delay:.1f}s (attempt {attempts}/{MAX_RETRY_ATTEMPTS})"
                )
                time.sleep(delay)
                continue
            else:
                # Bubble up any non-retryable errors
                log(f"Failed to upsert item id={item.get('id')}: {e}")
                raise


def patch_batch_concurrent(
    container,
    items: list[dict[str, Any]],
    concurrency: int,
    use_emulator: bool = False,
) -> int:
    """
    Update a batch of items concurrently using ThreadPoolExecutor.
    Uses patch operations for Azure, upsert for emulator.
    Returns count of successfully updated items.
    """
    if not items:
        return 0

    operation = "Upserting" if use_emulator else "Patching"
    log(f"{operation} {len(items)} items with concurrency={concurrency}")
    items_updated = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        if use_emulator:
            # Emulator: use upsert (patch not supported)
            # Prepare items with updated answer field
            for item in items:
                item["answer"] = "GREETING"

            future_to_item = {
                executor.submit(upsert_item_with_retry, container, item): item for item in items
            }
        else:
            # Azure: use patch for cost efficiency
            future_to_item = {
                executor.submit(
                    patch_item_with_retry, container, item["id"], extract_partition_key(item)
                ): item
                for item in items
            }

        # Collect results as they complete
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                if future.result():
                    items_updated += 1
                    if items_updated % BATCH_SIZE == 0:
                        log(f"Progress: {items_updated}/{len(items)} items updated")
            except Exception as e:
                log(f"Failed to update item id={item.get('id')}: {e}")
                continue

    return items_updated


def update_greetings_answer(
    client: CosmosClient,
    database_name: str,
    container_name: str,
    dry_run: bool = False,
    use_emulator: bool = False,
) -> tuple[int, int]:
    """
    Update answer field from NO_ANSWER to GREETING for items with intent:greetings tag.
    Uses patch operations for Azure or upsert for emulator.

    Returns:
        Tuple of (items_matched, items_updated)
    """
    operation = "upsert" if use_emulator else "patch"
    log(
        f"Connecting to {COSMOS_ACCOUNT_URI}:{database_name}/{container_name} (using {operation} operations)"
    )

    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    # Query for items with intent:greetings tag and answer = NO_ANSWER
    # For emulator: select all fields since we need full document for upsert
    # For Azure: select only necessary fields to minimize RU consumption
    if use_emulator:
        query = """
            SELECT * FROM c 
            WHERE ARRAY_CONTAINS(c.manualTags, "intent:greetings") 
            AND c.answer = "NO_ANSWER"
        """
    else:
        query = """
            SELECT c.id, c.datasetName, c.bucket, c.answer FROM c 
            WHERE ARRAY_CONTAINS(c.manualTags, "intent:greetings") 
            AND c.answer = "NO_ANSWER"
        """

    log("Querying for items with 'intent:greetings' tag and answer='NO_ANSWER'...")

    try:
        items = list(
            container.query_items(
                query=query,
                enable_cross_partition_query=True,
            )
        )
    except CosmosHttpResponseError as e:
        log(f"Query error: {e}")
        raise

    items_matched = len(items)
    log(f"Found {items_matched} items matching criteria")

    if items_matched == 0:
        return 0, 0

    if dry_run:
        operation = "upserted" if use_emulator else "patched"
        log(f"[DRY RUN] Items that would be {operation}:")
        for item in items:
            log(f"  - id: {item.get('id')}, answer: {item.get('answer')} -> GREETING")
        log(f"[DRY RUN] Total items that would be {operation}: {items_matched}")
        return items_matched, 0

    # Execute concurrent batch update (patch for Azure, upsert for emulator)
    items_updated = patch_batch_concurrent(container, items, CONCURRENCY, use_emulator)

    operation = "upserted" if use_emulator else "patched"
    log(f"Update complete: {items_updated}/{items_matched} items {operation} successfully")
    return items_matched, items_updated


# ------------- Main -------------


def main():
    """Main entry point."""
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    use_emulator = is_cosmos_emulator_in_use()
    log(f"Starting update script in {mode} mode")

    # Build credential
    aad_credential = DefaultAzureCredential()

    # Create Cosmos client
    if use_emulator:
        log("Using Cosmos Emulator (will use upsert operations - patch not supported)")
        emulator_key = require_env("COSMOS_EMULATOR_KEY")
        client = CosmosClient(COSMOS_ACCOUNT_URI, credential=emulator_key, logging_enable=True)
    else:
        log("Using Azure Cosmos DB with DefaultAzureCredential (will use patch operations)")
        client = CosmosClient(COSMOS_ACCOUNT_URI, credential=aad_credential, logging_enable=True)

    # Execute update
    items_matched, items_updated = update_greetings_answer(
        client=client,
        database_name=COSMOS_DATABASE,
        container_name=COSMOS_CONTAINER,
        dry_run=DRY_RUN,
        use_emulator=use_emulator,
    )

    # Summary
    operation = "upserted" if use_emulator else "patched"
    log("=" * 60)
    log("Summary:")
    log(f"  Mode: {mode}")
    log(f"  Environment: {'Emulator' if use_emulator else 'Azure'}")
    log(f"  Operation: {'upsert' if use_emulator else 'patch'}")
    log(f"  Items matched: {items_matched}")
    if DRY_RUN:
        log(f"  Items that would be {operation}: {items_matched}")
    else:
        log(f"  Items {operation}: {items_updated}")
        if items_matched > 0:
            success_rate = (items_updated / items_matched) * 100
            log(f"  Success rate: {success_rate:.1f}%")
    log("=" * 60)


if __name__ == "__main__":
    main()
