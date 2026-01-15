# Plan: Remove in-memory repo and migrate tests to Cosmos emulator

## Overview
We will retire `InMemoryGroundTruthRepo` and make Cosmos the only datastore. Any tests that depend on the in-memory repo will be moved to integration tests and run against the Cosmos DB Emulator. We will keep fast unit tests by focusing them on pure logic (domain validation, key/id builders, mapping/DTOs, query composers, policies, authZ, ETag helpers, small utilities) and by using simple test doubles/mocks rather than a real repository.

We will implement only what’s needed to: (1) drop memory backend, (2) keep API behavior intact on Cosmos, (3) preserve meaningful, fast unit coverage without hitting the datastore.

## Scope and non‑goals
- In scope: remove code paths and test fixtures that assume an in-memory repo; move/convert memory-dependent tests to integration tests (Cosmos emulator); refactor any in-memory special cases (e.g., SnapshotService) to work with Cosmos; update docs and container wiring accordingly.
- Not in scope: adding nonessential features, alternate “legacy fallback” backends, or broader refactors unrelated to memory repo removal.

## Current state (summary)
- DI/container (`app/container.py`) selects backend based on `settings.REPO_BACKEND` and falls back to memory on errors; heavy references to `InMemoryGroundTruthRepo`.
- In-memory implementation: `app/adapters/repos/memory_repo.py`.
- Cosmos implementation: `app/adapters/repos/cosmos_repo.py` (async SDK, MultiHash PK).
- API has comments and occasional branches to support both backends.
- SnapshotService has a memory-optimized path using `hasattr(self.repo, "items")`.
- Unit tests and fixtures import/use in-memory repo, e.g. `tests/unit/conftest.py`, `tests/unit/test_memory_repo_curation_docs.py`, `tests/unit/test_curation_service.py`.

## Phased plan (small, verifiable PRs)
1) Preparation: split tests and fixtures
- Add/confirm a dedicated integration test fixture that instantiates `CosmosGroundTruthRepo` using `environments/integration-tests.env` and connects to the Cosmos emulator. Mark such tests and ensure the CI/dev flow can start emulator or skip with a clear message.
- Update unit test fixture to stop importing or constructing any repo; provide helpers to stub/mocks services’ repo dependencies per test where needed.
- Identify tests that truly need persistence (repo behavior) and mark/move them to `tests/integration/`.

2) Normalize repo usage in services/API and remove in-memory special-cases
- Replace any in-memory-only branches or assumptions with Cosmos-compatible logic. Remove direct access to `repo.items`.
- SnapshotService: replace memory-optimized code by using repo methods to fetch approved items.
- Ensure the repository interface used by services is consistent with Cosmos (dataset + bucket pk expectations), and fix any mismatches that came from supporting both backends.

3) Switch DI to Cosmos-only and delete memory repo
- Container: remove import and fallback to memory. If Cosmos settings are missing or invalid, fail fast with a clear error. No silent fallback.
- Remove `app/adapters/repos/memory_repo.py` and all references.
- Update docs to reflect Cosmos-only backend and how to run emulator for integration tests.

4) Clean up and harden tests
- Ensure unit tests are green without datastore; integration tests green with emulator. Document how to run both locally and in CI.

## Files to change (minimal necessary)
- `app/container.py`: remove memory fallback and InMemory import; require Cosmos configuration; improve log/error if missing.
- `app/adapters/repos/cosmos_repo.py`: ensure all methods used by services/API exist and adhere to the contract; small touch-ups only if mismatches exist.
- `app/adapters/repos/base.py`: update/confirm the protocol for consistency with Cosmos usage; remove any signatures that existed solely for the in-memory repo.
- `app/services/snapshot_service.py`: remove `hasattr(self.repo, "items")` optimization; use repo queries to obtain approved items.
- `app/api/v1/*` (e.g., `ground_truths.py`): remove comments/branches for in-memory; rely on Cosmos semantics consistently (e.g., `get_ground_truth(dataset, bucket, id)` or the normalized API we define below).
- `tests/unit/conftest.py`: stop importing InMemoryGroundTruthRepo; provide app/service fixtures without a datastore; add stubbing helper(s) for repo-dependent code paths per-test.
- `tests/unit/test_*`: move datastore-dependent tests to `tests/integration/`; update remaining unit tests to only cover pure logic.
- `tests/integration/**`: ensure these use the Cosmos emulator fixture and environment variables from `environments/integration-tests.env`.
- `README.md`, `CODEBASE.md`, `docs/*`: remove in-memory references; add emulator instructions.
 - `tests/integration/contract/test_ground_truth_repo_contract.py`: add the contract tests described above.
 - `tests/integration/conftest.py`: add the `ensure_cosmos_available` and `cosmos_repo_factory` fixtures.
 - `pytest.ini`: declare the `cosmos` marker and set asyncio mode.

## Function-level changes (names and purpose)
- `app/container.Container.__init__`
  - Purpose: Construct the only supported repo (Cosmos) from `settings`; remove try/fallback to memory. If misconfigured, raise a configuration error early.
- `app/adapters/repos/base.GroundTruthRepo` (Protocol)
  - Purpose: Align method signatures with Cosmos usage. Ensure parity for: import_bulk, list_by_dataset, get_ground_truth(dataset, bucket, id), get_by_id, upsert (ETag), soft_delete(dataset, bucket, id), delete_dataset(dataset), stats, assignment methods, curation docs methods.
- `app/services/snapshot_service.SnapshotService.export_json`
  - Purpose: Query approved items via repo methods (e.g., list_by_dataset + filter, or add a repo helper if needed) instead of peeking into memory store.
- `app/api/v1/ground_truths.* handlers`
  - Purpose: Remove in-memory compatibility branches; call normalized repo methods. Keep existing API contracts (ETag behavior, status codes).
- `tests/unit/conftest.live_app` (or equivalent app fixture)
  - Purpose: Create app without forcing a real repo. Provide helper to inject mocks/stubs for repo where needed.
- `tests/integration/conftest` (Cosmos fixture)
  - Purpose: Build `CosmosGroundTruthRepo` from test env vars; create containers if missing (emulator), clean them between tests, and expose an async client.

## Tests to move/replace
- Move to integration (Cosmos emulator):
  - `tests/unit/test_memory_repo_curation_docs.py` → `tests/integration/test_curation_docs_cosmos.py`
    - Behavior: create/update/get curation docs with ETag checks; pk is [datasetName, 0].
  - `tests/unit/test_curation_service.py` (if constructing InMemory directly)
    - Behavior: end-to-end curation route or service changes that truly persist; migrate to integration or rewrite to stub repo in unit tests.
  - Any tests that rely on `container.repo = InMemoryGroundTruthRepo()` or inspect `.items`.

- Keep as unit tests (no datastore):
  - Domain rules & validation
  - Key/ID/PK derivation
  - DTO ↔ domain mapping
  - Query composition helpers
  - Retry/backoff policy selection and error classification
  - AuthZ checks
  - ETag helpers
  - Small utilities

## New/updated unit tests (examples)
- `tests/unit/test_domain_validation.py::test_missing_required_fields_raises`
  - Validate required fields, type and enum constraints.
- `tests/unit/test_partition_keys.py::test_pk_builder_dataset_bucket_zero`
  - Hierarchical PK builder handles bucket=0 consistently.
- `tests/unit/test_id_format.py::test_id_format_uuid_like_or_slugged`
  - ID format builder enforces expected patterns.
- `tests/unit/test_dto_mapping.py::test_camel_to_snake_aliases`
  - Pydantic aliases preserved across model dump/load.
- `tests/unit/test_query_helpers.py::test_continuation_token_round_trip`
  - Query helper encodes/decodes continuation tokens correctly.
- `tests/unit/test_retry_policy.py::test_transient_errors_classified_for_retry`
  - Classify transient vs fatal, pick backoff policy.
- `tests/unit/test_authz.py::test_reader_can_only_access_org_x`
  - AuthZ predicate denies cross-org access.
- `tests/unit/test_etag_utils.py::test_if_match_header_extraction`
  - Extract/validate If-Match header semantics.
- `tests/unit/test_utils.py::test_config_parsing_defaults`
  - Config defaults/overrides parsed without side effects.

(Each of the above should be 5–10 lines of focused assertions and not create any real repo.)

## New/updated integration tests (examples)
- `tests/integration/test_repo_import_bulk.py::test_import_bulk_creates_documents`
  - Create-only import; duplicates conflict appropriately.
- `tests/integration/test_repo_assignments.py::test_list_and_assign_unassigned`
  - List/sample unassigned, assign atomically, check assignments container.
- `tests/integration/test_repo_soft_delete.py::test_soft_delete_marks_deleted`
  - Soft delete sets status=deleted, not hard delete.
- `tests/integration/test_repo_stats.py::test_stats_counts_by_status`
  - Stats correctly counts draft/approved/deleted.
- `tests/integration/test_curation_docs.py::test_upsert_curation_etag_conflict_412`
  - ETag mismatch surfaces as 412-equivalent ValueError.
- `tests/integration/test_api_endpoints.py::test_end_to_end_put_get`
  - API PUT then GET uses Cosmos repo; headers/ETags correct.

## Implementation details we’ll align (Cosmos-only)
- ETag and concurrency: services and API continue to treat repo `ValueError("etag_mismatch")` as 412; Cosmos calls use `match_condition=IfNotModified`.
- Partition key behavior: datasetName + bucket (bucket=0 for curation docs). Provide helpers for building PK arrays for read/patch/delete.
- Snapshot export: replace memory shortcut with a repo-based enumeration over only approved items. If needed, add a narrow repo method to enumerate approved items efficiently.
- Timestamps: when updating timestamps in code, use `datetime.now(timezone.utc)` per repo guidance.

## Repository contract tests (spec + skeleton)
We will formalize the repo behavior with a small “contract test” suite running against the Cosmos emulator. This locks in method semantics, error mapping, partition-key expectations, and pagination/ETag behavior.

Contract scope (musts):
- Upsert and get round-trip with ETag return
- Conditional update with If-Match → ETag mismatch surfaces as 412-equivalent domain error (e.g., `ValueError("etag_mismatch")`)
- List by dataset with continuation tokens: deterministic page size; last page and empty dataset
- Soft delete visibility: deleted items excluded by default; optional include-deleted path behaves consistently if supported
- Stats counts by status (draft/approved/deleted)
- Curation docs CRUD with ETag and PK=[dataset, 0]
- Assignment atomicity within a partition key (if applicable): list unassigned → assign → verify assigned

Minimal test harness skeleton (illustrative):

```python
# tests/integration/contract/test_ground_truth_repo_contract.py
import uuid
import pytest
import pytest_asyncio

COSMOS_MARK = pytest.mark.cosmos

def _unique_dataset(prefix: str = "gtc_contract") -> str:
  return f"{prefix}_{uuid.uuid4().hex[:8]}"

@pytest_asyncio.fixture
async def repo(cosmos_repo_factory):
  dataset = _unique_dataset()
  repo = await cosmos_repo_factory(dataset)
  try:
    yield repo
  finally:
    await repo.delete_dataset(dataset)

@COSMOS_MARK
@pytest.mark.asyncio
async def test_upsert_and_get_round_trip(repo):
  item = {"id": "a1", "dataset": repo.dataset, "bucket": 0, "status": "draft"}
  saved = await repo.upsert(item, match_etag=None)
  assert saved["id"] == "a1" and "etag" in saved
  fetched = await repo.get_by_id(item["dataset"], item["bucket"], item["id"])
  assert fetched["etag"] == saved["etag"]

@COSMOS_MARK
@pytest.mark.asyncio
async def test_upsert_with_etag_mismatch_raises(repo):
  item = {"id": "a2", "dataset": repo.dataset, "bucket": 0, "status": "draft"}
  _ = await repo.upsert(item, match_etag=None)
  with pytest.raises(ValueError):
    await repo.upsert({**item, "status": "approved"}, match_etag="wrong-etag")

@COSMOS_MARK
@pytest.mark.asyncio
async def test_list_pagination(repo):
  for i in range(0, 7):
    await repo.upsert({"id": f"p{i}", "dataset": repo.dataset, "bucket": 0, "status": "draft"}, match_etag=None)
  items, token = await repo.list_by_dataset(repo.dataset, bucket=0, limit=3, continuation_token=None)
  assert len(items) == 3 and token is not None
  items2, token2 = await repo.list_by_dataset(repo.dataset, bucket=0, limit=3, continuation_token=token)
  assert len(items2) in (3, 4)

@COSMOS_MARK
@pytest.mark.asyncio
async def test_soft_delete_excludes_from_default_list(repo):
  item = await repo.upsert({"id": "del1", "dataset": repo.dataset, "bucket": 0, "status": "draft"}, match_etag=None)
  await repo.soft_delete(item["dataset"], item["bucket"], item["id"]) 
  items, _ = await repo.list_by_dataset(repo.dataset, bucket=0, limit=100, continuation_token=None)
  assert all(x["id"] != item["id"] for x in items)

@COSMOS_MARK
@pytest.mark.asyncio
async def test_curation_docs_etag_conflict(repo):
  doc_id = "cur1"
  _ = await repo.upsert_curation_doc(repo.dataset, doc_id, content={"v": 1}, match_etag=None)
  with pytest.raises(ValueError):
    await repo.upsert_curation_doc(repo.dataset, doc_id, content={"v": 2}, match_etag="bogus")
```

Guidance:
- Keep each test <50 lines and self-contained.
- Use unique datasets per test to avoid cross-test coupling; avoid global cleanups.
- Assert domain-level behavior only. Do not import Cosmos SDK types in tests.
- Prefer strict assertions on error types/messages for ETag and Not Found paths.

Deliverable: a green contract suite on the emulator gives us confidence to delete the in-memory repo without semantic drift.

## Integration test infra: pytest marker and Cosmos skip fixture
Make emulator-dependent tests explicit and skippable when the emulator isn’t available.

Markers and config:
- Add a `cosmos` marker for all emulator tests.
- In `pytest.ini`, declare the marker and set asyncio mode.

Example entries:

```ini
# pytest.ini
[pytest]
markers =
  cosmos: tests that require Cosmos DB Emulator
asyncio_mode = auto
```

Skip + factory fixtures outline:

```python
# tests/integration/conftest.py
import os
import socket
import contextlib
import pytest
import pytest_asyncio

EMULATOR_URL = os.getenv("COSMOS_EMULATOR_ENDPOINT")  # e.g., https://localhost:8081/

def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
  with contextlib.closing(socket.socket()) as s:
    s.settimeout(timeout)
    try:
      s.connect((host, port))
      return True
    except OSError:
      return False

@pytest.fixture(scope="session", autouse=False)
def ensure_cosmos_available():
  if os.getenv("GTC_SKIP_COSMOS_TESTS") == "1":
    pytest.skip("GTC_SKIP_COSMOS_TESTS=1 set; skipping Cosmos tests")
  if not EMULATOR_URL:
    pytest.skip("COSMOS_EMULATOR_ENDPOINT not set; skipping Cosmos tests")
  host = "localhost" if "localhost" in (EMULATOR_URL or "") else "127.0.0.1"
  port = 8081
  if not _port_open(host, port):
    pytest.skip(f"Cosmos emulator not reachable on {host}:{port}")

@pytest_asyncio.fixture
async def cosmos_repo_factory(ensure_cosmos_available):
  from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo
  from app.core.config import Settings
  async def _make(dataset: str):
    settings = Settings(_env_file=os.getenv("GTC_ENV_FILE", "environments/integration-tests.env"))
    repo = CosmosGroundTruthRepo.from_settings(settings, dataset=dataset)
    await repo.ensure_containers()
    return repo
  yield _make
```

Usage:
- Mark emulator tests with `@pytest.mark.cosmos` and depend on `cosmos_repo_factory` or `repo` fixture in the contract suite.
- Running tests:
  - Unit only: `pytest -q -m "not cosmos"`
  - Integration only: `pytest -q -m cosmos`

## Risks and mitigations
- Emulator availability: integration tests require emulator. Mitigate with skip markers when not available and clear setup docs; CI job to start emulator.
- Test flakiness: Cosmos queries with random sampling must be deterministic in tests; limit randomness or assert invariants not specific sample sets.
- Interface mismatches: ensure `GroundTruthRepo` protocol matches Cosmos implementation; fix callers accordingly.

## Rollout and verification
- PR1: Test split + fixtures (no code deletion yet). Unit tests stop importing memory; moved tests pass against emulator locally.
- PR2: Remove in-memory special-cases in services/API; SnapshotService refactor; all tests green.
- PR3: DI switch to Cosmos-only; delete memory repo; docs update.
- CI quality gates: build, lint/typecheck, unit tests (fast), integration tests (emulator). Report PASS/FAIL per stage.

## Acceptance criteria
- No source references to `InMemoryGroundTruthRepo` remain; file deleted.
- Unit tests run and pass without Cosmos; they do not import or rely on a repo.
- Integration tests pass against emulator, covering repo-dependent behavior.
- SnapshotService exports approved items without peeking into memory store state.
- README/CODEBASE/docs reflect Cosmos-only backend and how to run emulator.
 - Repository contract tests pass on the Cosmos emulator (pagination, ETag, soft delete, stats, curation docs, assignments).
 - A `cosmos` pytest marker exists; emulator-dependent tests are skippable with a clear message when the emulator is unavailable.

## Appendix: checklist of impacted tests to audit
- `tests/unit/conftest.py` — remove InMemory import/usage; provide mocks/stubs helper.
- `tests/unit/test_memory_repo_curation_docs.py` — move to integration; rename for Cosmos.
- `tests/unit/test_curation_service.py` — if persisting, move; otherwise stub repo and remain unit.
- `tests/unit/test_datasets_router_curation.py` — if hitting persistence, move; if only mapping/validation, keep as unit with stubs.
- Any tests referencing `.items` or `_curation_docs` — move to integration or rewrite.
