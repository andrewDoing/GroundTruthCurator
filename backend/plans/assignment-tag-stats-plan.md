# Assignment stats by tag – plan

Short overview

Implement a minimal endpoint to show, for the current user, a breakdown of their currently assigned items by tag. Keep it simple: count each item once per tag, include an “(untagged)” bucket for items with no tags, and return a small JSON payload. Do this entirely by composing existing APIs (list assigned items) with an in-memory aggregation; no new storage or complex queries.

What and why (only what we need now)

- Scope: “My assignments” workload snapshot by tag. This helps SMEs see where their current queue is concentrated. We do not compute historical/user-wide performance or status beyond draft right now.
- Simplicity: Use repo.list_assigned(user_id) and aggregate in Python. No repo changes required. No pagination needed (assigned list is already bounded by assignment flow).
- No legacy fallbacks or extra knobs. We will not add filters/sorting in v1.

Files to change

- `app/api/v1/assignments.py`
  - Add a new GET route: `/assignments/my/stats-by-tag`.
- `app/services/assignment_service.py`
  - Add a method to compute stats by tag for the current user from `list_assigned` results.

Optional (defer unless needed by type/shape consistency)

- `app/domain/models.py`
  - If we want typed responses, add a tiny Pydantic model, e.g., `TagCount` and/or `AssignmentTagStats`. For v1, return a plain dict response to keep it simple.

API design (v1)

- Route: `GET /v1/assignments/my/stats-by-tag`
- Auth: Same as other assignments routes (uses `get_current_user`).
- Response (minimal):
  ```json
  {
    "byTag": {
      "safety": 4,
      "usability": 2,
      "(untagged)": 1
    },
    "total": 7,
    "uniqueTags": ["(untagged)", "safety", "usability"]
  }
  ```
- Notes:
  - Count each item once per tag (items with multiple tags contribute to multiple tag buckets).
  - Items with no tags contribute to `(untagged)`.
  - Only considers draft items currently assigned to the user (consistent with `list_assigned`).

Functions to add/change

- `AssignmentService.stats_by_tag_for_user(user_id: str) -> dict[str, int] | tuple[dict[str, int], int]`
  - Fetch the user’s currently assigned items via `self.repo.list_assigned(user_id)` and aggregate a simple per-tag count. Returns a mapping `{ tag: count }` and optionally the total for convenience.

- `list_my_assignments_stats_by_tag()` in `app/api/v1/assignments.py`
  - FastAPI route handler for `GET /assignments/my/stats-by-tag`. Calls the service method, formats the response into `{ byTag, total, uniqueTags }` and returns JSON. No request body. Uses `get_current_user` for context.

Edge cases and simple handling

- Empty assignment list -> `{ byTag: {}, total: 0, uniqueTags: [] }`.
- Items with duplicate tags in their array -> de-duplicate per item to avoid double counting within the same item.
- Non-string/invalid tags (should be prevented by validators) -> ignore if encountered.

Tests to add

- `tests/unit/test_assignment_tag_stats_service.py::test_counts_simple`
  - One user with a few assigned items; verify straightforward counts.

- `tests/unit/test_assignment_tag_stats_service.py::test_counts_multiple_tags_per_item`
  - Item has multiple tags; contributes to each tag exactly once.

- `tests/unit/test_assignment_tag_stats_service.py::test_counts_handles_untagged`
  - Items with no tags increment `(untagged)`; totals correct.

- `tests/integration/test_assignments_stats_api.py::test_stats_by_tag_endpoint_happy_path`
  - Seed items with tags, assign to user, call endpoint, verify shape and counts.

- `tests/integration/test_assignments_stats_api.py::test_stats_by_tag_ignores_other_users`
  - Items assigned to a different user don’t affect counts.

Implementation steps (straightforward)

1) Service: implement `stats_by_tag_for_user` in `assignment_service.py`:
   - Get items = `await repo.list_assigned(user_id)`.
   - For each item: build a per-item set of tags; if empty, use `{"(untagged)"}`.
   - Increment counters per tag. Track total as `len(items)` (each item counted once in total).

2) API: add route in `assignments.py`:
   - `@router.get("/my/stats-by-tag")` -> call service and return `{ byTag, total, uniqueTags }`.

3) Tests: add unit tests for service logic and integration tests for the route.

Non-goals (v1)

- No dataset filter, no status breakdowns beyond the draft-only nature of current assignments.
- No pagination, sorting, or top-N limiting.
- No repo changes or server-side aggregation queries; Python aggregation is sufficient for initial needs.

Future follow-ups (separate plans)

- Add optional dataset filter and/or status breakdown (draft/approved/skipped/deleted).
- Add organization-level dashboards (all users) with tag breakdown using efficient queries.
- Expose similar breakdown for global GT pool (not just current user).
