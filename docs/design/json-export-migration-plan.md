# Plan: Migrate from JSONL to JSON (single-document model)

## Summary

- Replace all JSONL assumptions/usages with JSON across docs, frontend demo/provider, and backend snapshot/export.
- Each Ground Truth is a single JSON document using the attached schema (schemaVersion v1).
- Backend/API serialize using exact wire keys (including hyphenated keys), and exports a single JSON array file per snapshot plus a manifest.
- Frontend provider and UI copy updated from “JSONL” to “JSON”.

## Goals and Non-goals

- Goals
  - Canonical representation: one JSON object per Ground Truth, aligned with the real schema.
  - Snapshot/export format: JSON (array file), not JSONL.
  - API I/O and persistence use the same field names as the schema.
- Non-goals
  - Changing business rules (assignment, approval gating, etc.).
  - New schema version (stay on v1; we’re changing the export wire format only).

## Canonical JSON schema (wire format)

Use these keys exactly in API I/O, persistence, and exports:

- Required core
  - `id`: string (e.g., "gt_{uuid}")
  - `datasetName`: string
  - `bucket`: number (int)
  - `status`: "draft" | "accepted" | "deleted"
  - `docType`: "ground-truth-item"
  - `schemaVersion`: "v1"
- SME/curation
  - `curationInstructions`?: string
  - `synthQuestion`: string
  - `editedQuestion`?: string
  - `answer`?: string
  - `refs`: Array<{ `url`: string; `content`: string; `keyExcerpt`: string; `type`: string }>
  - `tags`: string[]
- Generation/provenance
  - `contextUsedForGeneration`?: string
  - `contextSource`?: string
  - `modelUsedForGeneration`?: string
- Sampling fields
  - `semanticClusterNumber`?: number
  - `weight`?: number (0–1)
  - `samplingBucket`?: number (0–999)
  - `questionLength`?: number
- Assignment & audit
  - `assignedTo`?: string
  - `assignedAt`?: string (ISO-8601 UTC)
  - `updatedAt`?: string (ISO-8601 UTC)
  - `updatedBy`?: string
  - `reviewedAt`?: string (ISO-8601 UTC)
  - `_etag`?: string

Notes
- Times are ISO-8601 UTC strings.
- Hyphenated keys ("synth-question", "edited-question") and camelCase keys must be preserved in API I/O and persistence.

## Export/snapshot format

- Artifact layout per snapshot timestamp:
  - `./exports/snapshots/{timestamp}/ground-truth-{uuid}.json` — single JSON per approved item, each item exactly as per schema.
  - `./exports/snapshots/{timestamp}/manifest.json` — metadata: `{ schemaVersion, snapshotAt, datasetNames, count, filters }`.
- Remove JSONL (`part-*.jsonl`) generation from code paths and docs.

## Backend changes

- `backend/app/domain/models.py`
  - Align Pydantic models with wire schema via field aliases:
    - `synth_question: str = Field(alias="synthQuestion")`
    - `edited_question: str | None = Field(default=None, alias="editedQuestion")`
    - Use aliases for camelCase: `datasetName`, `assignedTo`, `assignedAt`, `updatedAt`, `updatedBy`, `reviewedAt`, `semanticClusterNumber`, `samplingBucket`, `questionLength`.
  - Types:
    - `bucket`: `int`
    - `refs` structure matches `{ url, content, keyExcerpt, type }`.
  - Model config: `populate_by_name=True`; export with `by_alias=True`; ensure safe JSON (`ser_json_inf_nan=False`).

- `backend/app/services/snapshot_service.py`
  - Replace `export_jsonl()` with `export_json()`.
  - Write a single JSON file per ground truth (`ground-truth-{uuid}.json`) and a `manifest.json`.
  - Serialize with `model_dump(mode="json", by_alias=True, exclude_none=True)`.

- `backend/app/adapters/storage/local_fs.py`
  - Replace JSONL writer utilities with JSON helper:
    - `write_json(path, obj)`.
  - Ensure directories exist and `.json` extensions are used.

- `backend/app/api/v1/ground_truths.py`
  - Update snapshot route to call `export_json()` and adjust responses to reference JSON artifacts.
  - Ensure all request/response bodies use alias serialization.

- `backend/app/adapters/repos/*`
  - Ensure Cosmos read/write uses `by_alias=True` on dumps and accepts aliases on validate/parse.

- Tests (`backend/tests/unit/*`)
  - Snapshot test asserts presence and validity of the set of `ground-truth-{uuid}.json` and `manifest.json`.
  - Remove JSONL-specific assertions and fixtures.

Acceptance criteria (backend)
- Snapshot route produces `{ts}/ground-truth-{uuid}.json` and `{ts}/manifest.json` with correct counts and schemaVersion.
- JSON array items validate against the wire schema (round-trip with Pydantic by_alias).
- No `.jsonl` is produced anywhere. All unit tests pass.

## Frontend changes

- `frontend/src/models/provider.ts`
  - Remove JSONL constructs: `DEMO_JSONL`, `JsonlProvider`, `providerId: "jsonl"`.
  - Add `DEMO_JSON: any[]` as canonical seed (array of schema-valid items).
  - Provider `export(ids?)` returns a pretty-printed JSON array string.

- `frontend/src/hooks/useGroundTruth.ts`
  - Replace `exportJsonl()` with `exportJson()` returning `{ ok: true; json: string }`.
  - Initialize with `DEMO_JSON` and new provider.

- UI (`frontend/src/demo.tsx`, `frontend/src/components/app/HeaderBar.tsx`, etc.)
  - Rename UI copy: “Export JSONL” → “Export JSON”.
  - Preview modal shows formatted JSON; clipboard copies JSON string.

- Docs: `frontend/CODEBASE_GUIDE.md`, `frontend/REFACTORING_PLAN.md`
  - Replace JSONL references with JSON; update provider class names and behavior.

Acceptance criteria (frontend)
- Demo loads from `DEMO_JSON` and renders items.
- “Export JSON” copies a valid JSON array string and shows preview.
- No references to “JSONL” remain in UI or provider code/guides.

## Documentation updates

- `docs/ground-truth-curation-reqs.md`
  - Replace “export JSONL” with “export JSON (array file)” in Requirements and Appendix A notes.
- `backend/docs/fastapi-implementation-plan.md`
  - Update artifact names and paths to JSON equivalents.
  - Remove `part-*.jsonl` examples.
- Add a short note in `.specstory/history` describing the migration (optional).

## API compatibility and versioning

- Keep `schemaVersion: "v1"`.
- Routes unchanged; snapshot returns now refer to JSON artifacts.
- Always serialize with `by_alias=True` to preserve field names.

## Edge cases and validation

- Empty snapshot: manifest with `count: 0`.
- Date/enum safety: ensure ISO-8601 strings; no NaN/Infinity in JSON.

## QA checklist

- Backend
  - POST `/v1/ground-truths/snapshot` writes JSON artifacts and returns metadata.
  - GET `/v1/ground-truths/{datasetName}?status=approved` returns items with canonical field names.
- Frontend
  - No “JSONL” text in UI.
  - Export payload JSON.parse-able; round-trips correctly.
- Repo search: no lingering `jsonl` mentions except historical notes.

## Timeline (suggested)

- Day 1: Backend aliases + snapshot JSON writer + tests.
- Day 2: Frontend provider/UI refactor + docs update + end-to-end smoke.
- Day 3: Optional conversion script + cleanup.

## Impacted files

- Backend
  - `backend/app/domain/models.py`
  - `backend/app/services/snapshot_service.py`
  - `backend/app/adapters/storage/local_fs.py`
  - `backend/app/api/v1/ground_truths.py`
  - `backend/tests/unit/*`
  - `backend/docs/fastapi-implementation-plan.md`
- Frontend
  - `frontend/src/models/provider.ts`
  - `frontend/src/hooks/useGroundTruth.ts`
  - `frontend/src/demo.tsx`
  - `frontend/src/components/app/HeaderBar.tsx`
  - `frontend/CODEBASE_GUIDE.md`
  - `frontend/REFACTORING_PLAN.md`
- Docs
  - `docs/ground-truth-curation-reqs.md`

## Requirements coverage

- “We are not using JSONL in any capacity” → all JSONL usage removed.
- Single JSON document per GT → defined and enforced via aliases and export format.
- Aligned to attached schema (field names, types, and hyphenated keys) → covered in wire schema, backend aliases, and export format.
