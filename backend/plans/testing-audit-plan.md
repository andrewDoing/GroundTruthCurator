# Testing audit and consolidation plan

## Overview
We will audit and consolidate tests to reduce duplication, clarify intent, and enforce boundaries: unit tests focus on pure logic with fakes/mocks, integration tests validate app + datastore behavior. We’ll keep it simple—merge related specs, delete duplicates, centralize fixtures/utilities, and mark any truly-live tests. Stress tests are out-of-scope for now.

## What we will implement right now (scope)
- Consolidate overlapping integration tests by domain (ground truths, assignments, tags/schemas, curation, search, snapshots).
- Ensure unit tests don’t touch Cosmos or external services; replace with fakes/mocks.
- Delete duplicate or redundant cases where the same behavior is covered in both unit and integration (keep one, prefer unit for logic, integration for E2E happy-paths + key edge cases).
- Centralize fixtures/utilities shared across tests to cut repetition.
- Quarantine any “live” external calls behind an explicit marker and/or folder.

## Ground rules
- Unit tests: fast, deterministic, no network/filesystem/containers/datastore; use fakes/mocks; assert business logic and serialization/validation.
- Integration tests: run against Cosmos emulator and full app; cover routing, wiring, permissions, and datastore behaviors (ETags, filters, imports, artifacts). Avoid re-testing algorithms fully covered in unit tests.
- Stress tests: ignore for now.

## Pytest markers and enforcement
- Markers to use and register in `pytest.ini`:
  - `@pytest.mark.unit` — pure logic, no I/O or network; fastest lane.
  - `@pytest.mark.integration` — hits FastAPI app and Cosmos emulator.
  - `@pytest.mark.cosmos` — subset of integration that specifically exercises Cosmos behaviors (e.g., ETags, queries).
  - `@pytest.mark.live` — external services; skipped by default in CI, opt-in locally/with flag.
  - `@pytest.mark.container` — container/build smoke tests; separate CI lane.
- Enforcement suggestions:
  - Deny network in unit jobs (e.g., pytest-socket) and use `tmp_path` for any temp files.
  - Default-skip `live` in CI (`-m "not live"`).
  - Prefer parallelizing unit (xdist) and keep integration serial or per-worker isolated DB.

## Inventory by theme (current files)
- Assignments
  - Unit: `tests/unit/test_sampling_allocation.py`, `tests/unit/test_assignments_skip_persist.py`
  - Integration: `tests/integration/test_assignments_cosmos.py`, `tests/integration/test_assignments_flow_cosmos.py`, `tests/integration/test_bucket_assignment_cosmos.py`, `tests/integration/test_sample_unassigned_allocation.py`
- Ground Truths
  - Integration: `tests/integration/test_ground_truths_cosmos.py`, `tests/integration/test_ground_truths_delete_restore_etag_cosmos.py`, `tests/integration/test_ground_truths_etag_errors_cosmos.py`, `tests/integration/test_ground_truths_get_and_filters_cosmos.py`, `tests/integration/test_ground_truths_import_conflicts_cosmos.py`, `tests/integration/test_etag_and_refs_cosmos.py`
- Tags and Schemas
  - Unit: `tests/unit/test_tag_registry_service.py`, `tests/unit/test_tagging_service.py`, `tests/unit/test_groundtruthitem_tags_validation.py`
  - Integration: `tests/integration/test_tags_and_schemas_integration.py`, `tests/integration/test_tags_registry_api.py`, `tests/integration/test_tags_schema_api.py`
- LLM / Generate Answer / API
  - Unit: `tests/unit/test_llm_service_prompt.py`, `tests/unit/test_azure_foundry_llm_adapter.py`, `tests/unit/test_generate_answer_endpoint.py`
  - Integration: `tests/integration/test_generate_answer_integration_negative.py`, `tests/integration/test_llm_foundry_live.py`
- Curation / Datasets / Search / Snapshots / Frontend
  - Unit: `tests/unit/test_curation_models.py`, `tests/unit/test_openapi.py`, `tests/unit/test_frontend_serving.py`
  - Integration: `tests/integration/test_datasets_router_curation.py`, `tests/integration/test_search_integration.py`, `tests/integration/test_snapshot_artifacts_cosmos.py`, `tests/integration/test_container_smoke.py`

## Proposed consolidation and deletions (keep it simple)
- Assignments
  - Merge integration files into `tests/integration/assignments/test_assignments_cosmos.py`:
    - Move content from `test_assignments_cosmos.py`, `test_assignments_flow_cosmos.py`, `test_bucket_assignment_cosmos.py`.
    - Keep a single test for “sample unassigned allocation” at integration (golden path) and delete `tests/integration/test_sample_unassigned_allocation.py` if it repeats unit logic.
  - Keep unit `test_sampling_allocation.py` as the source of truth for the allocation algorithm. If `test_assignments_skip_persist.py` hits datastore or duplicative flow logic, refactor to mock repository or merge into `test_sampling_allocation.py` and delete duplicates.
- Ground Truths
  - Merge to a package `tests/integration/ground_truths/` with files:
    - `test_crud_and_filters.py` (merge from `test_ground_truths_cosmos.py`, `test_ground_truths_get_and_filters_cosmos.py`).
    - `test_etag_and_concurrency.py` (merge from `test_ground_truths_delete_restore_etag_cosmos.py`, `test_ground_truths_etag_errors_cosmos.py`, and relevant parts of `test_etag_and_refs_cosmos.py`).
    - `test_import_and_conflicts.py` (from `test_ground_truths_import_conflicts_cosmos.py`).
  - Delete any duplicated cases appearing in multiple source files (e.g., repeated ETag precondition failures already covered in the new `test_etag_and_concurrency.py`).
- Tags and Schemas
  - Merge integration API tests into `tests/integration/tags/test_tags_api.py` covering registry and schema endpoints; remove `test_tags_registry_api.py` and `test_tags_schema_api.py` after merging into one consolidated suite (grouped by describe/contexts).
  - Keep `test_tags_and_schemas_integration.py` only if it covers a broader end-to-end with schema registration + application. Otherwise fold its unique cases into `test_tags_api.py` and delete.
  - Keep unit tests focused on service-layer behavior (`test_tag_registry_service.py`, `test_tagging_service.py`, validation); ensure no datastore usage.
- LLM / Generate Answer
  - Keep unit: `test_llm_service_prompt.py` and `test_azure_foundry_llm_adapter.py` with pure fakes; `test_generate_answer_endpoint.py` should use an app with mocked LLM + repo.
  - Integration: keep `test_generate_answer_integration_negative.py` if it validates request/response handling with real app + datastore; do not duplicate prompt logic (unit covers it).
  - Quarantine `test_llm_foundry_live.py` under `tests/integration/live/` and add marker `@pytest.mark.live` so it runs only when explicitly enabled; otherwise skip by default. Delete any duplicated negative/timeout cases if already covered by unit or non-live integration.
- Curation / Datasets / Search / Snapshots / Frontend
  - Keep `test_datasets_router_curation.py`, `test_search_integration.py`, `test_snapshot_artifacts_cosmos.py` as integration suites.
  - Prefer `tests/integration/test_container_smoke.py` for frontend asset serving; trim or remove `tests/unit/test_frontend_serving.py` if it’s asserting the same HTTP behavior.
  - Keep `tests/unit/test_openapi.py` (pure logic/schema), and `tests/unit/test_curation_models.py` (domain models only).

## Files to change (create/move/merge/delete)
- Create directories for grouping:
  - `tests/integration/assignments/`
  - `tests/integration/ground_truths/`
  - `tests/integration/tags/`
  - `tests/integration/live/` (for explicit external/live tests)
- Merge/move:
  - Move and merge assignments specs into `tests/integration/assignments/test_assignments_cosmos.py`.
  - Move and merge ground truths specs into:
    - `tests/integration/ground_truths/test_crud_and_filters.py`
    - `tests/integration/ground_truths/test_etag_and_concurrency.py`
    - `tests/integration/ground_truths/test_import_and_conflicts.py`
  - Merge tags registry + schema integration into `tests/integration/tags/test_tags_api.py`.
  - Move `tests/integration/test_llm_foundry_live.py` to `tests/integration/live/test_llm_foundry_live.py` and mark.
- Delete duplicates after merging:
  - `tests/integration/test_sample_unassigned_allocation.py` (if only repeating algorithm already in unit).
  - `tests/unit/test_frontend_serving.py` (if container smoke covers the same routing behavior).
  - Any former integration files replaced by the consolidated modules above.
- Update fixtures:
  - Consolidate duplicated fixtures into `tests/conftest.py` and the per-scope `tests/unit/conftest.py` and `tests/integration/conftest.py`. Prefer one place per scope.
 - Add `tests/README.md` documenting markers, how to run unit vs integration vs live/container suites, and local Cosmos emulator tips.
 - Update `pytest.ini` to register markers, add default options (e.g., `addopts = --durations=10`), and default-skip `live`.

## Minimal helper functions to add (keep it simple)
- make_app_with_fakes()
  - Build FastAPI app with in-memory fake repos and fake LLM; for unit tests that need routing.
- fake_ground_truth_repo()
  - In-memory repository simulating basic CRUD without ETag/network; used in unit tests only.
- seed_cosmos_dataset(client)
  - Utility for integration tests to load baseline dataset into Cosmos emulator via API; keeps integration suites DRY.
- assert_etag_precondition_failed(resp)
  - Assert pattern for 412/etag conflicts to avoid repeated status/message assertions.
- create_tag_schema(client, schema)
  - Small helper to register tag schema via API in integration tests.

## Target unit test names (and behaviors)
- test_sampling_allocation_distributes_by_quota
  - Allocation splits by quotas proportionally and deterministically.
- test_sampling_allocation_skips_persist_when_configured
  - No datastore writes when skip-persist flag set.
- test_llm_prompt_template_renders_expected_placeholders
  - Prompt variables inserted; no external call.
- test_azure_foundry_adapter_builds_chat_messages
  - Adapts internal prompt to Foundry message format.
- test_generate_answer_endpoint_with_fake_llm_and_repo
  - Endpoint returns answer using fakes; no I/O.
- test_tag_registry_service_registers_and_lists_schemas
  - Registers schema version and can list versions.
- test_tagging_service_applies_schema_and_validates_values
  - Matches types/enums; rejects invalid tags.
- test_openapi_contains_expected_routes_and_models
  - OpenAPI has critical routes and models.
- test_ground_truth_tag_validation_rules
  - Domain validators correctly enforce tag shape.

## Target integration test names (and behaviors)
- test_assignments_flow_end_to_end_cosmos
  - Assign, persist, retrieve; consistent across calls.
- test_bucket_assignment_balances_load_across_buckets
  - Bucketing assigns fairly; persists choices.
- test_ground_truths_create_get_list_filter
  - CRUD and server-side filters return expected results.
- test_ground_truths_delete_restore_with_etag_checks
  - Delete/restore respects ETags and state changes.
- test_ground_truths_etag_conflict_on_stale_update
  - Update with stale ETag yields 412 precondition failed.
- test_import_conflicts_report_and_resolution_paths
  - Import reports conflicts and supports resolution flow.
- test_tags_api_register_schema_then_apply_to_item
  - Register schema; apply tags; retrieve and verify.
- test_search_returns_expected_items_with_filters
  - Search endpoint returns filtered, correctly ordered results.
- test_snapshot_artifacts_written_and_listed
  - Snapshot produces artifacts; can download/list them.
- test_container_serves_frontend_assets
  - Container serves index and deep-link routes.
- test_generate_answer_negative_paths_cosmos
  - Input validation and error handling against datastore.
- test_llm_foundry_live_smoke (marked live)
  - Only runs with explicit flag; hits external Foundry.

## Step-by-step plan (SIMPLE)
1) Create target subdirectories for integration suites (assignments, ground_truths, tags, live).
2) Move and merge tests by theme; keep filenames and tests descriptive. Add the new consolidated tests alongside the existing ones and ensure BOTH old and new suites pass in CI for a transition period.
3) Centralize fixtures and small helpers; ensure unit fixtures use only fakes/in-memory state.
4) Quarantine “live” tests and add `pytest.mark.live`; default to skip in CI.
5) Run unit tests and integration tests locally; confirm parity and remove redundant cases that unit already covers.
6) Once parity is confirmed, remove the old files replaced by consolidated suites in the same PR. Commit with a conventional message and open a focused PR explaining reductions and listing old->new mappings.

## Acceptance checks
- Unit tests do not import or initialize Cosmos clients; they pass without emulator.
- Integration tests pass against emulator; no algorithm duplication versus unit.
- No test files remain with clear overlap after merges; naming is consistent by theme.
- CI runtime decreases or stays flat; flakiness reduced for non-live suites.

## Notes
- If some integration tests exercise the same decision logic as unit tests, keep a single “golden path” case at integration and delete the rest to avoid brittleness.
- Keep stress tests as-is (ignored here) and revisit later for load/scale scenarios.