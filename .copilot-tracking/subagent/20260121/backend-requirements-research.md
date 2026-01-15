# Backend Behavioral Requirements (Doc-Inferred)

Date: 2026-01-21

This document captures stable, high-level backend behavioral requirements inferred from backend documentation. It is intended to describe “what the backend must do” in a testable way, not propose new features.

## Scope and sources

Primary sources reviewed:

- backend/README.md
- backend/CODEBASE.md
- backend/docs/api-change-checklist-assignments.md
- backend/docs/assign-single-item-endpoint.md
- backend/docs/api-write-consolidation-plan.v2.md
- backend/docs/drift_cleanup.md
- backend/docs/tagging_plan.md
- backend/docs/export-pipeline.md
- backend/docs/multi-turn-refs.md
- backend/docs/history-tags-feature.md
- backend/docs/cosmos-emulator-limitations.md

## Requirements (by area)

### API wire conventions

- The API accepts both snake_case and camelCase inputs, but responses are always camelCase (aliases) via Pydantic.
	- Evidence (backend/CODEBASE.md#L32-L34):
		> - Pydantic v2 with aliases: accept snake_case or camelCase on input; always output camelCase via model_dump(..., by_alias=True).

### Health check

- The service exposes a health endpoint at `GET /healthz`.
	- Evidence (backend/CODEBASE.md#L14-L15, backend/CODEBASE.md#L159-L161):
		> - GET /healthz returns repo/backend info (Cosmos details when active).
		> - Health check: GET /healthz

### Optimistic concurrency (ETag / If-Match)

- Updates must enforce optimistic concurrency using Cosmos ETags.
	- Clients may supply ETag via `If-Match` header or an `etag` field in request body (depending on endpoint); missing/mismatch maps to HTTP 412.
	- Evidence (backend/CODEBASE.md#L32-L34):
		> - Concurrency uses ETag: updates require If-Match header or etag in body; 412 on missing/mismatch.

- Assignment write paths must require `If-Match` and return/echo the updated ETag.
	- Evidence (backend/docs/api-change-checklist-assignments.md#L7-L12, backend/docs/api-change-checklist-assignments.md#L74-L90):
		> - Require `If-Match` on all write paths (approve/skip/delete) and return updated ETag.
		> - Request headers (required):
		>   - `If-Match: <etag>` (all write paths)
		> - 412 Precondition Failed: Missing/invalid ETag. Error code `IF_MATCH_REQUIRED` or `ETAG_MISMATCH`. Include current ETag in `ETag` header.
	- Evidence (backend/docs/api-change-checklist-assignments.md#L168-L178):
		> - Concurrency: All writes require `If-Match` with the current ETag. On mismatch, return 412 and provide the current ETag in the `ETag` header.
		> - ETag: Return the new ETag in the 200 response body and `ETag` header.

### Delete semantics (soft delete)

- “Delete” is represented as `status=deleted` (soft delete), and list APIs filter deleted items unless status is explicitly requested.
	- Evidence (backend/CODEBASE.md#L33-L34):
		> - Soft-delete via status=deleted; list APIs filter unless status is specified.

### Write surface area (consolidation)

- Ground Truth item writes are consolidated to two update endpoints: SME PUT and Curator PUT.
	- Evidence (backend/docs/api-write-consolidation-plan.v2.md#L28-L36, backend/docs/api-write-consolidation-plan.v2.md#L60-L67):
		> - SME PUT `/v1/assignments/{item_id}`
		>   - Add: optional `etag` in body, and accept `If-Match` header
		> - Curator PUT `/v1/ground-truths/{datasetName}/{item_id}`
		>   - Add: optional `etag` in body, and accept `If-Match` header
		> - Only two endpoints perform writes to GT items: SME PUT and Curator PUT.

- Curator import remains a separate POST and is create-only (no updates).
	- Evidence (backend/docs/api-write-consolidation-plan.v2.md#L38-L45, backend/docs/api-write-consolidation-plan.v2.md#L62-L64):
		> - Curator POST `/v1/ground-truths` (import)
		>   - Unchanged in path/method; clarify it’s for create/import only (no updates)
		> - Curator POST import remains for create-only flows.

- Reference subroutes are removed; references are handled via the PUTs.
	- Evidence (backend/docs/api-write-consolidation-plan.v2.md#L21-L25, backend/docs/api-write-consolidation-plan.v2.md#L64-L66):
		> | POST   | /v1/ground-truths/{datasetName}/{item_id}/references          | Curator | Add references to item      | Remove | Fold into Curator PUT with references           |
		> | DELETE | /v1/ground-truths/{datasetName}/{item_id}/references/{ref_id} | Curator | Remove a specific reference | Remove | Fold into Curator/SME PUT via references        |
		> - Reference-specific endpoints are removed and covered by references in PUTs.

### Assignments

- Ownership must be enforced on SME mutation routes; non-owner attempts return 403 with stable error code.
	- Evidence (backend/docs/api-change-checklist-assignments.md#L7-L12, backend/docs/api-change-checklist-assignments.md#L82-L86):
		> - Enforce ownership on SME update route with 403 and stable error code.
		> - 403 Forbidden: Ownership violation. Error code `ASSIGNMENT_OWNERSHIP`.
	- Evidence (backend/docs/api-change-checklist-assignments.md#L168-L176):
		> - Ownership: Only the currently assigned user may mutate. If unassigned or assigned to a different user, return 403/`ASSIGNMENT_OWNERSHIP`.

- On transitions to skipped/approved/deleted, assignment fields must be cleared atomically (same write).
	- Evidence (backend/docs/api-change-checklist-assignments.md#L10-L12, backend/docs/api-change-checklist-assignments.md#L175-L178):
		> - Clear assignment fields atomically on transitions (skipped/approved/deleted).
		> - Assignment clearing: On transitions to skipped/approved/deleted, clear `assignedTo` and `assignedAt` atomically with the status change.

- Assignment timestamps should be timezone-aware UTC (RFC3339), set via `datetime.now(timezone.utc)`.
	- Evidence (backend/docs/api-change-checklist-assignments.md#L13-L14, backend/docs/api-change-checklist-assignments.md#L182-L184):
		> - Use timezone-aware UTC timestamps via `datetime.now(timezone.utc)` when setting or updating `assignedAt` or other timestamps.
		> - `assignedAt` (nullable, RFC3339 UTC). Set with `datetime.now(timezone.utc)`.

- `/v1/assignments/my` response must include `etag` in the JSON body (headers optional).
	- Evidence (backend/docs/api-change-checklist-assignments.md#L19-L24, backend/docs/api-change-checklist-assignments.md#L35-L38):
		> - `etag` (string)
		> - `assignedAt` (string, RFC3339 UTC)
		> - `ETag` header is optional per-item, but the item’s `etag` MUST be included in the JSON body.

- Single-item assignment endpoint (`POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign`) must enforce 409 conflict when draft-assigned to another user, and on success always sets status to draft.
	- Evidence (backend/docs/assign-single-item-endpoint.md#L22-L29, backend/docs/assign-single-item-endpoint.md#L33-L43):
		> - **409 Conflict**: Item is already assigned to another user in draft state
		> 2. **Items assigned to another user (draft status)**: Cannot be assigned (409 Conflict) ❌
		> **Important**: When an item is assigned, its status is **always set to draft**, regardless of previous state (approved, deleted, skipped, etc.).

- Successful assignment must create/upsert a secondary “assignment document” in the assignments container (materialized view) for fast per-user queries.
	- Evidence (backend/docs/assign-single-item-endpoint.md#L85-L95):
		> When an item is successfully assigned, an assignment document is created in the assignments container with:
		> ...
		> This materialized view allows fast retrieval of all items assigned to a user via `/v1/assignments/my`.

### Tagging

- Tags must be stored and returned in canonical `group:value` format (lowercase), with normalization (trim/lowercase/dedupe/sort) for deterministic output.
	- Evidence (backend/docs/tagging_plan.md#L3-L10):
		> - Canonical form is `group:value` (all lowercase). Inputs are normalized (trimmed, lowercased, deduplicated, sorted for determinism).
	- Evidence (backend/docs/tagging_plan.md#L54-L60):
		> - Lowercase group and value; trim whitespace; collapse inner whitespace; accept and normalize `group : value` to `group:value`.
		> - Deduplicate after normalization; sort ascending for deterministic storage.

- Unknown groups/values are allowed, but known-group behavioral rules (e.g., exclusivity) must be enforced.
	- Evidence (backend/docs/tagging_plan.md#L5-L10, backend/docs/tagging_plan.md#L60-L66):
		> - Unknown groups and values are allowed. We do not enforce membership in a hardcoded set.
		> - For known groups defined in our schema, we still enforce behavioral rules like mutual exclusivity.
		> - Unknown groups or values are allowed. We only enforce format and known-group rules.
		> - Exclusive groups (in the known schema) may contain at most one value.

### Snapshot export pipeline

- Snapshot export supports `attachment` and `artifact` delivery modes; missing/empty request body uses defaults equivalent to `attachment`.
	- Evidence (backend/docs/export-pipeline.md#L26-L34):
		> Supports `attachment` or `artifact` delivery.
		> If the request body is omitted or `{}`, the server uses defaults (equivalent to `delivery.mode=attachment`).

- `GET /v1/ground-truths/snapshot` always returns a JSON document payload (not artifacts).
	- Evidence (backend/docs/export-pipeline.md#L33-L38):
		> * Always returns a JSON document payload (not storage artifacts)

- Artifact exports must write one JSON file per item plus a manifest under a deterministic path, and the manifest includes `schemaVersion` currently `v2`.
	- Evidence (backend/docs/export-pipeline.md#L76-L90):
		> Artifacts are written under:
		> * `exports/snapshots/{snapshotAt}/ground-truth-{id}.json`
		> * `exports/snapshots/{snapshotAt}/manifest.json`
		> ...
		> * `schemaVersion` (currently `v2`)

- Export processors run before formatting; `merge_tags` merges manual/computed tags into a single sorted union `tags` array.
	- Evidence (backend/docs/export-pipeline.md#L116-L128):
		> ### `merge_tags`
		> Merges tag fields into a single `tags` array on each exported document:
		> * Reads `manualTags`/`manual_tags` and `computedTags`/`computed_tags`
		> * Writes `tags` as a sorted union of the two

### Multi-turn history: refs + per-turn tags

- The backend must remain backward compatible with top-level `refs` while supporting optional per-history-item `refs` for assistant messages.
	- Evidence (backend/docs/multi-turn-refs.md#L5-L8, backend/docs/multi-turn-refs.md#L67-L73):
		> This change maintains backward compatibility with the existing top-level `refs` field.
		> 1. **Top-level `refs` field preserved**: The `GroundTruthItem.refs` field at the top level remains unchanged and continues to work as before.
		> 2. **Optional refs in history**: The `refs` field in `HistoryItem` is optional (defaults to `None`), so existing history items without refs continue to work.

- History item `tags` is optional and defaults to an empty list; when parsing, accept both `msg` and `content` field names.
	- Evidence (backend/docs/multi-turn-refs.md#L71-L76):
		> 3. **Optional tags in history**: The `tags` field in `HistoryItem` is optional (defaults to an empty list), so existing history items without tags continue to work.
		> 4. **Flexible field names**: The parser supports both `msg` and `content` field names for the message text, accommodating different client implementations.

- Tags validation for history items is intentionally permissive: list-of-strings, no value-format restrictions, duplicates allowed.
	- Evidence (backend/docs/history-tags-feature.md#L140-L150):
		> - Tags must be a list of strings (enforced by Pydantic)
		> - No format restrictions on individual tag values
		> - Empty lists are allowed
		> - Duplicate tags are allowed (no automatic deduplication at model level)

### Observability and user identity

- Logs must include a `user=<id>` field derived per request; in dev mode it comes from `X-User-Id` header (else `anonymous`).
	- Evidence (backend/README.md#L334-L341):
		> Every log line now includes a `user=<id>` field derived per request:
		> - Dev mode (Easy Auth disabled): uses the `X-User-Id` header if provided, otherwise `anonymous`.
		> - Tests can set `X-User-Id` to simulate multiple users.

### Local dev and emulator constraints

- When using Cosmos Emulator and multiturn data containing Unicode, the backend must support disabling unicode escaping to avoid emulator parsing bugs.
	- Evidence (backend/README.md#L104-L121):
		> - `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true` (workaround for emulator Unicode bug with multiturn data)
		> **Solution:** Set `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true` ... ensures that the backend sends real UTF-8 characters instead of escape sequences...

- Emulator does not support `ARRAY_CONTAINS`, so tag-filtering queries against the emulator cannot rely on server-side `ARRAY_CONTAINS` behavior.
	- Evidence (backend/docs/cosmos-emulator-limitations.md#L5-L18, backend/README.md#L248-L259):
		> **Issue:** The Cosmos DB Emulator does not support the `ARRAY_CONTAINS` SQL function...
		> ...
		> Integration tests that test tag filtering functionality must be skipped when using the emulator
		> ...
		> **Note:** Some tests are skipped when using the Cosmos DB Emulator due to unsupported features (e.g., `ARRAY_CONTAINS` for tag filtering).

## Notes / interpretation boundaries

- Some docs (e.g., drift cleanup) describe the intended “design compliance” direction rather than a fully enforced current behavior; items listed under “Goal/Acceptance criteria” are treated here as target requirements.
	- Evidence (backend/docs/drift_cleanup.md#L7-L18):
		> Goal: align current FastAPI endpoints so all Ground Truth writes happen only via SME PUT and Curator PUT...
		> ... ETag-based concurrency enforced, and reference-specific routes removed.