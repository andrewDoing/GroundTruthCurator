#!/usr/bin/env python3
"""Validation script for schema v1 to v2 migration.

This script validates that the migration from schema v1 to v2 completed successfully
by checking that all ground truth documents have the expected v2 schema structure.

Validation Checks:
1. All documents have schemaVersion = 'v2'
2. All documents have 'manualTags' field (list)
3. All documents have 'computedTags' field (list)
4. No documents have the legacy 'tags' field
5. Computed tags are consistent with what the tag plugins would generate
6. No duplicate tags between manualTags and computedTags

Configuration:
    This script uses the same configuration file as the migration script.
    Copy migrate_v1_to_v2.sample.env to migrate_v1_to_v2.env and configure.

Usage:
    # Run validation:
    python scripts/validate_v2_migration.py

    # Validate specific dataset:
    python scripts/validate_v2_migration.py --dataset my-dataset

    # Verbose output (show each document):
    python scripts/validate_v2_migration.py --verbose

    # Show only documents with issues:
    python scripts/validate_v2_migration.py --issues-only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

# Add parent directory to path for imports (needed for plugin registry)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from app.plugins import get_default_registry
from app.domain.models import GroundTruthItem


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Well-known Cosmos DB emulator key
COSMOS_EMULATOR_KEY = (
    "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
)

# Schema version constants
SCHEMA_VERSION_V2 = "v2"


@dataclass
class DocumentIssue:
    """Represents an issue found in a document."""

    doc_id: str
    dataset: str
    issue_type: str
    message: str


@dataclass
class ValidationResult:
    """Results from validation run."""

    total_documents: int = 0
    valid_documents: int = 0
    documents_with_issues: int = 0
    issues: list[DocumentIssue] = field(default_factory=list)

    # Breakdown by issue type
    missing_schema_version: int = 0
    wrong_schema_version: int = 0
    missing_manual_tags: int = 0
    missing_computed_tags: int = 0
    has_legacy_tags: int = 0
    history_has_tags: int = 0
    computed_tags_mismatch: int = 0
    duplicate_tags: int = 0

    def add_issue(self, issue: DocumentIssue) -> None:
        """Add an issue and update counters."""
        self.issues.append(issue)

    @property
    def is_valid(self) -> bool:
        """Return True if no issues were found."""
        return len(self.issues) == 0


def load_env_file() -> None:
    """Load configuration from migrate_v1_to_v2.env file."""
    script_dir = Path(__file__).resolve().parent
    env_file = script_dir / "migrate_v1_to_v2.env"

    if not env_file.exists():
        logger.warning(f"Configuration file not found: {env_file}")
        logger.warning("Please create migrate_v1_to_v2.env based on migrate_v1_to_v2.sample.env")
        raise FileNotFoundError(f"Required configuration file not found: {env_file}")

    load_dotenv(env_file)
    logger.info(f"Loaded configuration from {env_file}")


def get_config() -> dict[str, Any]:
    """Load configuration from environment variables."""
    return {
        "endpoint": os.environ.get("GTC_COSMOS_ENDPOINT"),
        "db_name": os.environ.get("GTC_COSMOS_DB_NAME", "gt-curator"),
        "container_name": os.environ.get("GTC_COSMOS_CONTAINER_GT", "ground_truth"),
        "use_emulator": os.environ.get("GTC_USE_COSMOS_EMULATOR", "").lower() == "true",
    }


async def create_cosmos_client(config: dict[str, Any]) -> CosmosClient:
    """Create and return a Cosmos DB client."""
    endpoint = config["endpoint"]

    if not endpoint:
        raise ValueError("GTC_COSMOS_ENDPOINT environment variable is required")

    if config["use_emulator"]:
        logger.info("Using Cosmos DB emulator with well-known key")
        return CosmosClient(
            url=endpoint,
            credential=COSMOS_EMULATOR_KEY,
            connection_verify=False,
        )
    else:
        logger.info("Using DefaultAzureCredential for Cosmos DB authentication")
        credential = DefaultAzureCredential()
        return CosmosClient(
            url=endpoint,
            credential=credential,
        )


async def query_raw_documents(
    container: Any,
    dataset: str | None,
) -> list[dict[str, Any]]:
    """Query raw documents from Cosmos DB."""
    params: list[dict[str, Any]] = []
    where_clause = "WHERE c.docType = 'ground-truth-item'"

    if dataset:
        where_clause += " AND c.datasetName = @dataset"
        params.append({"name": "@dataset", "value": dataset})

    query = f"SELECT * FROM c {where_clause}"

    docs: list[dict[str, Any]] = []
    items = container.query_items(query=query, parameters=params)
    async for doc in items:
        docs.append(doc)
    return docs


def create_model_for_compute(doc: dict[str, Any]) -> GroundTruthItem:
    """Create a GroundTruthItem for computing expected tags."""
    temp_doc = dict(doc)

    # Ensure required fields exist for model validation
    if "manualTags" not in temp_doc:
        temp_doc["manualTags"] = []
    if "computedTags" not in temp_doc:
        temp_doc["computedTags"] = []
    if "history" not in temp_doc or temp_doc["history"] is None:
        temp_doc["history"] = []

    return GroundTruthItem.model_validate(temp_doc)


def validate_document(
    doc: dict[str, Any],
    registry: Any,
    verbose: bool = False,
) -> list[DocumentIssue]:
    """Validate a single document against v2 schema requirements.

    Returns a list of issues found (empty if valid).
    """
    issues: list[DocumentIssue] = []
    doc_id = doc.get("id", "unknown")
    dataset = doc.get("datasetName", "unknown")

    def add_issue(issue_type: str, message: str) -> None:
        issues.append(
            DocumentIssue(
                doc_id=doc_id,
                dataset=dataset,
                issue_type=issue_type,
                message=message,
            )
        )

    # Check 1: schemaVersion exists and is 'v2'
    schema_version = doc.get("schemaVersion")
    if schema_version is None:
        add_issue("missing_schema_version", "Document is missing 'schemaVersion' field")
    elif schema_version != SCHEMA_VERSION_V2:
        add_issue("wrong_schema_version", f"Expected schemaVersion='v2', got '{schema_version}'")

    # Check 2: manualTags field exists and is a list
    manual_tags = doc.get("manualTags")
    if manual_tags is None:
        add_issue("missing_manual_tags", "Document is missing 'manualTags' field")
    elif not isinstance(manual_tags, list):
        add_issue(
            "missing_manual_tags",
            f"'manualTags' should be a list, got {type(manual_tags).__name__}",
        )

    # Check 3: computedTags field exists and is a list
    computed_tags = doc.get("computedTags")
    if computed_tags is None:
        add_issue("missing_computed_tags", "Document is missing 'computedTags' field")
    elif not isinstance(computed_tags, list):
        add_issue(
            "missing_computed_tags",
            f"'computedTags' should be a list, got {type(computed_tags).__name__}",
        )

    # Check 4: No legacy 'tags' field
    if "tags" in doc:
        add_issue("has_legacy_tags", f"Document still has legacy 'tags' field: {doc['tags']}")

    # Check 5: Computed tags match what plugins would generate
    if isinstance(computed_tags, list):
        try:
            temp_item = create_model_for_compute(doc)
            expected_computed = set(registry.compute_all(temp_item))
            actual_computed = set(computed_tags)

            if expected_computed != actual_computed:
                missing = expected_computed - actual_computed
                extra = actual_computed - expected_computed
                details = []
                if missing:
                    details.append(f"missing: {sorted(missing)}")
                if extra:
                    details.append(f"extra: {sorted(extra)}")
                add_issue(
                    "computed_tags_mismatch",
                    f"Computed tags don't match expected. {', '.join(details)}",
                )
        except Exception as e:
            add_issue("computed_tags_mismatch", f"Error computing expected tags: {e}")

    # Check 6: No duplicate tags between manualTags and computedTags
    if isinstance(manual_tags, list) and isinstance(computed_tags, list):
        manual_set = set(manual_tags)
        computed_set = set(computed_tags)
        duplicates = manual_set & computed_set
        if duplicates:
            add_issue(
                "duplicate_tags",
                f"Tags appear in both manualTags and computedTags: {sorted(duplicates)}",
            )

    # Check 7: No 'tags' field in history items
    # In v2 schema, history items no longer have their own tags field
    history = doc.get("history")
    if history and isinstance(history, list):
        for idx, history_item in enumerate(history):
            if isinstance(history_item, dict) and "tags" in history_item:
                add_issue(
                    "history_has_tags",
                    f"History item [{idx}] has legacy 'tags' field: {history_item['tags']}",
                )

    return issues


async def validate_migration(
    dataset: str | None = None,
    verbose: bool = False,
    issues_only: bool = False,
) -> ValidationResult:
    """Validate that all documents have been properly migrated to v2 schema.

    Args:
        dataset: If provided, only validate documents in this dataset
        verbose: If True, log each document being processed
        issues_only: If True, only show documents with issues

    Returns:
        ValidationResult with statistics and issues found
    """
    config = get_config()
    registry = get_default_registry()

    logger.info(f"Tag plugin registry has {len(registry)} plugins registered")
    logger.info(f"Cosmos endpoint: {config['endpoint']}")
    logger.info(f"Database: {config['db_name']}, Container: {config['container_name']}")
    if dataset:
        logger.info(f"Filtering to dataset: {dataset}")

    result = ValidationResult()
    docs_with_issues: set[str] = set()

    client = await create_cosmos_client(config)

    try:
        database = client.get_database_client(config["db_name"])
        container = database.get_container_client(config["container_name"])

        # Query all documents
        raw_docs = await query_raw_documents(container, dataset)
        result.total_documents = len(raw_docs)
        logger.info(f"Found {len(raw_docs)} ground truth documents to validate")

        for doc in raw_docs:
            doc_id = doc.get("id", "unknown")

            # Validate document
            issues = validate_document(doc, registry, verbose)

            if issues:
                docs_with_issues.add(doc_id)
                for issue in issues:
                    result.add_issue(issue)

                    # Update breakdown counters
                    if issue.issue_type == "missing_schema_version":
                        result.missing_schema_version += 1
                    elif issue.issue_type == "wrong_schema_version":
                        result.wrong_schema_version += 1
                    elif issue.issue_type == "missing_manual_tags":
                        result.missing_manual_tags += 1
                    elif issue.issue_type == "missing_computed_tags":
                        result.missing_computed_tags += 1
                    elif issue.issue_type == "has_legacy_tags":
                        result.has_legacy_tags += 1
                    elif issue.issue_type == "history_has_tags":
                        result.history_has_tags += 1
                    elif issue.issue_type == "computed_tags_mismatch":
                        result.computed_tags_mismatch += 1
                    elif issue.issue_type == "duplicate_tags":
                        result.duplicate_tags += 1

                if verbose or issues_only:
                    logger.warning(f"Document {doc_id} has {len(issues)} issue(s):")
                    for issue in issues:
                        logger.warning(f"  - [{issue.issue_type}] {issue.message}")
            else:
                result.valid_documents += 1
                if verbose and not issues_only:
                    logger.info(f"Document {doc_id}: OK")

        result.documents_with_issues = len(docs_with_issues)

    finally:
        await client.close()

    return result


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate that ground truth documents have been properly migrated to v2 schema"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Only validate documents in this dataset",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (show each document)",
    )
    parser.add_argument(
        "--issues-only",
        action="store_true",
        help="Only show documents with issues",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment configuration
    try:
        load_env_file()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info("Starting migration validation...")
    start_time = datetime.now(timezone.utc)

    result = await validate_migration(
        dataset=args.dataset,
        verbose=args.verbose,
        issues_only=args.issues_only,
    )

    elapsed = datetime.now(timezone.utc) - start_time

    logger.info("=" * 70)
    logger.info("Validation Summary:")
    logger.info(f"  Total documents:           {result.total_documents}")
    logger.info(f"  Valid documents:           {result.valid_documents}")
    logger.info(f"  Documents with issues:     {result.documents_with_issues}")
    logger.info(f"  Total issues found:        {len(result.issues)}")
    logger.info("")

    if result.issues:
        logger.info("Issue Breakdown:")
        if result.missing_schema_version:
            logger.info(f"  Missing schemaVersion:     {result.missing_schema_version}")
        if result.wrong_schema_version:
            logger.info(f"  Wrong schemaVersion:       {result.wrong_schema_version}")
        if result.missing_manual_tags:
            logger.info(f"  Missing manualTags:        {result.missing_manual_tags}")
        if result.missing_computed_tags:
            logger.info(f"  Missing computedTags:      {result.missing_computed_tags}")
        if result.has_legacy_tags:
            logger.info(f"  Has legacy 'tags' field:   {result.has_legacy_tags}")
        if result.history_has_tags:
            logger.info(f"  History has 'tags' field:  {result.history_has_tags}")
        if result.computed_tags_mismatch:
            logger.info(f"  Computed tags mismatch:    {result.computed_tags_mismatch}")
        if result.duplicate_tags:
            logger.info(f"  Duplicate tags:            {result.duplicate_tags}")
        logger.info("")

    logger.info(f"  Elapsed time:              {elapsed}")
    logger.info("=" * 70)

    if result.is_valid:
        logger.info("✅ All documents passed validation!")
        sys.exit(0)
    else:
        logger.error("❌ Validation failed. Some documents have issues.")
        logger.info("Run with --verbose or --issues-only to see details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
