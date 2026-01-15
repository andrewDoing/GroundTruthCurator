# Curation Instructions — Implementation Plan

## Overview
We’ll introduce a dataset-level “curation instructions” document that holds Markdown instructions for SMEs. We’ll store one document per dataset alongside existing ground-truth items in the same container, expose GET/PUT endpoints to fetch and update it with ETag concurrency, and add a minimal service and repo methods to keep responsibilities clean. We’ll implement only the essential get/set flows; no legacy fallbacks, auto-propagation to items, or version history for now.

## Minimal scope (only what we need now)
- One document per dataset: Markdown text + metadata (`id`, `datasetName`, `bucket=0`, `docType`, `schemaVersion`, `updatedAt`, `updatedBy`, `etag`).
- Store in the ground-truth container, partitioning by `datasetName` (bucket fixed to `0`).
- Endpoints:
	- `GET /api/v1/datasets/{datasetName}/curation-instructions`
	- `PUT /api/v1/datasets/{datasetName}/curation-instructions` (requires `If-Match` for update; omit `If-Match` to create if missing)
- Concurrency control: ETag (`If-Match` → 412 on mismatch).
- Auth: same auth dependency as other v1 endpoints. No role checks in this phase.
- No pagination, history, or search.

## Storage decision
- Store alongside ground-truth items: Yes.
	- Reason: reuse existing Cosmos container, consistency with dataset partitioning, and simpler operational model. We’ll use `docType="curation-instructions"`, `id="curation-instructions|{datasetName}"`, `datasetName={datasetName}`, `bucket=0` for MultiHash PK compatibility.
	- Alternative containers are unnecessary at this phase; they’d add wiring and latency without clear benefits.

## Files to change
- `app/domain/models.py`
	- Add `DatasetCurationInstructions` model.
- `app/adapters/repos/base.py`
	- Extend protocol with curation instructions methods.
- `app/adapters/repos/memory_repo.py`
	- Implement in-memory get/upsert for `DatasetCurationInstructions`.
- `app/adapters/repos/cosmos_repo.py`
	- Implement Cosmos get/upsert using the GT container (MultiHash PK: `[datasetName, 0]`).
- `app/services/curation_service.py` (new)
	- Thin service orchestrating repo calls and enforcing simple rules.
- `app/api/v1/datasets.py` (new) or `app/api/v1/ground_truths.py` (add handlers)
	- Add GET/PUT routes for curation instructions; prefer a new datasets router for clarity.
- `app/api/v1/router.py`
	- Include new datasets router with prefix="/datasets".
- `app/container.py`
	- Wire `CurationService` into container.

## Function and endpoint definitions

### Domain
- `class DatasetCurationInstructions(BaseModel)`
	- Fields: `id`, `datasetName`, `bucket (int=0)`, `docType="curation-instructions"`, `schemaVersion="v1"`, `instructions (str)`, `updatedAt (datetime)`, `updatedBy (str|None)`, `etag (str|None, alias _etag)`.
	- Purpose: schema for dataset-level instructions with Cosmos-friendly serialization.

### Repo protocol (`GroundTruthRepo`)
- `async def get_curation_instructions(self, dataset: str) -> DatasetCurationInstructions | None`
	- Fetch dataset-level instructions document or `None` if not found.
- `async def upsert_curation_instructions(self, doc: DatasetCurationInstructions) -> DatasetCurationInstructions`
	- Create or update; honor ETag when provided (raise `ValueError("etag_mismatch")` on 412).

### InMemoryGroundTruthRepo
- Implement `get_curation_instructions` and `upsert_curation_instructions`.
- Keep a simple dict keyed by `id="curation-instructions|{dataset}"`. Generate/verify ETag as UUID strings.

### CosmosGroundTruthRepo
- `async def get_curation_instructions(dataset: str) -> DatasetCurationInstructions | None`
	- Read by id with PK `[dataset, 0]` or query TOP 1 by id; return parsed model.
- `async def upsert_curation_instructions(doc: DatasetCurationInstructions) -> DatasetCurationInstructions`
	- If `doc.etag` provided, use replace with `IfNotModified`; else create/upsert; return updated doc with new ETag and `updatedAt`.

### Service: `app/services/curation_service.py`
- `class CurationService`
	- `def __init__(self, repo: GroundTruthRepo)` — store repo.
	- `async def get_for_dataset(self, dataset: str) -> DatasetCurationInstructions | None` — thin pass-through to repo get.
	- `async def set_for_dataset(self, dataset: str, instructions: str, user_id: str, etag: str | None) -> DatasetCurationInstructions` — build/merge doc with id and PK fields, set `updatedBy` and `updatedAt`, call repo upsert. If `etag` provided, attach; else omit to allow create. Propagate etag mismatch as service error.

### API: `app/api/v1/datasets.py`
- `router = APIRouter()`
- `@router.get("/datasets/{datasetName}/curation-instructions")`
	- Returns 200 with doc JSON (`by_alias`) and `{ etag }` field; 404 if not found.
- `@router.put("/datasets/{datasetName}/curation-instructions")`
	- Body: `{ instructions: string, etag?: string }`. Also support `If-Match` header. If neither `etag` is provided and doc exists, reject with 412 to require concurrency token. Returns updated doc with `etag`. 201 if created, 200 if updated. Map `ValueError("etag_mismatch")` to 412.

### Container wiring
- `self.curation_service = CurationService(self.repo)`

## Tests to add
- `tests/unit/test_curation_models.py` — Validates model aliases and ETag serialization.
- `tests/unit/test_curation_service_set_create.py` — Creates doc when missing; sets `updatedBy/At`.
- `tests/unit/test_curation_service_update_with_etag.py` — Updates succeed with correct ETag; returns new ETag.
- `tests/unit/test_curation_service_update_etag_mismatch.py` — Raises `etag_mismatch` when `If-Match` wrong.
- `tests/unit/test_memory_repo_curation_docs.py` — In-memory repo create/update/get happy path.
- `tests/unit/test_datasets_router_get_404.py` — GET returns 404 when doc not found.
- `tests/unit/test_datasets_router_put_create_201.py` — PUT without ETag creates new; returns 201.
- `tests/unit/test_datasets_router_put_update_200_etag.py` — PUT with `If-Match` updates; returns 200 and new ETag.
- `tests/unit/test_datasets_router_put_etag_mismatch_412.py` — PUT wrong `If-Match` returns 412.
- `tests/integration/test_curation_instructions_cosmos.py` — Cosmos: create, fetch, update with ETag, mismatch 412.

## Implementation notes and constraints
- ID scheme: `id = "curation-instructions|{datasetName}"`. Partition key: `[datasetName, 0]` to satisfy MultiHash path `[/datasetName, /bucket]` in GT container. Set `bucket=0` on the doc.
- Wire format: Return `by_alias` JSON and include explicit `etag` field in responses, mirroring existing ground-truth serialization pattern.
- Concurrency:
	- Create: no `If-Match` required when doc doesn’t exist.
	- Update: require `If-Match` (header or body `etag`); if missing and doc exists, return 412.
- Validation: basic checks only (non-empty `instructions` string; length cap optional later). For now, accept any string.
- Security: reuse existing `get_current_user` dependency; set `updatedBy` to user principal or id (`UserContext`).
- Non-goals now:
	- No propagation to item-level `curationInstructions`.
	- No version history, diffing, or audit log beyond `updatedAt/By`.
	- No listing all datasets’ instructions.
	- No role-based authorization.

## Requirements coverage
- Add curation instructions doc per dataset: Planned with `DatasetCurationInstructions` model, repo methods, service.
- Expose via endpoint: Planned GET/PUT handlers under `/datasets/{datasetName}/curation-instructions`.
- Store alongside ground-truth items: Yes—same GT container; `docType="curation-instructions"`, `bucket=0`, MultiHash PK respected.
