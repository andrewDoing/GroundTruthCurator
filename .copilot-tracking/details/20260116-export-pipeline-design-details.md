---
description: Implementation details for export pipeline design in Ground Truth Curator
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Task Details: Export Pipeline Design

## Research Reference

Source research: `.copilot-tracking/research/20260116-export-pipeline-design-research.md`

## Phase 1: Confirm export requirements and compatibility targets

### Task 1.1: Document the current export behavior baseline

Capture the observable behaviors that must remain stable:

- `POST /v1/ground-truths/snapshot` writes per-item JSON artifacts plus `manifest.json` under `exports/snapshots/{ts}/`
- `GET /v1/ground-truths/snapshot` returns a downloadable attachment with `Content-Disposition`
- Frontend download behavior depends on `Content-Disposition` parsing

Files:

- `backend/app/services/snapshot_service.py`
- `backend/app/api/v1/ground_truths.py`
- `frontend/src/services/groundTruths.ts`

Success:

- A short “baseline contract” section exists in the design notes (what stays stable, what can change)
- The plan identifies what the new pipeline must not break

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 31-70) - Verified baseline behaviors for snapshot write/download and frontend expectations

Dependencies:

- None

### Task 1.2: Decide the v1 export pipeline API surface

Choose a minimal, forward-compatible API for pipeline-based exports.

Recommended options:

- Option A: `GET /v1/exports/ground-truths` with query params for filters and format selection
- Option B: `POST /v1/exports/ground-truths` with a request body describing filters and options

Decide and document:

- Supported formats for the initial milestone (at least JSON)
- Supported filters for the initial milestone (dataset, status; tags optional)
- Whether exports always operate on approved items or can be generalized

Files:

- New router file (proposed): `backend/app/api/v1/exports.py`
- Existing snapshot routes: `backend/app/api/v1/ground_truths.py`

Success:

- The plan includes a clear route definition and request/response shape
- Backward compatibility for snapshot endpoints is explicitly preserved

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 154-160) - API surface recommendations for pipeline-based exports

Dependencies:

- Task 1.1 completion

## Phase 2: Define the export pipeline abstractions (processors, formatters, registry)

### Task 2.1: Specify processor and formatter interfaces

Define interfaces aligned to the existing design in `docs/computed-tags-design.md`:

- Export processors: `List[dict] -> List[dict]`
- Export formatters: `List[dict] -> bytes | str`

Document required properties:

- Stable `name`/`format_name` identifiers
- Deterministic behavior requirements for tests
- Error handling conventions (raise vs collect errors)

Files:

- Proposed new module(s):
  - `backend/app/exports/processors/base.py`
  - `backend/app/exports/formatters/base.py`

Success:

- Interfaces are defined in the plan with method signatures and naming rules
- The registry approach (discover/register) is specified

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 138-153) - Proposed pipeline architecture and core concept definitions
- `docs/computed-tags-design.md` (Export pipeline architecture section)

Dependencies:

- Task 1.2 completion

### Task 2.2: Specify registries and configuration strategy

Define:

- `ExportProcessorRegistry` to register processors and prevent name collisions
- `ExportFormatterRegistry` to register formatters and resolve requested formats
- Configuration via environment variable(s), e.g. `GTC_EXPORT_PROCESSOR_ORDER="merge_tags,anonymize"`

Decide:

- How unknown processor/formatter names fail (400 with clear error)
- Defaults when env vars are empty or unset

Files:

- Proposed new module(s):
  - `backend/app/exports/registry.py`
  - `backend/app/core/config.py` (new settings fields)

Success:

- Plan documents exact env var names, defaults, and validation rules
- Plan specifies how registries are wired in `backend/app/container.py`

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 97-105) - Existing docs mention processor ordering via env var
- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 183-191) - Naming conventions and determinism guidance for registry/config behavior

Dependencies:

- Task 2.1 completion

## Phase 3: Define the execution flow (load, process, format, deliver)

### Task 3.1: Specify export execution orchestration

Design an `ExportService` (or extend `SnapshotService`) that:

1. Loads items from `GroundTruthRepo` using the selected filters
2. Converts items to export records (`model_dump(..., by_alias=True)`)
3. Applies the configured processor chain
4. Formats output using the selected formatter
5. Delivers output either as:
   - A generated artifact (FileResponse), or
   - An in-memory attachment (JSONResponse), or
   - A streaming response for large payloads

Files:

- Proposed new service: `backend/app/services/export_service.py`
- Existing snapshot service: `backend/app/services/snapshot_service.py`

Success:

- The plan contains a step-by-step flow diagram (text is sufficient)
- The plan specifies where `Content-Disposition` filename is generated

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 161-176) - Streaming and file download guidance (FileResponse/StreamingResponse)

Dependencies:

- Phase 2 completion

### Task 3.2: Define initial processors and formatters

Initial candidates (minimum viable set):

- Processor: `merge_tags` (construct `tags = unique(manualTags + computedTags)` and/or enforce export union contract)
- Formatter: `json_snapshot_payload` (preserve current `GET /snapshot` payload shape)
- Formatter: `json_items` (export list of items only)

Document:

- Exact JSON shapes
- How schemaVersion is set
- Whether manifest is included and what fields it contains

Files:

- Proposed new modules under `backend/app/exports/`

Success:

- The plan has JSON examples for each formatter output
- The plan explicitly preserves current snapshot payload keys used by the frontend

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 118-124) - Computed tags/export compatibility considerations
- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 146-152) - Export record/processor/formatter contract

Dependencies:

- Task 3.1 completion

## Phase 4: Storage targets (multi-backend) and artifact strategy

### Task 4.1: Define a multi-backend export storage interface

Define an `ExportStorage` (or similarly named) abstraction that the pipeline-based export endpoint will use to write artifacts.

Design goals:

- Support multiple backends behind a stable interface.
- Make Azure Blob the initial concrete implementation.
- Optionally keep a local filesystem implementation for dev/test.

Decide whether:

- `SnapshotStorage` is generalized to `ExportStorage` and snapshot uses it, or
- Snapshot remains its own service, while the new export pipeline uses a separate storage abstraction

If generalized, define:

- Methods required beyond `write_json` (e.g., `write_bytes`, `open_read`, `list_prefix`)
- A minimal “artifact key” strategy (prefix + timestamp + logical filename)

Files:

- `backend/app/adapters/storage/base.py`
- `backend/app/adapters/storage/local_fs.py`

Success:

- The plan includes a clear abstraction boundary and migration steps
- The plan identifies the minimal method set required for Blob and local FS

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 72-81) - Existing storage adapter building blocks and current bypass
- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 177-181) - Evolution plan for integrating generalized storage (Blob-first)

Dependencies:

- Phase 3 completion

### Task 4.2: Specify Azure Blob configuration and authentication strategy

Document settings required for Blob-first storage:

- Container name
- Storage account URL (or connection string, if preferred)
- Authentication approach:
  - Recommended: Managed Identity / `DefaultAzureCredential` via `azure-identity`
  - Alternative: connection string via environment variable

Also document required dependency changes:

- Add `azure-storage-blob` to backend runtime dependencies

Files:

- `backend/app/core/config.py` (new settings fields)
- `backend/pyproject.toml` (dependency addition)

Success:

- Plan lists exact env var names and the auth priority order
- Plan notes settings strictness (`extra="forbid"`) and the need to add fields explicitly

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 83-96) - Verified Blob readiness gaps + existing `azure-identity` dependency
- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 132-136) - Additional gaps for Blob-first implementation

Dependencies:

- Task 4.1 completion

### Task 4.3: Define delivery strategy for Blob-hosted artifacts

Decide what the export endpoint returns when using Blob storage:

- Option A: Backend streams content (downloads from Blob and proxies to client) while preserving `Content-Disposition`
- Option B: Backend returns a short-lived SAS URL (client downloads directly)
- Option C: Backend returns an export “job id” and a separate download endpoint

Document:

- Security expectations (who can access the artifact, TTL, auditing)
- Frontend changes required (if any) based on chosen option

Files:

- Proposed router file: `backend/app/api/v1/exports.py`

Success:

- Plan selects one option for the initial milestone and documents the rationale
- Plan preserves existing snapshot download behavior

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 62-70) - Frontend depends on `Content-Disposition` filename parsing
- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 161-176) - FileResponse/StreamingResponse guidance

Dependencies:

- Task 4.2 completion

## Phase 5: Testing, observability, and rollout

### Task 5.1: Add test strategy for pipeline configuration and outputs

Plan tests covering:

- Registry duplicate name protections
- Processor order configuration parsing
- JSON output shape compatibility with existing snapshot download tests
- Large payload path choice (artifact vs streaming) is at least unit-tested via a small fake dataset

Files:

- `backend/tests/unit/` (new tests)
- Existing snapshot tests for reference:
  - `backend/tests/unit/test_snapshot_service.py`
  - `backend/tests/integration/ground_truths/test_snapshot_download_endpoint.py`

Success:

- Tests are identified by file and target behavior
- The plan includes a rollout step that does not break existing endpoints

Research references:

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` (Lines 188-191) - Determinism guidance for stable tests

Dependencies:

- Phase 4 completion

## Dependencies

- Backend: FastAPI + Pydantic v2 (already in repo)
- Storage: multi-backend interface with Azure Blob as initial concrete implementation (local filesystem optional for dev/test)

## Success Criteria

- A clear design exists for processors/formatters/registries, aligned to existing snapshot behavior
- Backward compatibility for snapshot endpoints is preserved
- The plan includes a minimal initial implementation slice (JSON export) and a growth path (additional formats and storage targets)
