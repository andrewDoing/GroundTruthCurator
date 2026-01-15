# API Write Consolidation Plan — Ground Truths (SME + Curator Only)

This plan consolidates all write operations on Ground Truth items so they occur exclusively through two endpoint surfaces:
- SME: `/v1/assignments/{item_id}` (PUT)
- Curator: `/v1/ground-truths/{datasetName}/{item_id}` (PUT)

Reference attachment/detachment and other mutable fields will be handled inside these two endpoints. We will remove any separate reference-specific endpoints to align API behavior with Cosmos DB write patterns, reduce contention, and simplify concurrency control via ETags.


## Goals

- All writes to Ground Truth items flow through two endpoints only (SME and Curator).
- Fold reference add/remove operations into the existing update operations for SME and Curator.
- Align write paths with Cosmos repository semantics (single-document ETag concurrency where possible).
- Keep curator bulk import as a separate POST endpoint.


## Current state (as of repo today)

Write-capable endpoints in `app/api/v1`:
- SME endpoints in `assignments.py`:
  - PUT `/assignments/{item_id}` — SME edit/approve
  - POST `/assignments/self-serve` — assign new batch (creates assignment docs)
  - GET `/assignments/my` — list user assignments
- Curator endpoints in `ground_truths.py`:
  - PUT `/ground-truths/{datasetName}/{item_id}` — curator update
  - POST `/ground-truths` — bulk import
  - DELETE `/ground-truths/{datasetName}` — delete dataset (admin)
  - DELETE `/ground-truths/{datasetName}/{item_id}` — delete item (admin)
  - POST `/ground-truths/snapshot` — export (write to storage, not GT item)
  - Reference-specific (to be consolidated):
    - POST `/ground-truths/{datasetName}/{item_id}/references`
    - DELETE `/ground-truths/{datasetName}/{item_id}/references/{ref_id}`

Problem: reference-specific endpoints diverge from how writes will be organized in Cosmos (one doc update path for GT item), introduce extra surface area, and complicate authorization logic.


## Proposed design

Consolidate writes to these two update endpoints only:
- SME writes: `PUT /v1/assignments/{item_id}`
- Curator writes: `PUT /v1/ground-truths/{datasetName}/{item_id}`

Both endpoints accept a structured update payload that supports:
- Partial field updates (patch semantics) for allowed fields per role.
- Reference attachment/detachment via an explicit references delta.
- Optional `etag` for optimistic concurrency (If-Match behavior).

Reference-only endpoints will be removed.


### Update payloads (request schemas)

We will introduce role-scoped update request models in `domain/models.py` (or `api/v1/*` schemas if preferred). The shapes below are illustrative; we will finalize to match current domain types.

Common reference delta:
- `references`: object with two optional arrays:
  - `add: ReferenceInput[]` — new references to attach
  - `remove: str[]` — reference IDs to detach

ReferenceInput includes fields required by retrieval/AI search integration and UI (example):
- `refId?: str` (optional if server generates IDs)
- `docId: str`
- `sourceType: Literal["ai-search", "manual", "other"]`
- `relevantParagraph: str` (required)
- `snippet?: str`
- `score?: float`
- `metadata?: dict[str, Any]`

Concurrency:
- `etag?: str` — if provided by the client, the update will use If-Match semantics against the stored `_etag`. In dev mode, `etag` may be omitted; in prod, require an ETag (configurable).
Note: Cosmos DB `_etag` is a system-generated property returned on reads; clients never set `_etag` directly. The API will surface the current `_etag` in responses and accept it back either via this `etag` field or the standard `If-Match` HTTP header.

SME update body (allowed fields):
- `status?: Literal["draft", "approved", "deleted"]` (SME can approve; deletion here performs soft delete on the item)
- `editedQuestion?: str`
- `editedAnswer?: str`
- `tags?: list[str]` (optional; limited to allowed set if enabled)
- `references?: { add?: ReferenceInput[]; remove?: str[] }`
- `etag?: str`

Curator update body (allowed fields):
- `status?: Literal["draft", "approved", "deleted"]` (Curator can restore from deleted)
- `canonicalQuestion?: str`
- `canonicalAnswer?: str`
- `tags?: list[str]`
- `notes?: str`
- `references?: { add?: ReferenceInput[]; remove?: str[] }`
- `etag?: str`

Response (both):
- Returns the updated `GroundTruthItem` (server-authoritative shape) including new `_etag` value and full `references` list.


### Semantics and validation

- Reference attachment:
  - `relevantParagraph` is required for every added reference.
  - If `sourceType == "ai-search"`, validate `docId` and any index constraints via `search_service` (no-op in dev). Fail fast on invalid refs.
- Reference removal:
  - Removing a non-existent `refId` is idempotent (ignored) unless strict mode enabled.
- Role-based field masks:
  - SME endpoint enforces allowed fields; attempts to mutate curator-only fields are rejected with 403 or 422 as appropriate.
  - Curator endpoint can mutate the full set (within business rules).
- Concurrency:
  - If client supplies `etag`, perform If-Match update; on mismatch, return 412 Precondition Failed with current server etag.
  - If `etag` is omitted, behavior is environment-dependent: allow in `dev`, require in `prod` (config flag `GTC_REQUIRE_ETAG_WRITES`).
- Assignment checks (SME):
  - SME PUT requires the item be assigned to the authenticated SME user (or include a valid assignment context). Otherwise 403.


## API changes

- Keep endpoint paths unchanged for SME/Curator PUT; expand their request bodies to include `references` delta.
- Remove the following reference-specific endpoints:
  - POST `/v1/ground-truths/{datasetName}/{item_id}/references`
  - DELETE `/v1/ground-truths/{datasetName}/{item_id}/references/{ref_id}`
- Retain a separate Curator import endpoint for creating new ground truths:
  - POST `/v1/ground-truths` — curator-only bulk import; not used for updates.


## Cosmos repository alignment

- Prefer single-document updates for Ground Truth items including reference arrays; use Cosmos system `_etag` on the GT item document for concurrency instead of separate per-reference documents.
- `_etag` handling:
  - Cosmos generates `_etag` automatically; repository returns it on reads/updates.
  - Updates use conditional replace with If-Match set to the last known `_etag`.
  - In-memory repo will simulate `_etag` changes per write to mirror behavior.
- Repository interface changes (`adapters/repos/base.py`):
  - Extend the update method to accept a structured update (fields delta + references delta + etag).
  - Ensure implementations (memory + Cosmos later) apply adds/removes atomically to the `references` array.
- Service layer (`services/search_service.py`, `services/tagging_service.py`):
  - Move any reference validation/AI Search hooks into the update flows invoked by SME/Curator endpoints.


## Implementation plan (files and touchpoints)

- API routers
  - `app/api/v1/assignments.py` — extend PUT to accept `references` delta; enforce assignment and field masks; return updated item with etag.
  - `app/api/v1/ground_truths.py` — extend PUT to accept `references` delta; remove reference-specific endpoints; keep POST import endpoint for curator bulk import.
- Domain models / schemas
  - `app/domain/models.py` — define `ReferenceInput`, `ReferencesDelta`, `SmeUpdateRequest`, `CuratorUpdateRequest` (or place these in dedicated `api` schemas package if preferred).
  - `app/domain/enums.py` — ensure statuses include `draft`, `approved`, `deleted`.
- Services
  - `app/services/tagging_service.py` — validate tags if needed.
  - `app/services/search_service.py` — validate new references (relevantParagraph required; AI Search doc existence when available).
  - `app/services/assignment_service.py` — unchanged except for ensuring SME update flow removes approved items from SME queue immediately (already planned behavior).
- Repositories
  - `app/adapters/repos/base.py` — update interface to support field and references delta with etag.
  - `app/adapters/repos/memory_repo.py` — implement atomic in-memory add/remove for references and etag check.
  - (Later) Cosmos adapter — implement If-Match using `_etag` and atomically update `references` array.
- Tests
  - `tests/unit/test_assignments.py` — add cases: add/remove references via SME PUT; etag mismatch 412.
  - `tests/unit/test_ground_truths.py` — add cases: curator add/remove references; import remains via POST; reference-only endpoints no longer exist.
  - `tests/unit/test_stats.py` — ensure counts remain correct after reference updates.


## API examples (sketch)

SME update with ref add/remove and approval:

```
PUT /v1/assignments/123
{
  "editedQuestion": "What is XYZ?",
  "editedAnswer": "XYZ is...",
  "status": "approved",
  "references": {
    "add": [
      {
        "docId": "doc-abc",
        "sourceType": "ai-search",
        "relevantParagraph": "para text",
        "snippet": "...",
        "score": 0.92
      }
    ],
    "remove": ["ref-old-1"]
  },
  "etag": "\"0000-aaaa\""
}
```

Curator update (restore from deleted, replace tags):

```
PUT /v1/ground-truths/my-dataset/123
{
  "status": "draft",
  "tags": ["billing", "howto"],
  "references": {
    "remove": ["ref-orphan"]
  }
}
```

## Acceptance criteria

- All reference modifications are supported via the SME and Curator PUT endpoints using `references` delta.
- Reference-specific endpoints have been removed.
- Writes use ETag-based optimistic concurrency; 412 returned on mismatch.
- SME endpoint enforces assignment ownership and role-based field masks.
- Unit tests cover happy paths and key edge cases (invalid reference, missing paragraph, etag mismatch, unauthorized field change).


## Risks and mitigations

- Concurrency conflicts: require `etag` in prod; return 412 with current etag to enable retry.
- Reference validation latency (AI Search): keep validation optional in dev; timeouts with clear 504/502 mapping and retry guidance.


## Notes on alignment with Cosmos

- By funneling all field/reference writes through one document update per item and using `_etag`, we avoid cross-document transactions and better match Cosmos RU-efficient point-writes.
- Reference arrays remain embedded within the Ground Truth item document; any search index side effects (if needed) are triggered by services synchronously or via future background processes.


---
Requirements coverage:
- "All writes occur from two endpoints (SME and Curator)" — Delivered via consolidated update payloads and removal of reference-specific endpoints.
- "Align with Cosmos write patterns" — Single-document updates with ETag enforcement.
- "Change references via SME/Curator update" — References delta supported in both payloads with validation.
- "Curator import remains a separate POST" — Explicit curator-only bulk import endpoint retained.
