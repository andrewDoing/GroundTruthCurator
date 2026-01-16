---
description: Research findings to support an export pipeline design plan for Ground Truth Curator
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Research: Export Pipeline Design

## Tooling notes (how findings were verified)

- Workspace search: `file_search` and `grep_search` were used to locate existing snapshot/export routes, services, and tests.
- File inspection: `read_file` was used to review the current implementations and confirm actual behavior.
- External references: `fetch_webpage` was used to pull verified FastAPI documentation for streaming/file download responses.

## Scope

Define an export pipeline architecture that supports:

- The existing snapshot export behaviors (write artifacts + download as attachment)
- Multiple output formats (at least JSON; optionally CSV/JSONL later)
- Pluggable transformations (processors) and final serialization (formatters)
- Future storage targets (local filesystem today; Blob later)

Additional requirement (user-provided):

- The export endpoint (pipeline-based export) should support multiple backends via an interface/adapter layer.
- The initial concrete storage backend should point to Azure Blob Storage.

## Verified repo findings (current state)

### Existing export behaviors

- There is a snapshot export write path:
  - Endpoint: `POST /v1/ground-truths/snapshot`
  - Implementation: `SnapshotService.export_json()` writes per-item JSON files and a `manifest.json` under `./exports/snapshots/{ts}/`.
  - Source: `backend/app/services/snapshot_service.py`

Minimal excerpt (write artifacts):

```python
async def export_json(self) -> dict[str, str | int]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = self.base_dir / ts
    out_dir.mkdir(parents=True, exist_ok=True)
```

- There is a snapshot download/read path:
  - Endpoint: `GET /v1/ground-truths/snapshot`
  - Implementation: builds an in-memory payload containing `{ schemaVersion, snapshotAt, datasetNames, count, filters, items }` and returns it as a JSON attachment (`Content-Disposition`).
  - Source: `backend/app/api/v1/ground_truths.py`

Minimal excerpt (attachment header):

```python
return JSONResponse(
    content=payload,
    media_type="application/json",
    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
)
```

- The frontend expects `Content-Disposition` for snapshot downloads and derives a filename from it.
  - Source: `frontend/src/services/groundTruths.ts`

Minimal excerpt (derives filename from header):

```ts
const cd = res.headers.get("Content-Disposition") || res.headers.get("content-disposition") || "";
const match = cd.match(/filename\*?=(?:UTF-8''|")?([^";]+)"?/i);
```

### Existing “storage adapter” building blocks

- A `SnapshotStorage` protocol exists with `write_json(path, obj)`.
  - Source: `backend/app/adapters/storage/base.py`

- A local filesystem implementation exists.
  - Source: `backend/app/adapters/storage/local_fs.py`

- The current `SnapshotService` bypasses the `SnapshotStorage` abstraction and writes directly via `pathlib.Path`.
  - Source: `backend/app/services/snapshot_service.py`

### Azure Blob readiness (verified)

- The backend configuration currently does not define any Blob-related settings (no `BLOB_*` fields).
  - Source: `backend/app/core/config.py`

- The backend dependency set currently does not include `azure-storage-blob` in `pyproject.toml`.
  - Source: `backend/pyproject.toml`

- The backend already includes `azure-identity` as a dependency, which can be used to authenticate to Azure Blob via `DefaultAzureCredential`.
  - Source: `backend/pyproject.toml`

- Project documentation anticipates Azure Blob support (account URL + container) and a future adapter module.
  - Source: `backend/docs/fastapi-implementation-plan.md`

### Existing docs influencing export

- `docs/computed-tags-design.md` proposes an export processor / formatter pipeline:
  - Processors: list-in/list-out transforms (merge tags, anonymize, split/explode, etc.)
  - Formatters: final conversion to bytes/string (CSV, JSON)
  - Configuration: env var ordering (e.g., `EXPORT_PROCESSOR_ORDER`)

- `docs/json-export-migration-plan.md` documents a prior decision to move away from JSONL assumptions and keep snapshot artifacts as JSON.

## Current code patterns that the export pipeline should align with

### Serialization conventions

- The backend consistently uses Pydantic v2 with `model_dump(mode="json", by_alias=True, exclude_none=True)`.
  - Example usage in `SnapshotService.build_snapshot_payload()` and `SnapshotService.export_json()`.

### Container wiring

- Services are constructed in `backend/app/container.py` and injected through a singleton `container` referenced by routers.
  - Snapshot route calls `container.snapshot_service.*`.

### Computed tags and export

- Computed tags are applied on write paths via `apply_computed_tags()`.
  - This suggests exports should be explicit about whether they export:
    - Raw stored fields (`manualTags`, `computedTags`), or
    - A merged/derived field (`tags`) for downstream consumer compatibility.

## Gaps / constraints

- There is no generalized export endpoint or service beyond “snapshot”; exports are coupled to approved items only.
- There is no generic way to chain transformations (processors) or select output formats.
- The storage abstraction exists but is not currently used by `SnapshotService`.
- Download snapshot currently builds the full payload in memory; for large exports, streaming (or generating an artifact and returning it) may be preferable.

Additional gaps (for Blob-first implementation):

- No Azure Blob adapter implementation exists in `backend/app/` today.
- Settings are strict (`extra="forbid"`), so Blob env vars must be explicitly added to `Settings` before they can be used.
- `azure-storage-blob` must be added as a runtime dependency before implementing the adapter.

## Proposed export pipeline architecture (evidence-based)

This design combines:

- The plugin-based processor/formatter approach from `docs/computed-tags-design.md`
- The concrete snapshot behaviors already implemented (`SnapshotService`)
- Standard FastAPI patterns for file downloads and streaming

### Core concepts

- **ExportJob input**: filters (dataset/status/tags), format selection, and processor list.
- **ExportRecord**: a dict-like representation (or a strongly typed DTO) produced from `GroundTruthItem.model_dump(..., by_alias=True)`.
- **ExportProcessor**: `List[dict] -> List[dict]` transformations.
- **ExportFormatter**: `List[dict] -> bytes | str` final serialization.
- **ExportTarget/Storage**: writes artifacts (local fs today; Blob later).

### API surface recommendations

- Keep the existing snapshot routes stable for backward compatibility.
- Add a new export endpoint that makes the pipeline explicit, e.g.:
  - `GET /v1/exports/ground-truths?format=json&dataset=...&status=approved&processors=merge_tags,anonymize`
  - or `POST /v1/exports/ground-truths` with a request body defining filters and options.

### Streaming / large payload guidance

FastAPI supports returning file-like responses without buffering whole payloads.

- `FileResponse` can stream a generated artifact and sets `Content-Disposition` when `filename=` is provided.
- `StreamingResponse` can stream bytes from a generator if you want to avoid writing to disk first.

External reference:
- FastAPI “Custom Response - HTML, Stream, File, others” (`StreamingResponse`, `FileResponse`):
  - https://fastapi.tiangolo.com/advanced/custom-response/

Verified examples from the FastAPI docs (high level):

- `StreamingResponse(generator(), media_type=...)` for streaming bytes from an iterator/generator.
- `FileResponse(path, filename=...)` for sending a file with `Content-Disposition`.

## Compatibility and evolution plan

- Phase 1: implement processors/formatters and keep output JSON-compatible with current snapshot payload and/or current per-item JSON artifacts.
- Phase 2: integrate a generalized export storage interface with Azure Blob as the initial concrete implementation (optionally keep local filesystem for dev/test).
- Phase 3: optional support for asynchronous/batched exports for very large datasets (queue + polling).

## Concrete implementation guidance (what we should standardize)

- Naming conventions:
  - Processor names and formatter names should be lowercase and stable (e.g., `merge_tags`, `anonymize`, `json_items`, `json_snapshot_payload`).

- Deterministic output (testability):
  - Prefer stable key ordering for manifests where it matters; otherwise rely on JSON comparison via parsed objects.
  - Avoid non-deterministic timestamps in unit tests by injecting a clock or allowing `snapshotAt` override.

- Cosmos query considerations (future):
  - Filter by dataset/bucket when possible to avoid cross-partition scans.
  - If exports become “all datasets”, make it explicit and guarded.

## Files most relevant to this task

- `backend/app/services/snapshot_service.py`
- `backend/app/api/v1/ground_truths.py`
- `backend/app/adapters/storage/base.py`
- `backend/app/adapters/storage/local_fs.py`
- `docs/computed-tags-design.md`
- `docs/json-export-migration-plan.md`
- `frontend/src/services/groundTruths.ts`

## External references: Azure Blob Storage (Python SDK)

These references support the Blob-first storage backend plan and provide verified SDK/auth patterns.

- Azure Storage Blobs client library for Python (overview + credential options + async notes):
  - https://learn.microsoft.com/en-us/python/api/overview/azure/storage-blob-readme

- Quickstart (managed identity / `DefaultAzureCredential` example):
  - https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python?tabs=managed-identity%2Cazure-portal

Key takeaways for this repo’s planned adapter:

- Client creation supports AAD token credentials (e.g., `DefaultAzureCredential`) with `account_url`, which aligns with using Managed Identity in production.
- The SDK provides async clients under `azure.storage.blob.aio`, but requires an async transport (commonly `aiohttp`) to be installed.
- A Blob-first delivery option can be implemented either by proxying downloads via the backend (preserve `Content-Disposition`) or by returning a SAS URL (client downloads directly).

