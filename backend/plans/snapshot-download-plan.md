# Snapshot download plan

Short overview:
- Return a single JSON payload of all approved ground truth items from a new/updated API endpoint so the frontend can download it directly. Defer blob storage writing for later. Keep it simple, minimal, and focused on the immediate need.

## What we will implement now
- A service method that collects approved items and builds a compact JSON payload with a manifest and the items array.
- An API endpoint that returns this payload as application/json with a Content-Disposition header so browsers download it as a file.
- No filesystem writes and no blob storage in this iteration. No legacy fallbacks.

## Files to change
- `app/services/snapshot_service.py` — add a payload-building method; avoid writing to disk for this path; remove try/except fallback for list_all.
- `app/api/v1/ground_truths.py` — add or update the snapshot endpoint to return the downloadable JSON payload (not a filesystem export path).
- (Optional, only if wiring is missing) `app/container.py` — ensure `snapshot_service` is available and used by the endpoint.
- Tests:
  - `tests/unit/test_snapshot_service.py`
  - `tests/integration/test_snapshot_endpoint.py`

## Functions (names and purposes)
- SnapshotService.collect_approved() -> list[GroundTruthItem]
  - Calls `repo.list_all_gt(status=GroundTruthStatus.approved)` and returns the model instances. No fallbacks; errors surface.

- SnapshotService.build_snapshot_payload() -> dict
  - Uses `collect_approved()` and produces a dict: `{ schemaVersion: "v1", snapshotAt: <UTC ISO-like ts>, count, datasetNames, items }`. Each item uses `model_dump(mode="json", by_alias=True, exclude_none=True)`. Use `datetime.now(timezone.utc)` for timestamps.

- ground_truths.download_snapshot() -> JSONResponse
  - FastAPI route handler (GET `/ground-truths/snapshot` or `/snapshots/download`) that calls `snapshot_service.build_snapshot_payload()` and returns it with `Content-Disposition: attachment; filename="ground-truth-snapshot-<ts>.json"` and `media_type="application/json"`.

## API shape (now)
- GET /ground-truths/snapshot
  - 200 OK
  - Body: JSON object with manifest + items array
  - Headers: `Content-Type: application/json`, `Content-Disposition: attachment; filename=ground-truth-snapshot-<ts>.json`

Example payload (abbreviated):
```
{
  "schemaVersion": "v1",
  "snapshotAt": "20250826T173000Z",
  "datasetNames": ["faq", "docs"],
  "count": 2,
  "filters": {"status": "approved"},
  "items": [ { /* item 1 */ }, { /* item 2 */ } ]
}
```

## Minimal behavior notes and assumptions
- Only approved items are included (no other filters in this iteration).
- Use built-in `dict`/`list` types when annotating; avoid `typing.Dict`/`typing.List`.
- Timestamps via `datetime.now(timezone.utc)` to match repo conventions.
- If there are zero approved items, return `count: 0` and `items: []`.
- Keep payload construction in-memory (no streaming) for simplicity; revisit streaming if payloads grow large.

## Tests (names and scope)
- Unit: test_build_snapshot_payload_includes_only_approved
  - Only approved items appear in payload `items`.

- Unit: test_build_snapshot_payload_counts_and_timestamp_present
  - `count` equals items length and `snapshotAt` exists.

- Unit: test_build_snapshot_payload_has_dataset_names_sorted_unique
  - `datasetNames` is unique, sorted, excludes empty strings.

- Unit: test_collect_approved_calls_repo_with_status
  - Verifies repo called with `status=GroundTruthStatus.approved`.

- Integration: test_snapshot_endpoint_returns_json_attachment
  - 200 OK with `Content-Type` and `Content-Disposition` headers.

- Integration: test_snapshot_endpoint_returns_manifest_and_items
  - Body has `schemaVersion`, `snapshotAt`, `count`, `items` keys.

- Integration: test_snapshot_endpoint_empty_list_returns_empty_payload
  - Returns `count: 0`, `items: []` when none approved.

## Out of scope (future work)
- Writing to blob storage in a specific layout.
- Streaming response or pagination for very large datasets.
- Local filesystem export paths and manifests (existing helper may remain but is not used by the new endpoint).

## Simple step sequence
1) Add `collect_approved()` and `build_snapshot_payload()` to `SnapshotService`.
2) Update/add endpoint in `ground_truths.py` to return downloadable JSON using the new service method.
3) Add unit and integration tests listed above.
4) Verify with existing test suite and formatter/type checks.
