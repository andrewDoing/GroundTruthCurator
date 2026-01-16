---
description: Implementation details for building the export pipeline into the backend codebase
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Task Details: Export Pipeline Implementation

## Research Reference

**Source Research**: .copilot-tracking/research/20260116-export-pipeline-implementation-research.md

## Phase 1: Lock down compatibility contract

### Task 1.1: Confirm snapshot endpoint contracts (write + download)

Ensure the implementation preserves the behaviors that are already tested and used by the frontend:

- `POST /v1/ground-truths/snapshot` continues to write per-item JSON artifacts plus `manifest.json` under `exports/snapshots/{ts}/` and returns JSON with `snapshotDir`, `count`, and `manifestPath`.
- `GET /v1/ground-truths/snapshot` continues to return an `application/json` attachment with `Content-Disposition` containing a filename and stable payload keys.

* **Files**:
  - backend/app/api/v1/ground_truths.py
  - backend/app/services/snapshot_service.py
  - backend/tests/integration/test_snapshot_artifacts_cosmos.py
  - backend/tests/integration/ground_truths/test_snapshot_download_endpoint.py
  - frontend/src/services/groundTruths.ts

* **Success**:
  - Existing snapshot unit + integration tests remain the baseline acceptance gate.
  - Frontend download behavior remains unchanged (filename derived from header).

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 27-52) - Verified snapshot behaviors and frontend coupling

* **Dependencies**:
  - None

### Task 1.2: Define compatibility-safe defaults for pipeline adoption

Decide how the pipeline will be introduced without changing existing behavior:

- Treat an omitted/empty request body for `POST /v1/ground-truths/snapshot` as the legacy behavior (artifact write + manifest).
- Use the new pipeline request model only when request fields are provided.
- Keep the `GET /v1/ground-truths/snapshot` behavior stable, but allow its internal implementation to be pipeline-driven.

* **Files**:
  - docs/computed-tags-design.md (Section 4.4)
  - backend/app/api/v1/ground_truths.py

* **Success**:
  - A clear decision is written into the implementation as code-level defaults.
  - No existing callers must change.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 85-108) - Design requirements and compatibility rule
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 158-160) - Compatibility traps

* **Dependencies**:
  - Task 1.1 completion

## Phase 2: Build pipeline core (registries + request models)

### Task 2.1: Add export pipeline request/option models

Implement Pydantic models for the pipeline request body (v1) and internal options, aligned to the design:

- `format` (initial: `json_snapshot_payload`, `json_items`)
- `filters` (initial: `datasetNames`, `status` with default `approved`)
- `processors` (optional override list)
- `delivery.mode` (initial support: `attachment`, `artifact`, `stream`)

* **Files**:
  - backend/app/exports/models.py (new)

* **Success**:
  - Request validation errors map to 400 with clear messages for unknown formats/processors.
  - Defaults preserve legacy snapshot behavior when request is missing.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 85-108) - Interfaces, config, and compatibility requirements

* **Dependencies**:
  - Phase 1 completion

### Task 2.2: Implement processor and formatter registries

Create registries consistent with repo patterns (like computed-tags registry), supporting:

- register-by-name with duplicate rejection
- resolve-by-name with clear error messages
- resolve ordered processor chain from:
  - request override
  - or `GTC_EXPORT_PROCESSOR_ORDER` default

* **Files**:
  - backend/app/exports/registry.py (new)
  - backend/app/core/config.py (add `EXPORT_PROCESSOR_ORDER` setting)

* **Success**:
  - Registry unit tests cover duplicate registration and missing name resolution.
  - Environment parsing is deterministic and whitespace-tolerant.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 71-83) - Existing registry patterns
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 96-98) - `GTC_EXPORT_PROCESSOR_ORDER`

* **Dependencies**:
  - Task 2.1 completion

## Phase 3: Implement initial processors and formatters

### Task 3.1: Implement processor `merge_tags`

Add a processor that derives a `tags` field as the unique union of `manualTags` and `computedTags`.

- Input/output records must remain JSON-serializable dictionaries.
- Preserve `manualTags` and `computedTags` as-is.

* **Files**:
  - backend/app/exports/processors/merge_tags.py (new)

* **Success**:
  - Unit tests verify order stability (e.g., sorted output) and correct union behavior.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 98-101) - Initial pipeline features

* **Dependencies**:
  - Phase 2 completion

### Task 3.2: Implement formatters `json_items` and `json_snapshot_payload`

Add formatters:

- `json_items`: returns a JSON array of export records
- `json_snapshot_payload`: returns the stable snapshot payload envelope (`schemaVersion`, `snapshotAt`, `datasetNames`, `count`, `filters`, `items`)

* **Files**:
  - backend/app/exports/formatters/json_items.py (new)
  - backend/app/exports/formatters/json_snapshot_payload.py (new)
  - backend/app/services/snapshot_service.py (delegate payload assembly as needed)

* **Success**:
  - Formatter outputs match existing snapshot payload expectations.
  - Tests compare parsed JSON objects (not raw strings) for stability.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 31-45) - Current payload keys and tests

* **Dependencies**:
  - Task 3.1 completion

## Phase 4: Storage backends and delivery modes

### Task 4.1: Define and implement an export storage interface

Create an export storage protocol matching the design:

- `write_json(key: str, obj: dict) -> None`
- `write_bytes(key: str, data: bytes, content_type: str) -> None`
- `open_read(key: str)` (for streaming reads)
- `list_prefix(prefix: str)` (optional, for artifact discovery)

* **Files**:
  - backend/app/exports/storage/base.py (new)
  - backend/app/exports/storage/local.py (new)

* **Success**:
  - Local storage implementation supports the existing snapshot directory layout.
  - Storage key layout follows `exports/snapshots/{timestamp}/{filename}`.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 53-63) - Existing storage abstraction and current bypass
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 101-105) - Storage interface and delivery modes

* **Dependencies**:
  - Phase 3 completion

### Task 4.2: Add Azure Blob storage backend

Implement Blob storage backend using managed identity (`DefaultAzureCredential`) and the Azure Blob SDK.

- Add dependency: `azure-storage-blob`
- Add explicit settings to `Settings` (due to `extra="forbid"`):
  - `EXPORT_STORAGE_BACKEND` (`local|blob`)
  - `EXPORT_BLOB_ACCOUNT_URL`
  - `EXPORT_BLOB_CONTAINER`

* **Files**:
  - backend/pyproject.toml
  - backend/app/core/config.py
  - backend/app/exports/storage/blob.py (new)

* **Success**:
  - Blob backend can write and read artifacts using async client (`azure.storage.blob.aio`).
  - Settings validation fails fast with clear errors when backend is `blob` but configuration is missing.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 64-70) - Dependency/config constraints
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 142-155) - SDK and local dev operational notes

* **Dependencies**:
  - Task 4.1 completion

### Task 4.3: Implement delivery modes (attachment/artifact/stream)

Implement delivery behavior in the pipeline service:

- `attachment`: return JSON payload bytes with `Content-Disposition` filename
- `artifact`: write artifacts + `manifest.json` and return legacy `snapshotDir`/`manifestPath` response
- `stream`: return a `StreamingResponse` over bytes (for large payloads or Blob reads)

* **Files**:
  - backend/app/exports/pipeline.py (new)
  - backend/app/api/v1/ground_truths.py

* **Success**:
  - `GET /v1/ground-truths/snapshot` preserves current attachment semantics.
  - `POST /v1/ground-truths/snapshot` preserves current artifact-write behavior by default.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 133-140) - FastAPI response patterns
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 158-160) - Compatibility traps

* **Dependencies**:
  - Task 4.2 completion

## Phase 5: Wire into container, API, and tests

### Task 5.1: Wire registries, storage, and pipeline via container

Add pipeline service wiring in the singleton container so routers and services can depend on it.

* **Files**:
  - backend/app/container.py

* **Success**:
  - Pipeline dependencies are constructed once per app lifecycle (consistent with other services).

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 123-129) - Router/service integration expectations

* **Dependencies**:
  - Phase 4 completion

### Task 5.2: Update snapshot service and routes to use pipeline internally

Implement delegation so:

- `SnapshotService.build_snapshot_payload()` and `export_json()` route through the pipeline logic.
- API routes remain compatible but gain pipeline support when request parameters are provided.

* **Files**:
  - backend/app/services/snapshot_service.py
  - backend/app/api/v1/ground_truths.py

* **Success**:
  - Existing snapshot tests pass without modification.
  - Pipeline unit tests pass.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 31-45) - Existing endpoint contracts

* **Dependencies**:
  - Task 5.1 completion

### Task 5.3: Add new unit tests for pipeline components

Add tests for:

- registry behaviors (duplicate and missing names)
- `merge_tags` processor correctness
- formatter outputs
- delivery mode selection (unit-test level)

* **Files**:
  - backend/tests/unit/test_export_registry.py (new)
  - backend/tests/unit/test_export_pipeline.py (new)

* **Success**:
  - New unit tests provide fast validation of pipeline semantics.
  - Existing integration snapshot tests continue to pass.

* **Research References**:
  - .copilot-tracking/research/20260116-export-pipeline-implementation-research.md (Lines 162-166) - Suggested verification approach

* **Dependencies**:
  - Task 5.2 completion

## Dependencies

- Python 3.11 (repo requirement)
- FastAPI + Starlette responses already in use
- Azure SDK dependencies:
  - `azure-identity` (already present)
  - `azure-storage-blob` (to be added)

## Success Criteria

- Snapshot endpoints remain backward compatible (tests and frontend behavior)
- Pipeline components exist (registries, processor, formatter, delivery)
- Local storage works as today; Blob storage works behind a feature flag
- Tests cover pipeline logic and existing snapshot tests continue passing
