# GUID Buckets Plan

## Overview

We will convert the ground-truth bucket from an integer to a UUID and make the API auto-assign bucket IDs during import so importers never need to supply or reason about buckets. We will not maintain bucket sizes or a bucket index; instead, bulk imports will be deterministically split into a fixed number of UUID buckets per dataset per import operation (default 5). This keeps client UX simple and spreads writes across partitions without any cross-request coordination. All API routes that reference a bucket will accept UUIDs (as proper UUID type) instead of ints. No legacy fallback for numeric buckets is included in this plan.

## What we’ll implement (only what we need now)

- Change the `bucket` field to UUID across models, routes, and repository methods.
- Automatically assign UUID buckets on bulk import by splitting each import into N buckets (default N=5). If an import has fewer than N items, we create the minimal number of buckets necessary (at least 1).
- Keep using the Cosmos GT container MultiHash PK [`/datasetName`, `/bucket`]; the `bucket` value becomes a stringified UUID in stored documents.
- Use the NIL UUID `00000000-0000-0000-0000-000000000000` for dataset-level curation instruction docs (fixed bucket), replacing the previous numeric 0.
- Update all API endpoints and tests to treat `bucket` as a UUID (path param), not an int.

## Files to change

- `app/domain/models.py`
  - GroundTruthItem.bucket: change from `Optional[int]` to `Optional[UUID]`.
  - DatasetCurationInstructions.bucket: change to `UUID` with default NIL UUID.
  - AssignmentDocument.bucket: change from `int` to `UUID`.

- `app/adapters/repos/base.py`
  - Change method signatures taking `bucket: int` to `bucket: UUID` (or `str` but prefer `UUID`).

- `app/adapters/repos/cosmos_repo.py`
  - Ensure MultiHash PK still [`/datasetName`, `/bucket`] and pass `[datasetName, uuid_str]` as partition keys.
  - Implement per-import UUID bucket assignment that splits the items into N buckets (default 5) for the same dataset.
  - Replace all bucket-typed ints with UUID handling and normalize to strings for Cosmos queries.
  - Use NIL UUID for curation instructions `[datasetName, NIL_UUID]`.

- `app/api/v1/ground_truths.py`
  - Update routes with `{bucket}` to type as `UUID` instead of `int`.
  - Import route: accept items without bucket and let repo assign buckets.

- `app/api/v1/assignments.py`
  - Update `{bucket}` path params to type as `UUID`.

- `app/services/assignment_service.py`
  - Update `delete` method signature and calls to pass `UUID` bucket.

- Tests under `tests/integration/**` and `tests/unit/**`
  - Update fixtures and assertions to use UUID buckets.
  - Add tests for import auto-assignment and bucket rollover at ~2,000 items.

- Dev docs and examples
  - `test.http`: replace numeric bucket examples with UUID examples.
  - `README.md` or `CODEBASE.md` sections referencing integer buckets.

## Function-by-function changes

Contract notes (inputs/outputs):
- Partition keys: always pass `[datasetName: str, bucket: UUID|str]`; serialize UUID to string for Cosmos SDK.
- Timestamps: when updating, set with `datetime.now(timezone.utc)`.
- Import splitting: for a bulk import request, generate up to N fresh UUID bucket IDs for the dataset and distribute items evenly across them (round-robin). Items that already specify a bucket are honored and not reassigned.

### Domain models (`app/domain/models.py`)
- GroundTruthItem.bucket: Optional[UUID]
  - Purpose: store UUID bucket; None on inbound import; assigned during import.
- AssignmentDocument.bucket: UUID
  - Purpose: persist SME assignment PK component with UUID bucket; document id remains `"{dataset}|{bucket}|{id}"` using `str(bucket)`.
- DatasetCurationInstructions.bucket: UUID = NIL_UUID
  - Purpose: keep dataset-level doc anchored on fixed NIL UUID as partition key.

### Repo protocol (`app/adapters/repos/base.py`)
- get_gt(dataset: str, bucket: UUID, item_id: str) -> GroundTruthItem | None
  - Purpose: read via hierarchical PK with UUID bucket.
- soft_delete_gt(dataset: str, bucket: UUID, item_id: str) -> None
  - Purpose: soft delete using UUID partition key.
- All other methods that consume/produce `GroundTruthItem` pick up the UUID bucket naturally from the model.

### Cosmos repo (`app/adapters/repos/cosmos_repo.py`)
- _to_doc(item: GroundTruthItem) -> dict
  - Purpose: dump item, ensure `updatedAt`; when `bucket` is UUID, serialize to string.
- _from_doc(doc) -> GroundTruthItem
  - Purpose: parse UUID strings back to UUID type via Pydantic.
- import_bulk_gt(items: list[GroundTruthItem], buckets: int = 5) -> None
  - Purpose: assign buckets to incoming items lacking `bucket`; for each dataset in the batch, generate up to `buckets` new UUIDs and distribute those items evenly across them (round-robin). If items already have a bucket, leave them untouched.
- get_gt(dataset: str, bucket: UUID, item_id: str)
  - Purpose: pass partition_key `[dataset, str(bucket)]` to Cosmos.
- soft_delete_gt/delete_dataset/mark_approved/upsert_assignment_doc
  - Purpose: consistently use UUID bucket value when constructing partition keys and compound IDs.

New helper in cosmos repo:
- def _compute_bucket_assignments(dataset: str, n_items: int, buckets: int) -> list[UUID]
  - Purpose: produce a list of UUIDs of length `min(n_items, buckets)` for the dataset; import logic then assigns items round-robin across this list.

### API layer (`app/api/v1/ground_truths.py`, `app/api/v1/assignments.py`)
- Path params `{bucket}`: change to `UUID` type (FastAPI will validate/parse UUIDs).
- Import route: continue accepting `list[GroundTruthItem]`; callers omit `bucket`, repo assigns it. No change to the wire schema beyond making `bucket` optional and, when present, a UUID string in responses.

### Services (`app/services/assignment_service.py`)
- delete(dataset: str, bucket: UUID, item_id: str) -> None
  - Purpose: align to UUID bucket and delegate to repo.

## Tests to add/update

- test_import_bulk_assigns_uuid_buckets
  - Items missing bucket receive UUID buckets automatically; total number of unique buckets per dataset is `min(N, unique_items_without_bucket)`, default N=5.
- test_import_even_distribution_across_N_buckets
  - Items are distributed as evenly as possible across the generated UUID buckets via round-robin.
- test_import_respects_existing_bucket_values
  - Items that already specify a bucket are preserved; only bucketless items get assigned.
- test_api_get_put_with_uuid_bucket_path
  - Endpoints accept and return UUID bucket values.
- test_assignment_flow_with_uuid_bucket
  - Assignments container IDs include UUID bucket string.
- test_curation_instructions_use_nil_uuid_bucket
  - Curation docs read/write with NIL UUID partition.
- test_repo_get_gt_and_soft_delete_with_uuid
  - Partition key list uses stringified UUID and succeeds.

## Edge cases and notes

- Concurrency: No global index or active bucket to coordinate. Splitting occurs within a single import call; use SDK bulk operations grouped by partition to optimize RU. Ensure the operation is idempotent (deterministic item IDs) so client retries don’t create duplicates.
- Throughput: Group writes by partition (i.e., batch items by `[datasetName, bucket]`) when invoking Cosmos SDK bulk operations or transactional batches to reduce RU and improve latency/throughput.
- Config: Make the default number of buckets per import (N) configurable via environment variable (e.g., `GTC_IMPORT_BUCKETS_DEFAULT=5`) and allow a per-request override in the import API (validated and bounded, e.g., 1–50). If omitted, use the configured default.
- Configurability: Allow `buckets` (N) to be provided as an optional query/body parameter for the import route, with sane bounds (e.g., 1 <= N <= 50); default to 5.
- Mixed datasets: If a single import mixes multiple datasets, compute bucket sets per dataset and distribute independently.
- Pre-assigned buckets: Honor items that already include a `bucket` value. Do not reassign.
- Small batches: If item count per dataset is less than N, create only as many buckets as needed (at least 1). Single-item imports can end up in unique buckets, which is acceptable.
- Backfill/migration: Not in scope per instructions—existing integer buckets are not handled here.
- NIL UUID constant: `00000000-0000-0000-0000-000000000000` is used for dataset-level docs’ bucket only.
- Sampling fields (`samplingBucket`) remain integers and are unrelated to storage bucket.
- Response shape: Bucket appears as a UUID string in API responses via Pydantic JSON serialization.

## Short implementation sequence

1) Update domain models to UUID bucket types and NIL UUID default for curation instructions.
2) Adjust repo protocol signatures for UUID buckets.
3) Implement per-import UUID assignment in the Cosmos repo: for each dataset in the batch, allocate up to N fresh UUID buckets and round-robin bucketless items across them; update partition key usage accordingly.
4) Update API paths to `UUID` for `{bucket}` and optionally allow an import parameter `buckets` (N) with validation and a default of 5.
5) Update services and all call sites.
6) Update tests and sample requests; ensure even distribution across N buckets and respect for pre-assigned buckets.
7) Verify with integration tests against emulator.

## Implementation status (2025-08-22)

- Domain models updated: `GroundTruthItem.bucket` is `Optional[UUID]`; `AssignmentDocument.bucket` is `UUID`; `DatasetCurationInstructions.bucket` defaults to NIL UUID.
- Repo protocol updated to use `UUID` for `bucket` params; `import_bulk_gt` accepts optional `buckets` (N) override.
- Cosmos repo:
  - Container PK remains MultiHash `[/datasetName, /bucket]`.
  - All partition key usages stringify `UUID` values.
  - Bulk import assigns up to N UUID buckets per dataset, round-robin across items missing bucket; honors pre-assigned buckets; N defaults to `GTC_IMPORT_BUCKETS_DEFAULT` (5) and is bounded [1, 50].
  - Curation docs use NIL UUID for the bucket.
  - Assignment documents use UUID bucket in ID and body; model-validated on read/write.
- API:
  - Path params `{bucket}` now typed `UUID` for ground-truth and assignments routes.
  - Import endpoint supports `?buckets=N` to override default.
  - Legacy bucketless delete retained but mapped to NIL UUID.
- Services: `AssignmentService.delete` updated to UUID.
- Docs/examples: `test.http` and one user doc updated to show UUID buckets; broader doc sweep still pending.

Follow-ups:
- Add/adjust tests covering UUID buckets, import distribution, NIL UUID curation docs, and API path validation.
- Update remaining docs (`README.md`, `CODEBASE.md`, and any numeric bucket examples) to reference UUID buckets and NIL UUID usage.
