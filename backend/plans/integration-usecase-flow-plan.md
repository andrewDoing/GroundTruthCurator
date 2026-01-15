# Integration Use‑Case Flow — Test Plan

Short overview
- Goal: add realistic integration tests that simulate bulk import (1k/10k), multi‑user self‑serve assignment, mixed actions (leave draft, approve, skip, delete), then request more, verifying correctness at each step.
- Scope is tests only. We’ll use existing public API endpoints and current semantics; if a gap blocks the flow, we’ll note one minimal change to close it (no legacy fallbacks).

Assumptions
- Auth in tests uses X-User-Id header (dev mode), per `get_current_user` and `tests/integration/conftest.py`.
- Current endpoints (already present) we will exercise:
  - POST `/v1/ground-truths` — bulk import
  - POST `/v1/assignments/self-serve` — request N assignments
  - GET  `/v1/assignments/my` — list caller’s assigned draft items, returning for each: `id`, `dataset`, `bucket`, `status`, `etag`, `assignedAt`
  
  - PUT  `/v1/assignments/{dataset}/{bucket}/{item_id}` — SME update: approve, or set status=skipped/deleted (with If-Match)
- Status semantics we’ll validate:
  - draft: shows up in “my assignments” and eligible for SME edits.
  - approved: removed from “my assignments”; not sampled for re-assignment.
  - skipped: removed from “my assignments”; should be eligible for re-assignment once unassigned.
  - deleted: removed from “my assignments”; not eligible for re-assignment.

Only-what-we-need right now
- Focus on end-to-end behavior with Cosmos backend: import → self-serve → list → mutate → request more → verify.
- Guard large-volume (10k) test behind a `stress` marker and/or env flag so the suite stays fast by default.
- Avoid legacy/alternate endpoints. Use the currently implemented SME/curator endpoints only.

Files to add/change (tests only)
- tests/integration/test_usecase_flow_cosmos.py — main test module with parametrized scenarios.
- tests/integration/helpers_usecase.py — small helpers for API calls (headers, import, fetch `bucket`/`etag` via `/assignments/my`, update flows).
- tests/integration/__init__.py — ensure package discovery if needed.
- pytest.ini — register custom markers `large` and `stress` (tiny edit).
- Optionally tests/README.md — quick notes on running large tests and expected runtime/RUs.

Planned small API enhancements and enforcement
- Extend `GET /v1/assignments/my` response shape to include: `id`, `dataset`, `bucket`, `status`, `etag`, `assignedAt` for each item.
- Enforce ownership on SME update route: only the assigned user may mutate; on violation return HTTP 403 with a stable error code (e.g., `ASSIGNMENT_OWNERSHIP`).
- Require `If-Match` on all write paths (approve, skip, delete) and return the updated `etag` in the response body (and/or ETag header).
- app/api/v1/assignments.py: on status transitions to skipped/approved/deleted, clear assignment fields (`assignedTo`, `assignedAt`) atomically; consider deleting any separate assignment doc if present.
- app/adapters/repos/*: ensure repo methods invoked by approve/skip/delete clear assignment fields atomically.

Helper function names (tests) and purpose
- headers_for(user_id: str) -> dict[str, str]
  - Build `{"X-User-Id": user_id}` for requests.
- make_items(dataset: str, n: int) -> list[dict]
  - Generate n valid ground-truth items as JSON payloads (reuse existing `make_item` where available).
- import_bulk(async_client, items: list[dict]) -> None
  - POST to `/v1/ground-truths`; assert 200.
- self_serve(async_client, user: str, limit: int) -> dict
  - POST `/v1/assignments/self-serve` with `{"limit": limit}`; return parsed response.
- list_my(async_client, user: str) -> list[dict]
  - GET `/v1/assignments/my` for user; rows already include `id`, `dataset`, `bucket`, `status`, `etag`, `assignedAt`.
  
- approve_item(async_client, dataset: str, bucket: str, item_id: str, user: str, answer: str | None = None) -> dict
  - PUT `/v1/assignments/{dataset}/{bucket}/{item_id}` with body `{"approve": true, "answer": answer}` and header `If-Match: etag`; return updated item (including new `etag`).
- update_status(async_client, dataset: str, bucket: str, item_id: str, etag: str, user: str, status: str) -> dict
  - PUT SME route with body `{"status": status}` and header `If-Match: etag`; return updated item (including new `etag`).
- assert_distinct_sets(sets: list[set[str]]) -> None
  - Assert no overlap across users’ assignment id sets.

Test names and behaviors to cover
- test_bulk_import_1000_and_distinct_selfserve_three_users [large]
  - Three users self‑serve; no overlapping assigned ids.
- test_selfserve_then_mixed_actions_and_request_more
  - Approve some, skip some, delete some; request more fills back.
- test_bulk_import_10000_high_volume_assignment_smoke [stress]
  - 10k import, N-per-user self‑serve works within budget.
- test_idempotent_selfserve_does_not_duplicate_assignments
  - Repeated self‑serve doesn’t reassign same ids to same user.
- test_cross_user_update_forbidden
  - User B cannot mutate item assigned to user A.
- test_concurrent_selfserve_no_duplicates
  - Parallel self‑serve calls do not assign the same item twice.
- test_post_actions_visibility_in_my_assignments
  - Only draft items appear in “my assignments”.
- test_skipped_items_become_reassignable_after_unassign
  - Skipped items eventually unassigned and can be reassigned.

Flow details (core scenario)
1) Import
- Choose dataset string (unique per test). Generate 1000 (large) or 10k (stress) items. Import with a single POST for simplicity (or chunk by 1000 if needed).

1) Multi‑user self‑serve
- Users: `alice`, `bob`, `carol`. Each requests `limit = 100`.
- Verify: response `assignedCount == limit`. GET `/v1/assignments/my` returns exactly `limit` items each.
- Build sets of item ids per user and assert set disjointness.

1) Mixed actions for a single user (e.g., alice)
- List alice’s items via `/v1/assignments/my`; use returned `bucket` and `etag` directly.
- Partition her list into groups (e.g., first 20 approve, next 15 skip, next 10 delete, remaining stay draft).
  - Approve: call approve_item (with `If-Match`); assert status becomes approved and `etag` changes.
  - Skip: call update_status with status="skipped" and If-Match `etag`; assert status becomes skipped and `etag` changes.
  - Delete: update_status with status="deleted" and If-Match `etag`; assert status becomes deleted and `etag` changes.
- After actions: GET `/v1/assignments/my` for alice should only contain draft items; approved/skipped/deleted not present.

1) Request more after actions
- Alice calls self‑serve again with `limit = 50`.
- Verify: new assignments arrive and fill back to prior target (e.g., number of draft assignments increases accordingly). Ensure no re‑assignment of already approved/deleted items; skipped items may be re‑assigned only if unassigned (see note below).

1) Cross‑user isolation
- Attempt to approve/change an item assigned to alice using bob’s headers → expect 403/404 (ownership enforced). If current behavior differs, record and add a minimal fix to enforce ownership in the SME route.

1) Concurrency check
- Run two concurrent self‑serve calls for the same user (or for different users) with overlapping limits using asyncio.gather. Verify aggregate unique assignments equal sum of limits; no duplicates in results or in `/my`.

Edge cases and notes
- Skipped semantics: For items updated to `status=skipped`, they should be removed from the user’s active list immediately. To become eligible for re-assignment, `assignedTo` should be cleared. If that’s not currently done by the SME PUT path, we’ll add a small change to clear assignment on skip in the product code and cover it with `test_skipped_items_become_reassignable_after_unassign`.
- ETag handling: For non-approve mutations (skip/delete), send `If-Match` using `etag` from the dataset list endpoint. Approve path may not require ETag; we’ll still verify updated `etag` is returned afterwards.
 - ETag handling: All write paths (approve, skip, delete) require `If-Match` using the most recent `etag` (from `/v1/assignments/my` or GET-by-id). Responses return the updated `etag`.
- Performance: The 10k test is marked `[stress]` and may require higher RU limits; leave skipped by default unless `-m stress` is selected.

Minimal acceptance criteria (success)
- Distinctness: no overlapping assignments across users in the same dataset/timeframe.
- Correct visibility: `/assignments/my` returns only draft items; approved/skipped/deleted are absent.
- State transitions: approve → approved; skip → skipped; delete → deleted; all persist and are reflected in subsequent reads.
- Quotas: re‑requesting assignments increases the user’s draft count (until supply exhausted) without duplicating.
- Concurrency safety: No duplicate assignments from concurrent self‑serve calls.

Planned test module structure (sketch)
- helpers_usecase.py
  - headers_for, make_items, import_bulk, self_serve, list_my, get_dataset_rows, resolve_bucket_etag, approve_item, update_status, assert_distinct_sets
- test_usecase_flow_cosmos.py
  - Test class or standalone async tests with markers: [anyio], [large], [stress]
  - Parametrize dataset sizes and per-user limits where helpful.

Out of scope (explicitly excluded)
- Search adapters and search_service flows, snapshot exports, LLM adapters.
- Legacy reference subroutes (we’ll mutate references only if needed via current PUT paths; not part of this plan).

How we’ll validate
- Run integration tests with Cosmos emulator or configured account via the built-in tasks:
  - “Run integration tests (integration env)” for default set
  - Optionally: `pytest -q -m large` or `-m stress` in CI or local stress runs

Requirements coverage
- Detailed plan with minimal functionality: included.
- Files needing changes: listed (tests + optional minor product deltas if gaps appear).
- No legacy fallbacks: none planned.
- Overview + function names + test names: included above.