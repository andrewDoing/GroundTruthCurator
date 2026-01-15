#!/usr/bin/env python3
"""
Cosmos DB Export/Import Script
==============================

This script exports documents from a source Azure Cosmos DB container and imports them
into a target container with hierarchical partition keys (HPK). It's designed for
migrating data between Cosmos DB instances (e.g., from cloud to local emulator).

FEATURES:
- Exports data in paginated JSONL format for memory efficiency
- Supports hierarchical partition keys (/datasetName, /bucket)
- Concurrent/bulk import with retry logic for 429 throttling
- Dry-run mode for validation without writing
- Flexible missing partition key policies

USAGE:
1. Configure environment variables in '.env' file (use sample_cosmos_export_import.env as template)
2. Run: python cosmos_export_import.py

CONFIGURATION:
All settings are loaded from '.env' file:
- Source/target Cosmos DB connection strings and credentials
- Partition key paths (default: ["/datasetName", "/bucket"])
- Batch sizes, concurrency settings
- DRY_RUN mode for validation only
    - Note with DRY_RUN=true, export to jsonl files will still occur,
      hence allowing an export to file without importing into another instance
- Missing partition key handling policy

EXAMPLES:
# Export from cloud to local emulator (dry-run first)
DRY_RUN=true python cosmos_export_import.py

# Actual migration
DRY_RUN=false python cosmos_export_import.py

OUTPUT:
- Creates ./cosmos_export/ directory with paginated JSONL files
- Each page contains up to EXPORT_PAGE_SIZE documents
- Import processes files in batches of IMPORT_batch_SIZE

ERROR HANDLING:
- Automatic retry with exponential backoff for 429 (throttling)
- Configurable missing partition key policies: error/skip/default
- Detailed logging of progress and errors

NOTE: Ensure target container has sufficient RU/s to avoid throttling during import.
"""

import os
import json
from pathlib import Path
import time
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.cosmos.exceptions import CosmosHttpResponseError
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.identity import DefaultAzureCredential

# ------------- Configuration -------------


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:  # catches None and empty string
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


DOTENV_PATH = Path(".env")
load_dotenv(dotenv_path=DOTENV_PATH)

SRC_ACCOUNT_URI = require_env("SRC_ACCOUNT_URI")
SRC_DATABASE = require_env("SRC_DATABASE")
SRC_CONTAINER = require_env("SRC_CONTAINER")

DST_ACCOUNT_URI = require_env("DST_ACCOUNT_URI")
DST_DATABASE = require_env("DST_DATABASE")
DST_CONTAINER = require_env("DST_CONTAINER")


def is_dst_cosmos_emulator_in_use() -> bool:
    """Detect if Cosmos DB emulator is in use based on endpoint URL."""
    return "localhost" in DST_ACCOUNT_URI or "127.0.0.1" in DST_ACCOUNT_URI


if is_dst_cosmos_emulator_in_use():
    DST_EMULATOR_KEY = require_env("DST_EMULATOR_KEY")

# HPK paths
DST_PARTITION_KEY_PATHS_RAW = require_env("DST_PARTITION_KEY_PATHS")
try:
    DST_PARTITION_KEY_PATHS = json.loads(DST_PARTITION_KEY_PATHS_RAW)
    if not isinstance(DST_PARTITION_KEY_PATHS, list):
        raise ValueError("DST_PARTITION_KEY_PATHS must be a JSON list")
except (json.JSONDecodeError, ValueError) as e:
    raise RuntimeError(
        f"Invalid DST_PARTITION_KEY_PATHS format: {e}. Expected JSON list like: ['/datasetName', '/bucket']"
    )

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./cosmos_export")
EXPORT_PAGE_SIZE = int(os.getenv("EXPORT_PAGE_SIZE", "500"))
IMPORT_BATCH_SIZE = int(os.getenv("IMPORT_BATCH_SIZE", "200"))
BULK_MODE = os.getenv("BULK_MODE", "true").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

MISSING_PK_POLICY = os.getenv("MISSING_PK_POLICY", "error").lower()
DEFAULT_PK_VALUES_RAW = os.getenv("DEFAULT_PK_VALUES", '["UNKNOWN","DEFAULT_BUCKET"]')

# Retry/backoff
MAX_RETRY_ATTEMPTS = 10
RETRY_BACKOFF_BASE = 0.5  # seconds

CONCURRENCY = int(os.getenv("CONCURRENCY", "32"))  # number of parallel upserts


# ------------- Helpers -------------


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


def exponential_backoff(attempt: int) -> float:
    return min(RETRY_BACKOFF_BASE * (2**attempt), 30.0)


def log(msg: str):
    print(f"[cosmos-migrate] {msg}")


def transform_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove Cosmos system props; keep content unchanged.
    Add transformations here if needed later.
    """
    new_doc = dict(doc)
    for sys_field in ["_rid", "_ts", "_self", "_etag", "_attachments"]:
        new_doc.pop(sys_field, None)
    return new_doc


def get_value_by_path(doc: Dict[str, Any], path: str) -> Any:
    """
    Extract value from document following a path like "/bucket".
    """
    parts = path.strip("/").split("/")
    cur = doc
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def compute_hpk_values(doc: Dict[str, Any], paths: List[str]) -> Tuple[List[Any], List[int]]:
    """
    Returns (values_list, missing_indices) for hierarchical partition key paths.
    """
    values = []
    missing = []
    for i, path in enumerate(paths):
        val = get_value_by_path(doc, path)
        if val is None:
            values.append(None)
            missing.append(i)
        else:
            values.append(val)
    return values, missing


def parse_default_pk_values(raw: str, count: int) -> List[Any]:
    try:
        vals = json.loads(raw)
    except Exception:
        vals = []
    if len(vals) < count:
        vals = vals + [None] * (count - len(vals))
    elif len(vals) > count:
        vals = vals[:count]
    return vals


DEFAULT_PK_VALUES = parse_default_pk_values(DEFAULT_PK_VALUES_RAW, len(DST_PARTITION_KEY_PATHS))


def resolve_missing_hpk(values: List[Any], missing_indices: List[int]) -> Optional[List[Any]]:
    """
    Apply MISSING_PK_POLICY to fill or handle missing HPK components.
    """
    if not missing_indices:
        return values

    if MISSING_PK_POLICY == "error":
        return None
    elif MISSING_PK_POLICY == "skip":
        return None
    elif MISSING_PK_POLICY == "default":
        for i in missing_indices:
            default_val = DEFAULT_PK_VALUES[i]
            if default_val is None:
                return None
            values[i] = default_val
        return values
    else:
        return None


def upsert_with_retry(container, doc):
    attempts = 0
    while True:
        try:
            # Non-bulk path: let SDK infer HPK from doc fields
            container.upsert_item(doc)
            return True
        except CosmosHttpResponseError as e:
            # 429 (throttled) -> backoff, then retry
            if getattr(e, "status_code", None) == 429 and attempts < MAX_RETRY_ATTEMPTS:
                attempts += 1
                delay = min(RETRY_BACKOFF_BASE * (2**attempts), 30.0)
                log(
                    f"Throttled (429) on id={doc.get('id')}. Backing off {delay:.1f}s (attempt {attempts}/{MAX_RETRY_ATTEMPTS})"
                )
                time.sleep(delay)
                continue
            else:
                # Bubble up any non-retryable errors
                raise


# ------------- Export -------------


def export_cosmos_container_to_jsonl(
    client: CosmosClient,
    database_name: str,
    container_name: str,
    output_dir: str,
    page_size: int = 500,
) -> str:
    """
    Export all documents from a Cosmos DB container to paginated JSONL files.
    Uses by_page() for robust continuation handling.
    """
    log(f"Exporting from {SRC_ACCOUNT_URI}:{database_name}/{container_name} ...")
    ensure_dir(output_dir)

    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    query = "SELECT * FROM c"
    page_index = 1
    total_docs = 0

    try:
        iterator = container.query_items(
            query=query,
            enable_cross_partition_query=True,
            max_item_count=page_size,
        ).by_page()
    except CosmosHttpResponseError as e:
        log(f"Query initialization error: {e}")
        raise

    for page in iterator:
        docs = list(page)
        if not docs:
            break
        page_file = os.path.join(output_dir, f"{container_name}_page_{page_index}.jsonl")
        with open(page_file, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        total_docs += len(docs)
        log(f"Wrote {len(docs)} docs to {page_file}")
        page_index += 1

    log(f"Export complete: {total_docs} documents across {page_index - 1} file(s).")
    return output_dir


# ------------- Import -------------


def maybe_create_target_container(
    client: CosmosClient,
    database_name: str,
    container_name: str,
    partition_key_paths: List[str],
    throughput: Optional[int] = None,
):
    """
    Create database & container if they do not exist, with hierarchical PK definition.
    """
    log(f"Ensuring target DB '{database_name}' and container '{container_name}' exist ...")
    db_client = client.create_database_if_not_exists(id=database_name)

    try:
        db_client.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path=partition_key_paths, kind="MultiHash"),
            offer_throughput=throughput,
        )
        log("Target container is ready.")
    except exceptions.CosmosResourceExistsError:
        log("Target container already exists.")
    except CosmosHttpResponseError as e:
        log(f"Failed to create container: {e}")
        raise


def read_jsonl_files(folder: str, prefix: str) -> List[str]:
    files = []
    for name in sorted(os.listdir(folder)):
        if name.startswith(prefix) and name.endswith(".jsonl"):
            files.append(os.path.join(folder, name))
    return files


def summarize_missing_hpk_components(
    source_folder: str, prefix: str, partition_key_paths: List[str]
) -> None:
    """
    DRY_RUN validator: counts and reports missing HPK components without writing.
    """
    files = read_jsonl_files(source_folder, prefix)
    if not files:
        log(f"No JSONL files found in {source_folder} with prefix '{prefix}'")
        return

    total = 0
    missing_counts = [0] * len(partition_key_paths)

    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line)
                _, missing = compute_hpk_values(doc, partition_key_paths)
                total += 1
                for i in missing:
                    missing_counts[i] += 1

    log(f"Validation summary: checked {total} docs.")
    for i, path in enumerate(partition_key_paths):
        log(f"  Path {path}: missing in {missing_counts[i]} docs")


def import_jsonl_to_cosmos(
    client: CosmosClient,
    database_name: str,
    container_name: str,
    source_folder: str,
    source_prefix: Optional[str],
    partition_key_paths: List[str],
    batch_size: int = 200,
    bulk_mode: bool = True,
):
    """
    Import JSONL files into target Cosmos container with hierarchical partition keys.
    """
    db = client.get_database_client(database_name)
    container = db.get_container_client(container_name)

    prefix = source_prefix or container_name
    files = read_jsonl_files(source_folder, prefix)
    if not files:
        log(f"No JSONL files found in {source_folder} with prefix '{prefix}'")
        return

    total_written = 0
    total_skipped = 0

    for file in files:
        log(f"Importing from {file} to {DST_ACCOUNT_URI}:{database_name}/{container_name} ...")
        batch: List[Tuple[Dict[str, Any], List[Any]]] = []

        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line)
                doc = transform_document(doc)

                hpk_values, missing = compute_hpk_values(doc, partition_key_paths)
                if missing:
                    resolved = resolve_missing_hpk(hpk_values, missing)
                    if resolved is None:
                        total_skipped += 1
                        log(
                            f"Skipped doc id={doc.get('id')} due to missing HPK components at indices {missing}"
                        )
                        continue
                    else:
                        hpk_values = resolved

                batch.append((doc, hpk_values))

                if len(batch) >= batch_size:
                    if DRY_RUN:
                        total_written += len(batch)  # pretend write
                        log(f"[DRY_RUN] Would write {len(batch)} docs")
                    else:
                        written = write_batch(container, batch, bulk_mode=bulk_mode)
                        total_written += written
                    batch = []

        if batch:
            if DRY_RUN:
                total_written += len(batch)
                log(f"[DRY_RUN] Would write {len(batch)} docs")
            else:
                written = write_batch(container, batch, bulk_mode=bulk_mode)
                total_written += written

    log(
        f"Import complete: {total_written} documents {'validated' if DRY_RUN else 'written'}, {total_skipped} skipped (policy={MISSING_PK_POLICY})."
    )


def write_batch(
    container, docs_with_pk: List[Tuple[Dict[str, Any], List[Any]]], bulk_mode: bool = True
) -> int:
    """
    Write a batch of documents with retry on 429.
    For HPK, partition key is a list in the same order as paths.
    If bulk_mode=true, use concurrent upserts (no explicit partition_key kwarg).
    """
    # If someone enables bulk_mode, but the SDK doesn't have container.bulk, we'll use concurrency instead.
    if bulk_mode:
        log(f"Using concurrent upserts: CONCURRENCY={CONCURRENCY}, batch_size={len(docs_with_pk)}")
        total_success = 0
        # Kick off upserts in parallel
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as tp:
            futures = [tp.submit(upsert_with_retry, container, d) for (d, _pk_list) in docs_with_pk]
            for fut in as_completed(futures):
                try:
                    if fut.result():
                        total_success += 1
                except CosmosHttpResponseError as e:
                    log(f"Upsert failed: {e}")
                    # If desired, you can collect failed docs and retry sequentially here.
                    # For now, we just log and continue to next future.
                    continue
        log(f"Concurrent upserts wrote {total_success}/{len(docs_with_pk)} docs")
        return total_success

    # Fallback: sequential upserts (non-bulk)
    success = 0
    for d, _pk_list in docs_with_pk:
        upsert_with_retry(container, d)
        success += 1
    log(f"Sequential upserts wrote {success}/{len(docs_with_pk)} docs")
    return success


# ------------- Main orchestration -------------


def main():
    # Build one DefaultAzureCredential and reuse it
    # For user-assigned managed identity, you can do:
    # aad_credential = DefaultAzureCredential(managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"))
    aad_credential = DefaultAzureCredential()

    # Source client (AAD)
    src_client = CosmosClient(SRC_ACCOUNT_URI, credential=aad_credential, logging_enable=True)

    # Target client (emulator or AAD)
    if is_dst_cosmos_emulator_in_use():
        log("Using Cosmos Emulator for target client")
        dst_client = CosmosClient(DST_ACCOUNT_URI, credential=DST_EMULATOR_KEY, logging_enable=True)
    else:
        dst_client = CosmosClient(DST_ACCOUNT_URI, credential=aad_credential, logging_enable=True)

    # 1) Export
    export_cosmos_container_to_jsonl(
        client=src_client,
        database_name=SRC_DATABASE,
        container_name=SRC_CONTAINER,
        output_dir=OUTPUT_DIR,
        page_size=EXPORT_PAGE_SIZE,
    )

    # 2) Ensure target container exists (HPK-aware)
    maybe_create_target_container(
        client=dst_client,
        database_name=DST_DATABASE,
        container_name=DST_CONTAINER,
        partition_key_paths=DST_PARTITION_KEY_PATHS,
        throughput=None,  # set higher RU/s temporarily if you see 429s
    )

    # 3) Optional: summarize_missing_hpk_components (no writes)
    if DRY_RUN:
        summarize_missing_hpk_components(OUTPUT_DIR, SRC_CONTAINER, DST_PARTITION_KEY_PATHS)

    # 4) Import with HPK mapping
    import_jsonl_to_cosmos(
        client=dst_client,
        database_name=DST_DATABASE,
        container_name=DST_CONTAINER,
        source_folder=OUTPUT_DIR,
        source_prefix=SRC_CONTAINER,  # files are named using source container
        partition_key_paths=DST_PARTITION_KEY_PATHS,
        batch_size=IMPORT_BATCH_SIZE,
        bulk_mode=BULK_MODE,
    )


if __name__ == "__main__":
    main()
