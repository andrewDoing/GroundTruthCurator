# Integration coverage gaps - plan

Short overview
- Add targeted integration tests (Cosmos-backed) to cover untested endpoints and edge cases: status filters, duplicate import conflicts, ETag error paths, snapshot artifacts, assignments flows, tags/schema helpers, search read endpoint, and LLM negative paths. No app code changes; only new tests and small fixture helpers if needed.

How will we implement only the functionality we need right now?
- Reuse existing integration fixtures (in-process ASGI client, per-test Cosmos DB, user headers).
- Mock outbound HTTP for Azure services with respx; skip these tests if respx isn’t available.
- Keep scope to missing behaviors only; do not introduce new routes or back-compat shims.

Identify files that need to be changed
- New files under `tests/integration/`:
  - `test_ground_truths_get_and_filters_cosmos.py`
  - `test_ground_truths_import_conflicts_cosmos.py`
  - `test_ground_truths_etag_errors_cosmos.py`
  - `test_snapshot_artifacts_cosmos.py`
  - `test_assignments_flow_cosmos.py`
  - `test_tags_schema_integration.py`
  - `test_schemas_endpoints_integration.py` (optional; already covered in unit)
  - `test_search_integration.py`
  - `test_generate_answer_integration_negative.py`
- Optional tiny helper in `tests/integration/conftest.py` (e.g., snapshot path finder). No application code edits.

Functions (tests/helpers) and purposes
- tests/integration/test_ground_truths_get_and_filters_cosmos.py
  - async def test_get_item_200_and_404(): Create item; GET by dataset/bucket/id; verify 404 when missing.
  - async def test_list_filters_by_status(): Seed items with draft/approved/deleted; assert filter correctness.
- tests/integration/test_ground_truths_import_conflicts_cosmos.py
  - async def test_import_duplicate_returns_409(): Import same id twice; second returns HTTP 409.
- tests/integration/test_ground_truths_etag_errors_cosmos.py
  - async def test_update_requires_etag_412(): PUT without If-Match/body etag returns 412.
  - async def test_update_etag_mismatch_412(): PUT with wrong ETag returns 412.
- tests/integration/test_snapshot_artifacts_cosmos.py
  - async def test_snapshot_writes_artifacts_and_manifest(): Approve one; snapshot; assert files and manifest sane.
- tests/integration/test_assignments_flow_cosmos.py
  - async def test_self_serve_and_list_my(): Self-serve with limit; list mine shows only caller assignments.
  - async def test_assignment_put_approve_and_refs(): Approve with ETag; refs persisted; updatedBy set.
  - async def test_assignment_put_soft_delete_and_etag_errors(): status=deleted; missing/wrong ETag yield 412.
- tests/integration/test_tags_schema_integration.py
  - async def test_tags_schema_shape_and_ordering(): Schema groups/values sorted; depends_on mapped.
- tests/integration/test_schemas_endpoints_integration.py (optional)
  - async def test_list_and_get_openapi_components(): `/schemas` contains HTTPValidationError; GET specific works.
- tests/integration/test_search_integration.py
  - async def test_search_returns_url_title_with_mock(): Mock Azure AI Search; results normalized; `top` bounds honored.
  - async def test_search_backend_error_maps_to_502(): Mock 5xx; API responds 502.
- tests/integration/test_generate_answer_integration_negative.py
  - async def test_generate_answer_backend_error_502(): Mock Foundry 5xx; API responds 502.
- tests/integration/conftest.py (optional helper)
  - def latest_snapshot_dir() -> Path | None: Locate newest snapshot folder for artifact assertions.

Test names and behaviors to cover
- Ground truths
  - test_get_item_200_and_404 — fetch existing; missing returns 404
  - test_list_filters_by_status — approved/draft/deleted filters respected
  - test_import_duplicate_returns_409 — second import of same id conflicts
  - test_update_requires_etag_412 — missing ETag yields 412
  - test_update_etag_mismatch_412 — wrong ETag yields 412
  - test_snapshot_writes_artifacts_and_manifest — files exist; manifest valid
- Assignments
  - test_self_serve_and_list_my — caller gets own assignments only
  - test_assignment_put_approve_and_refs — approve persists; refs saved
  - test_assignment_put_soft_delete_and_etag_errors — delete and 412 paths
- Tags/Schemas
  - test_tags_schema_shape_and_ordering — stable ordering and mapping
  - test_list_and_get_openapi_components — components listed and retrievable
- Search
  - test_search_returns_url_title_with_mock — normalized results; `top` bounds
  - test_search_backend_error_maps_to_502 — backend error → 502
- Answers
  - test_generate_answer_backend_error_502 — provider error → 502

Notes
- Keep dataset names unique per test to avoid cross-test collisions.
- For snapshot checks, assert that the returned manifest/path exists under `exports/snapshots/<ts>/` and includes at least one part file when there are approved items.
- Follow repo guidance for timestamps in any test-side generated data using timezone-aware datetimes.

Out of scope
- Adding new API routes or altering current app behavior.
- Cloud credentials or live Azure calls; all external HTTP is mocked.
