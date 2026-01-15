# SME Self‑Serve Assignments — Implementation Plan

## Goal and constraints

- Users self‑serve a batch of curated items.
- AssignmentDocument exists solely to:
  - Partition all assignments by a single logical partition (fast per‑user fetch).
  - Provide a direct pointer to the underlying GroundTruth item by ID (no state duplication).
- Concurrency‑safe assignment: multiple concurrent requests must not assign the same item.
- Support idempotency: retry/continue gracefully if partial assignment fails.

---

## Data model

Contract defined in `app/domain/models.py`:

- AssignmentDocument (minimal, no duplication)
  - `pk`: string partition key = `sme:${userId}` (all a user’s assignments together)
  - `ground_truth_id`: string ID of the GroundTruthItem
  - `datasetName`: string
  - `bucket`: int
  - `docType`: "sme-assignment"
  - `schemaVersion`: "v1"

Notes:

- Do not mirror `status`, `assignedTo`, timestamps, etc., in the assignment doc.
- The GroundTruthItem retains the source of truth for status, `assignedTo`, etc.
- The assignments container uses partition key `/pk`.
- The current `AssignmentDocument` shape is sufficient.

Example (stored in assignments container):

```json
{
  "id": "<dataset>|<bucket>|<groundTruthId>",
  "pk": "sme:<userId>",
  "ground_truth_id": "<groundTruthId>",
  "datasetName": "<dataset>",
  "bucket": "00000000-0000-0000-0000-000000000000",
  "docType": "sme-assignment",
  "schemaVersion": "v1"
}
```

ID scheme: `id = ${datasetName}|${bucket}|${ground_truth_id}` (stable, deduplicates per user).

---

## Tiny contracts

Inputs:

- `userId`: string
- `limit`: int (max number of items to assign)

Outputs:

- List of `AssignmentDocument` for newly assigned items (and/or existing ones when idempotent)
- Optional list of `GroundTruthItem` summaries if needed for UX

Error modes:

- No items available
- Concurrency conflicts (picked by someone else)
- Partial success

Success criteria:

- Only items with `assignedTo=userId` are reflected in returned assignments.
- The assignments container contains one doc per `(userId, groundTruthId)` without duplicates.

---

## Repository changes (Cosmos)

### Ground truth container

Already present:

- `list_by_dataset`
- `get`
- `upsert` (with ETag replace)
- `sample_unassigned(limit)` — returns draft/skipped and unassigned items (uses `samplingBucket`).
- `assign_to(item_id, user_id)` — uses patch with filter to ensure still unassigned and `status='draft'`.

Adjustments:

- Ensure `assign_to`:
  - Also sets `assignedAt`.
  - Returns `True` only if filter succeeded; `False` otherwise.
  - Keep current design that uses `filter_predicate` with patch operations.

### Assignments container

Add methods:

- `create_or_upsert_assignment_doc(AssignmentDocument)` with idempotency
  - `id`: `${datasetName}|${bucket}|${ground_truth_id}` (uniqueness and easy upsert)
  - `pk`: `sme:${userId}`
  - Use upsert; no conflicting updates expected.
- `list_assignments_by_user(user_id)` → `AssignmentDocument[]` for `pk = sme:${userId}`
- Optional: `get_assignment_by_gt(user_id, ground_truth_id)` for idempotency checks

Why this `id`?

- Prevent duplicates per user on retries.
- Stable and deterministic.

---

## Service flow

Method: `AssignmentService.self_assign(userId, limit)`

1. Sample candidates
   - `items = repo.sample_unassigned(limit * overfetch)`
   - `overfetch = 2x` to handle contention; cap to a sane upper bound.
2. Attempt assignment atomically on each candidate
   - For each item:
     - `success = repo.assign_to(item.id, userId)`
     - If success:
       - Write `AssignmentDocument` into assignments container:
         - `pk = sme:${userId}`
         - `id = ${dataset}|${bucket}|${item.id}`
         - fields: `ground_truth_id`, `datasetName`, `bucket`
       - Collect result
     - If failure: continue to next candidate
   - Stop when `collected == limit` or candidates exhausted
3. If still below limit after pass 1:
   - Optionally retry sampling once more with a different sampling bucket set or widened criteria
4. Return `AssignmentDocument[]` and count

### Idempotency

- If the same user calls again:
  - First, list existing assignments for that user if desired and return them (or filter by not‑yet‑reviewed).
  - Or just attempt fresh assignment; upsert on assignment doc makes duplicates harmless.
- If assignment doc exists but GT no longer assigned to user (edge case), prefer source of truth in GT to decide display.

---

## API surface

Endpoints (FastAPI examples):

- `POST /api/v1/assignments/self-serve`
  - body: `{ userId: string, limit: int }`
  - returns: `{ assigned: AssignmentDocument[], requested: int, assignedCount: int }`
- `GET /api/v1/assignments/my`
  - query: `userId`
  - returns: `AssignmentDocument[]` (fast partition read)

Optional follow‑ups:

- `POST /api/v1/assignments/unassign`
  - body: `{ userId, groundTruthId }`
  - Removes assignment doc and clears `assignedTo` on GT if still assigned to that user.
- `POST /api/v1/assignments/complete`
  - Updates GT status, clears assignment fields, and deletes assignment doc.

---

## Concurrency strategy

- GroundTruth assignment relies on Cosmos patch with filter:
  - Filter: `NOT IS_DEFINED(c.assignedTo) OR c.assignedTo = null`, and `c.status = 'draft'`.
- No ETag is needed for patch with filter; the server enforces condition.
- The assignments doc write is after a successful GT patch, using idempotent upsert keyed by `user + dataset + bucket + id`.

### Failure handling

- If patch succeeds but assignments write fails transiently:
  - Subsequent self‑serve will detect GT already assigned to user when calling `assign_to` (which fails due to `assignedTo` being set).
  - To close the gap: after patch success, write the assignment doc and, on failure, retry the doc write a few times. If it still fails, reconcile on next `GET /my` by scanning GT for `assignedTo=user` and backfill missing assignment docs as needed (background reconciliation or on‑demand repair logic).
- If assignments write succeeds but patch failed (shouldn’t happen due to ordering), never write the assignment doc before patch; the flow orders patch first, then doc upsert.

---

## Edge cases

- Item with `status != draft` should be skipped.
- Item concurrently assigned by another user: patch fails; continue.
- Item previously assigned to this user:
  - `assign_to` will fail (already `assignedTo` set), but we can detect and ensure assignment doc exists by:
    - Optional: if `assign_to` failed, fetch GT by id; if `assignedTo == userId`, upsert assignment doc and count it.
- `limit == 0`: return empty.
- Dataset‑level or user‑level quotas: if needed, enforce before assignment.
- Cross‑bucket queries: covered by current GT query logic.

---

## Tests

Unit tests (repo‑level with emulator or mocked clients):

- `assign_to` succeeds when unassigned; fails when already assigned.
- `sample_unassigned` returns unassigned only.
- `create_assignment_doc` upsert produces stable id and partition key.
- `list_assignments_by_user` returns only their assignments.

Service tests:

- `self_assign` assigns up to `limit` under no contention.
- `self_assign` under contention with overfetch still fills up to `limit` when possible.
- Idempotency: calling twice returns the same set (no duplicates), and assignment docs remain one‑per‑GT per user.
- Backfill: when GT shows `assignedTo=user` but assignment doc is missing, the service can ensure doc presence (if you implement that behavior).

API tests (smoke):

- `POST` self‑serve returns expected shape and count.
- `GET` my returns consistent results post‑assign.

---

## Implementation notes for this repo

- `CosmosGroundTruthRepo` additions:
  - Methods for assignment docs:
    - `upsert_assignment_doc(user_id, gt: GroundTruthItem) -> AssignmentDocument`
    - `list_assignments_by_user(user_id) -> list[AssignmentDocument]`
  - Container creation already configures assignments with partition key `/pk`.

- `AssignmentService` (new or extend existing service):
  - `self_assign(user_id: str, limit: int)` using the flow above.
  - Optional reconciliation helper: `ensure_assignment_doc_for(user_id, gt_item)`.

- Controllers in `v1`:
  - `POST /assignments/self-serve` → calls `service.self_assign`.
  - `GET /assignments/my` → `repo.list_assignments_by_user`.

---

## Minimal field mapping

From `GroundTruthItem` to `AssignmentDocument`:

```text
pk              = "sme:" + userId
id              = gt.datasetName + "|" + str(gt.bucket) + "|" + gt.id
ground_truth_id = gt.id
datasetName     = gt.datasetName
bucket          = gt.bucket
```

No other fields are duplicated.

---

## Rollout and observability

- Add metrics/logs:
  - number sampled, attempted, assigned, docWrites, conflicts.
- Optional: retry policy with jitter for doc upserts.
- Optional: background reconciliation (scan GT for `assignedTo` per user and fix missing docs).

---

## Next steps

- Add repo methods for assignment docs.
- Implement `AssignmentService.self_assign`.
- Wire API endpoints.
- Write unit tests for repo and service.
- Smoke test locally against emulator or test account.
