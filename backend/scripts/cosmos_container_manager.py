#!/usr/bin/env python3
"""
Unified Cosmos DB container initialization script.

This script creates Cosmos DB containers with support for:
- Azure-deployed Cosmos DB (using Azure AD authentication)
- Local Cosmos Emulator (using key-based authentication)
- Hierarchical partition keys (MultiHash)
- Simple partition keys (Hash)
- Custom indexing policies

Usage Examples:

    # Azure AD authentication (production):
    python scripts/cosmos_container_manager.py \\
        --endpoint https://myaccount.documents.azure.com:443/ \\
        --use-aad \\
        --db my-database \\
        --gt-container --assignments-container --tags-container --tag-definitions-container

    # Key-based authentication (emulator):
    python scripts/cosmos_container_manager.py \\
        --endpoint https://localhost:8081 \\
        --key "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==" \\
        --no-verify \\
        --db my-database \\
        --gt-container --assignments-container --tags-container --tag-definitions-container

    # Single container with custom partition key:
    python scripts/cosmos_container_manager.py \\
        --endpoint https://localhost:8081 \\
        --key "<key>" \\
        --no-verify \\
        --db my-database \\
        --container my-container \\
        --partition-key /userId

    # Hierarchical partition key:
    python scripts/cosmos_container_manager.py \\
        --endpoint https://localhost:8081 \\
        --key "<key>" \\
        --no-verify \\
        --db my-database \\
        --container my-container \\
        --partition-paths /tenantId /userId /sessionId

    # Bulk initialization from JSON config:
    python scripts/cosmos_container_manager.py \\
        --endpoint https://myaccount.documents.azure.com:443/ \\
        --use-aad \\
        --db my-database \\
        --containers containers.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from azure.identity import DefaultAzureCredential


SCRIPT_DIR = Path(__file__).parent
DEFAULT_INDEXING_POLICY_FILE = SCRIPT_DIR / "indexing-policy.json"


# =============================================================================
# Authentication Configuration
# =============================================================================


def create_cosmos_client(
    endpoint: str,
    key: str | None = None,
    use_aad: bool = False,
    connection_verify: bool = True,
) -> CosmosClient:
    """
    Create a CosmosClient with the appropriate authentication.

    Args:
        endpoint: Cosmos DB endpoint URL
        key: Cosmos DB key (for key-based auth)
        use_aad: Whether to use Azure AD authentication
        connection_verify: Whether to verify SSL connection (False for emulator)

    Returns:
        CosmosClient instance

    Raises:
        ValueError: If neither key nor use_aad is provided
    """
    if use_aad:
        credential = DefaultAzureCredential()
        return CosmosClient(endpoint, credential=credential, connection_verify=connection_verify)  # type: ignore[arg-type]
    elif key:
        return CosmosClient(endpoint, credential=key, connection_verify=connection_verify)
    else:
        raise ValueError("Either --key or --use-aad must be provided for authentication")


# =============================================================================
# Partition Key Configuration
# =============================================================================


def build_partition_key(
    paths: list[str],
    kind: str = "Hash",
) -> PartitionKey:
    """
    Build a PartitionKey object for the Data SDK.

    Args:
        paths: List of partition key paths (e.g., ["/pk"] or ["/tenantId", "/userId"])
        kind: Partition key kind - "Hash" for simple, "MultiHash" for hierarchical

    Returns:
        PartitionKey object configured for the given paths and kind

    Raises:
        ValueError: If kind is invalid or paths don't match kind requirements
    """
    if kind not in ("Hash", "MultiHash"):
        raise ValueError(f"Invalid partition key kind: {kind}. Must be 'Hash' or 'MultiHash'")

    if len(paths) > 1 and kind != "MultiHash":
        raise ValueError("Multiple partition key paths require kind='MultiHash'")

    if len(paths) == 1 and kind == "Hash":
        # Simple partition key
        return PartitionKey(path=paths[0])
    else:
        # Hierarchical partition key (MultiHash)
        return PartitionKey(path=paths, kind="MultiHash")


# =============================================================================
# Container Specification
# =============================================================================


@dataclass
class ContainerSpec:
    """Specification for a Cosmos DB container."""

    name: str
    partition_key_paths: list[str]
    partition_key_kind: str = "Hash"
    indexing_policy_file: Path | None = None
    indexing_policy_dict: dict[str, Any] | None = None
    max_throughput: int | None = None

    def __post_init__(self) -> None:
        """Validate the container specification."""
        if not self.name:
            raise ValueError("Container name is required")
        if not self.partition_key_paths:
            raise ValueError("At least one partition key path is required")
        if self.indexing_policy_file and self.indexing_policy_dict:
            raise ValueError(
                "Provide either indexing_policy_file or indexing_policy_dict, not both"
            )

    def get_partition_key(self) -> PartitionKey:
        """Build the PartitionKey object for this container."""
        return build_partition_key(self.partition_key_paths, self.partition_key_kind)

    def get_indexing_policy(self) -> dict[str, Any] | None:
        """Load and return the indexing policy."""
        if self.indexing_policy_dict:
            return self.indexing_policy_dict
        if self.indexing_policy_file:
            with open(self.indexing_policy_file) as f:
                return json.load(f)
        return None


# =============================================================================
# Container Creation Logic
# =============================================================================


async def create_container(
    client: CosmosClient,
    database_name: str,
    spec: ContainerSpec,
) -> dict[str, Any]:
    """
    Create a single container using the Data SDK.

    Args:
        client: CosmosClient instance
        database_name: Name of the database
        spec: Container specification

    Returns:
        dict with container_name and created status
    """
    db = client.get_database_client(database_name)
    container = db.get_container_client(spec.name)

    try:
        await container.read()
        return {"container_name": spec.name, "created": False, "status": "already exists"}
    except CosmosHttpResponseError:
        # Container doesn't exist, create it
        partition_key = spec.get_partition_key()
        indexing_policy = spec.get_indexing_policy()

        create_kwargs: dict[str, Any] = {
            "id": spec.name,
            "partition_key": partition_key,
        }
        if indexing_policy:
            create_kwargs["indexing_policy"] = indexing_policy
        if spec.max_throughput is not None:
            create_kwargs["max_throughput"] = spec.max_throughput

        await db.create_container(**create_kwargs)
        return {"container_name": spec.name, "created": True, "status": "created"}


async def initialize_containers(
    client: CosmosClient,
    database_name: str,
    container_specs: list[ContainerSpec],
) -> dict[str, dict[str, Any]]:
    """
    Initialize multiple containers in a database.

    Creates the database if it doesn't exist, then creates each container.

    Args:
        client: CosmosClient instance
        database_name: Name of the database
        container_specs: List of container specifications

    Returns:
        dict mapping container names to creation results
    """
    # Create database if not exists
    db = client.get_database_client(database_name)
    try:
        await db.read()
        print(f"  Database '{database_name}': already exists")
    except CosmosHttpResponseError:
        await client.create_database(database_name)
        print(f"  Database '{database_name}': created")

    # Create containers
    results: dict[str, dict[str, Any]] = {}
    for spec in container_specs:
        result = await create_container(client, database_name, spec)
        results[spec.name] = result
        print(f"  Container '{spec.name}': {result['status']}")

    return results


# =============================================================================
# Default Container Configurations
# =============================================================================


def get_default_container_specs(
    gt_container: str | None = None,
    assignments_container: str | None = None,
    tags_container: str | None = None,
    tag_definitions_container: str | None = None,
    indexing_policy_file: Path | None = None,
    max_throughput: int | None = None,
) -> list[ContainerSpec]:
    """
    Get default container specifications for Ground Truth Curator.

    Args:
        gt_container: Name for ground truth container (if provided)
        assignments_container: Name for assignments container (if provided)
        tags_container: Name for tags container (if provided)
        tag_definitions_container: Name for tag definitions container (if provided)
        indexing_policy_file: Path to indexing policy file for gt container

    Returns:
        List of ContainerSpec objects for the requested containers
    """
    specs: list[ContainerSpec] = []

    if gt_container:
        specs.append(
            ContainerSpec(
                name=gt_container,
                partition_key_paths=["/datasetName", "/bucket"],
                partition_key_kind="MultiHash",
                indexing_policy_file=indexing_policy_file or DEFAULT_INDEXING_POLICY_FILE,
                max_throughput=max_throughput,
            )
        )

    if assignments_container:
        specs.append(
            ContainerSpec(
                name=assignments_container,
                partition_key_paths=["/pk"],
                partition_key_kind="Hash",
            )
        )

    if tags_container:
        specs.append(
            ContainerSpec(
                name=tags_container,
                partition_key_paths=["/pk"],
                partition_key_kind="Hash",
            )
        )

    if tag_definitions_container:
        specs.append(
            ContainerSpec(
                name=tag_definitions_container,
                partition_key_paths=["/tag_key"],
                partition_key_kind="Hash",
            )
        )

    return specs


def load_container_specs_from_file(file_path: Path) -> list[ContainerSpec]:
    """
    Load container specifications from a JSON file.

    Expected JSON format:
    [
        {
            "name": "container-name",
            "partition_key_paths": ["/path1", "/path2"],
            "partition_key_kind": "MultiHash",
            "indexing_policy_file": "path/to/policy.json"
        },
        ...
    ]

    Args:
        file_path: Path to the JSON configuration file

    Returns:
        List of ContainerSpec objects
    """
    with open(file_path) as f:
        configs = json.load(f)

    specs: list[ContainerSpec] = []
    for config in configs:
        indexing_file = config.get("indexing_policy_file")
        specs.append(
            ContainerSpec(
                name=config["name"],
                partition_key_paths=config["partition_key_paths"],
                partition_key_kind=config.get("partition_key_kind", "Hash"),
                indexing_policy_file=Path(indexing_file) if indexing_file else None,
                indexing_policy_dict=config.get("indexing_policy"),
                max_throughput=config.get("max_throughput"),
            )
        )

    return specs


# =============================================================================
# CLI Validation
# =============================================================================


def validate_args(args: argparse.Namespace) -> None:
    """
    Validate CLI arguments and provide user-friendly error messages.

    Args:
        args: Parsed command-line arguments

    Raises:
        SystemExit: If validation fails
    """
    errors: list[str] = []

    # Validate authentication
    if not args.key and not args.use_aad:
        errors.append("Authentication required: provide --key or --use-aad")

    if args.key and args.use_aad:
        errors.append("Conflicting auth: provide either --key or --use-aad, not both")

    # Validate container configuration
    has_default_containers = (
        args.gt_container
        or args.assignments_container
        or args.tags_container
        or args.tag_definitions_container
    )
    has_custom_container = args.container
    has_containers_file = args.containers

    container_options = sum(
        [bool(has_default_containers), bool(has_custom_container), bool(has_containers_file)]
    )
    if container_options == 0:
        errors.append("No containers specified: use --gt-container, --container, or --containers")
    if container_options > 1:
        errors.append(
            "Conflicting container options: use only one of --gt-container/--assignments-container/--tags-container/--tag-definitions-container, --container, or --containers"
        )

    # Validate custom container options
    if has_custom_container:
        if not args.partition_key and not args.partition_paths:
            errors.append("Custom container requires --partition-key or --partition-paths")
        if args.partition_key and args.partition_paths:
            errors.append(
                "Conflicting options: provide either --partition-key or --partition-paths, not both"
            )

    # Validate file paths
    if args.containers and not Path(args.containers).exists():
        errors.append(f"Containers file not found: {args.containers}")

    if args.indexing_policy and not Path(args.indexing_policy).exists():
        errors.append(f"Indexing policy file not found: {args.indexing_policy}")

    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# CLI Entry Point
# =============================================================================


async def main_async(args: argparse.Namespace) -> None:
    """Async entry point for CLI usage."""
    print(f"Initializing Cosmos DB containers in database '{args.db}'...")
    print(f"Endpoint: {args.endpoint}")
    print(f"Auth: {'Azure AD' if args.use_aad else 'Key-based'}")

    # Build container specs
    if args.containers:
        container_specs = load_container_specs_from_file(Path(args.containers))
    elif args.container:
        # Custom single container
        paths = args.partition_paths if args.partition_paths else [args.partition_key]
        kind = "MultiHash" if args.partition_paths and len(args.partition_paths) > 1 else "Hash"
        indexing_file = Path(args.indexing_policy) if args.indexing_policy else None
        container_specs = [
            ContainerSpec(
                name=args.container,
                partition_key_paths=paths,
                partition_key_kind=kind,
                indexing_policy_file=indexing_file,
                max_throughput=args.max_throughput,
            )
        ]
    else:
        # Default containers
        indexing_file = Path(args.indexing_policy) if args.indexing_policy else None
        container_specs = get_default_container_specs(
            gt_container=args.gt_container if args.gt_container else None,
            assignments_container=args.assignments_container
            if args.assignments_container
            else None,
            tags_container=args.tags_container if args.tags_container else None,
            tag_definitions_container=args.tag_definitions_container
            if args.tag_definitions_container
            else None,
            indexing_policy_file=indexing_file,
            max_throughput=args.max_throughput,
        )

    # Create client and initialize containers
    client = create_cosmos_client(
        endpoint=args.endpoint,
        key=args.key,
        use_aad=args.use_aad,
        connection_verify=not args.no_verify,
    )

    try:
        results = await initialize_containers(client, args.db, container_specs)
    finally:
        await client.close()

    # Summary
    created_count = sum(1 for r in results.values() if r["created"])
    existing_count = len(results) - created_count
    print(f"\nInitialization complete: {created_count} created, {existing_count} already existed")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Cosmos DB container initialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Azure AD auth (production):
  %(prog)s --endpoint https://myaccount.documents.azure.com:443/ --use-aad --db mydb --gt-container

  # Key auth (emulator):
  %(prog)s --endpoint https://localhost:8081 --key "<key>" --no-verify --db mydb --gt-container

  # Custom container:
  %(prog)s --endpoint <url> --key "<key>" --db mydb --container users --partition-key /userId

  # Hierarchical partition key:
  %(prog)s --endpoint <url> --key "<key>" --db mydb --container data --partition-paths /tenant /user
""",
    )

    # Authentication arguments
    auth_group = parser.add_argument_group("Authentication")
    auth_group.add_argument("--endpoint", required=True, help="Cosmos DB endpoint URL")
    auth_group.add_argument("--key", help="Cosmos DB key (for key-based auth)")
    auth_group.add_argument(
        "--use-aad",
        action="store_true",
        help="Use Azure AD authentication (DefaultAzureCredential)",
    )
    auth_group.add_argument(
        "--no-verify",
        action="store_true",
        help="Disable SSL verification (use for Cosmos Emulator)",
    )

    # Database argument
    parser.add_argument("--db", required=True, help="Database name")

    # Throughput
    parser.add_argument(
        "--max-throughput",
        type=int,
        default=None,
        help="Autoscale max throughput (RU/s) to set when creating containers",
    )

    # Default container shortcuts
    default_group = parser.add_argument_group("Default Containers (Ground Truth Curator)")
    default_group.add_argument(
        "--gt-container",
        nargs="?",
        const="ground_truth",
        default=None,
        metavar="NAME",
        help="Create ground truth container (default name: ground_truth)",
    )
    default_group.add_argument(
        "--assignments-container",
        nargs="?",
        const="assignments",
        default=None,
        metavar="NAME",
        help="Create assignments container (default name: assignments)",
    )
    default_group.add_argument(
        "--tags-container",
        nargs="?",
        const="tags",
        default=None,
        metavar="NAME",
        help="Create tags container (default name: tags)",
    )
    default_group.add_argument(
        "--tag-definitions-container",
        nargs="?",
        const="tag_definitions",
        default=None,
        metavar="NAME",
        help="Create tag definitions container (default name: tag_definitions)",
    )

    # Custom container options
    custom_group = parser.add_argument_group("Custom Container")
    custom_group.add_argument("--container", help="Custom container name")
    custom_group.add_argument("--partition-key", help="Single partition key path (e.g., /pk)")
    custom_group.add_argument(
        "--partition-paths",
        nargs="+",
        help="Hierarchical partition key paths (e.g., /tenantId /userId)",
    )

    # Bulk configuration
    bulk_group = parser.add_argument_group("Bulk Configuration")
    bulk_group.add_argument(
        "--containers",
        help="Path to JSON file with container configurations",
    )

    # Indexing policy
    parser.add_argument(
        "--indexing-policy",
        help="Path to indexing policy JSON file",
    )

    args = parser.parse_args()
    validate_args(args)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
