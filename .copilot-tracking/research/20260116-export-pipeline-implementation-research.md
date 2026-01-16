---
description: Research findings to support implementing the export pipeline design in code (backend-first)
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Research: Export Pipeline Implementation

## Tooling notes (how findings were verified)

- Workspace search: `file_search`, `grep_search`, and `semantic_search` were used to locate snapshot/export routes, services, storage adapters, and tests.
- File inspection: `read_file` was used to confirm current endpoint behavior and service implementations.
- External references: `fetch_webpage` was used to pull verified guidance for FastAPI `FileResponse`/`StreamingResponse` and Azure Blob Storage Python SDK usage patterns.

## Scope

Implement the export pipeline architecture described in `docs/computed-tags-design.md` (Section 4.4) into the backend codebase while preserving existing snapshot endpoint behaviors.

Out of scope for the first milestone (unless needed for compatibility):

- New export endpoints beyond the existing snapshot routes
- Export job orchestration (async background jobs, polling endpoints)
- Additional formats (CSV/JSONL/ZIP) beyond the initial JSON formats described in the design

## Verified repo findings (current state)

### Snapshot routes and stable behaviors

Backend snapshot endpoints exist and are currently relied upon by tests and the frontend:

- `POST /v1/ground-truths/snapshot`
  - Implementation: calls `SnapshotService.export_json()`
  - Writes per-item JSON artifacts and a `manifest.json` under `exports/snapshots/{ts}/`
  - Source: `backend/app/api/v1/ground_truths.py`, `backend/app/services/snapshot_service.py`

- `GET /v1/ground-truths/snapshot`
  - Implementation: returns an `application/json` payload with `Content-Disposition: attachment; filename="ground-truth-snapshot-<ts>.json"`
  - Payload shape includes `schemaVersion`, `snapshotAt`, `datasetNames`, `count`, `filters`, `items`
  - Source: `backend/app/api/v1/ground_truths.py`, `backend/app/services/snapshot_service.py`

These behaviors are verified by tests:

- Artifact write verification: `backend/tests/integration/test_snapshot_artifacts_cosmos.py`
- Download endpoint behavior: `backend/tests/integration/ground_truths/test_snapshot_download_endpoint.py`
- Payload shape/unit behavior: `backend/tests/unit/test_snapshot_service.py`

### Frontend coupling

Frontend snapshot download depends on the backend providing `Content-Disposition` for a filename.

- Source: `frontend/src/services/groundTruths.ts` (parses `Content-Disposition` to derive filename)

### Existing storage abstraction (partial)

There is a small storage protocol already:

- `SnapshotStorage` protocol with `write_json(path, obj)`
  - Source: `backend/app/adapters/storage/base.py`
- `LocalFilesystemStorage` implementation
  - Source: `backend/app/adapters/storage/local_fs.py`

However, current snapshot code writes directly to disk via `pathlib.Path` and does not use the storage protocol.

### Dependency and configuration constraints

- Backend settings enforce `extra="forbid"`, so any new env vars must be explicitly added.
  - Source: `backend/app/core/config.py`
- Backend dependencies include `azure-identity` but do not include `azure-storage-blob`.
  - Source: `backend/pyproject.toml`

### Existing "registry" patterns to follow

Computed tags are implemented with:

- Interface + registry (`ComputedTagPlugin`, `TagPluginRegistry`)
- Auto-discovery of plugin implementations via module scanning

Sources:

- `backend/app/plugins/base.py`
- `backend/app/plugins/registry.py`

This is a good local precedent for the export processor/formatter registries.

## Design requirements to implement (source of truth)

The implementation should follow `docs/computed-tags-design.md` Section 4.4, including:

- Processor and formatter interfaces:
  - `ExportProcessor`: list-in/list-out deterministic transforms
  - `ExportFormatter`: list-in -> `bytes|str` serialization
- Registries:
  - Resolve processors and formatters by stable names
  - Reject duplicates
  - Unknown names produce a clear 400 error at the API
- Configuration:
  - `GTC_EXPORT_PROCESSOR_ORDER` controls default processor order
- Initial pipeline features:
  - Processor: `merge_tags` (derive `tags = union(manualTags, computedTags)`)
  - Formatters: `json_snapshot_payload`, `json_items`
- Storage interface:
  - Multi-backend export storage with `local` default and `blob` as initial cloud backend
  - Stable artifact key layout: `exports/snapshots/{timestamp}/{filename}`
- Delivery modes:
  - `attachment`, `artifact`, `stream` (backend sets `Content-Disposition`)
- Compatibility rule:
  - Snapshot endpoints must remain backward compatible (payload keys and behavior expectations)

## Implementation mapping (repo-aligned)

### Recommended package layout (new)

Create a backend package (example):

- `backend/app/exports/`
  - `models.py` (request DTOs, export record type aliases)
  - `processors/` (merge_tags)
  - `formatters/` (json_snapshot_payload, json_items)
  - `registry.py` (processor/formatter registries)
  - `storage/` (local + blob backends)
  - `pipeline.py` (execution flow: load -> process -> format -> deliver)

### Router/service integration

- Keep router thin in `backend/app/api/v1/ground_truths.py`.
- Wire pipeline services through the singleton `container` in `backend/app/container.py`, similar to other services.
- Update `SnapshotService` to delegate to the pipeline for:
  - building the snapshot payload
  - writing artifacts

## External references (verified)

### FastAPI response types

FastAPI (Starlette) supports streaming and file responses for download behavior.

- `StreamingResponse` can stream from an iterator/generator or async generator.
- `FileResponse` can stream a local file and can set `Content-Disposition` using `filename=...`.

Source: https://fastapi.tiangolo.com/advanced/custom-response/

### Azure Blob Storage SDK (Python)

- `azure-storage-blob` is required for Blob operations; `azure-identity` provides `DefaultAzureCredential`.
- Async clients exist under `azure.storage.blob.aio` and are intended for use with `asyncio`.

Sources:

- https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python
- https://learn.microsoft.com/en-us/azure/developer/python/sdk/azure-sdk-library-usage-patterns#async

Operational note for local dev:

- Developers typically need the Storage Blob Data Contributor role for their identity to read/write blobs in a dev container.

## Risks and compatibility traps

- Changing the default behavior of `POST /v1/ground-truths/snapshot` could break integration tests (and any external automation).
- Changing `GET /v1/ground-truths/snapshot` headers or payload keys will break frontend download logic and snapshot tests.
- Introducing new env vars without updating `Settings` will fail app startup due to `extra="forbid"`.

## Suggested verification approach

- Run unit tests for pipeline components (registries, processors, formatters).
- Re-run existing snapshot integration tests to ensure the snapshot endpoints remain compatible.
- Ensure OpenAPI generation remains consistent if request models change (frontend uses generated client types).
