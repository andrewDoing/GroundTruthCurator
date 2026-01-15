# Cosmos Emulator Test Lifecycle — Plan

## Short overview
We’ll tighten our pytest + FastAPI setup to create an isolated Cosmos DB per test, ensure deterministic teardown that drops each per‑test database, and align fixture ordering so cleanup always targets the DB actually used. We’ll also close transports/clients cleanly and keep TLS verification safe for the emulator.

## What we will implement now (only what’s needed)
- Per-test DB isolation with a unique database name derived from worker_id + uuid.
- Session-scoped CosmosClient for test utilities; function-scoped DB create/drop on teardown.
- Deterministic fixture ordering: async_client depends on the per‑test DB fixture so the app uses the correct DB.
- Replace repo-introspection cleanup with explicit delete_database(db_name) using the name chosen by the fixture.
- Close HTTPX ASGI transport and Cosmos client(s) reliably; stop swallowing exceptions in teardown (log on failure).
- Keep emulator TLS safe: verify disabled only for emulator; recommend importing the certificate locally.
- Parallel-safe naming; no locking required with pytest-xdist.

## Files to change
- tests/integration/conftest.py — add session Cosmos client fixture; add test_db fixture; rewire async_client to depend on per‑test DB; drop DB in teardown; close transport; log cleanup failures.
- tests/stress/conftest.py — mirror integration fixture changes for stress suite; ensure per‑test DB teardown.
- app/container.py — small helper to rebind repo to a provided DB name for tests (uses existing init_cosmos_repo; add optional close helper for client).
- app/main.py — ensure lifespan does not eagerly initialize Cosmos when COSMOS_TEST_MODE=true (already supported; just verify and document).
- docs/pytest-fastapi-cosmos-emulator-best-practices.md — note our concrete fixture wiring and TLS guidance (doc-only).

(No product API or domain changes; this is test/infra wiring only.)

## Function/fixture names and purposes
- tests/integration/conftest.py
  - fixture: cosmos_client() -> CosmosClient (session)
    - Create one async Cosmos client per test session for utility ops (create/drop DBs). Reused across tests for performance.
  - fixture: test_db_name(worker_id: str) -> str (function)
    - Return unique DB name like f"t_{worker_id}_{uuid4().hex[:10]}" to avoid parallel collisions.
  - fixture: configure_repo_for_test_db(test_db_name: str) -> None (function)
    - Call container.init_cosmos_repo(db_name=test_db_name) so the app/repo uses this DB for the test.
  - fixture: clear_cosmos_db(cosmos_client, test_db_name) (function, autouse)
    - Yields to test; in teardown, await cosmos_client.delete_database(test_db_name); log failures; do not swallow silently.
  - fixture: live_app() -> FastAPI (function)
    - Create app; require REPO_BACKEND=cosmos; do not init repo here (defer to configure_repo_for_test_db).
  - fixture: async_client(live_app, configure_repo_for_test_db, clear_cosmos_db)
    - Build AsyncClient with ASGITransport(app=live_app); yield; finally await transport.aclose().

- tests/stress/conftest.py
  - Duplicate the above fixture pattern to ensure stress tests also create/drop per‑test DBs deterministically.

- app/container.py
  - def close_cosmos_repo_client(self) -> None
    - Best-effort close of the repo’s underlying CosmosClient (await if needed). Used by tests if we decide to close the app-owned client too.

- app/main.py
  - Lifespan already respects COSMOS_TEST_MODE for lazy init. Keep that so the SDK binds to the test’s event loop.

## Tests (names and brief behaviors)
- tests/integration/test_cosmos_lifecycle.py
  - test_per_test_db_is_deleted: DB dropped in teardown; not listed after.
  - test_parallel_db_names_are_unique: names include worker_id+uuid; no collisions.
  - test_transport_is_closed_after_request: transport closed in teardown; lifespan exits.

- tests/stress/test_cosmos_lifecycle_stress.py
  - test_many_dbs_teardown_cleanly: N tests create N DBs; none remain.

(We’ll mark lifecycle tests with a skip if REPO_BACKEND!=cosmos.)

## Implementation notes and order of work
1) Integration fixtures
- Add cosmos_client (session) via azure.cosmos.aio.CosmosClient with settings.COSMOS_CONNECTION_VERIFY.
- Add test_db_name(worker_id) and configure_repo_for_test_db(test_db_name) calling container.init_cosmos_repo(db_name=...). Ensure async_client depends on configure_repo_for_test_db so ordering is enforced.
- Add clear_cosmos_db that deletes the DB name picked by test_db_name in teardown. Replace current repo-introspection cleanup with direct delete_database(name). Log exceptions with repr(e) for visibility.
- Ensure async_client closes ASGITransport by calling transport.aclose() after client context.

2) Stress fixtures
- Mirror the integration fixtures (copy or factor into a shared helper) and apply the same ordering and cleanup.

3) Container helper (optional)
- Add Container.close_cosmos_repo_client() to close the repo’s internal client if tests choose to explicitly close it in teardown (not required for DB deletion, but good hygiene).

4) TLS
- Keep COSMOS_CONNECTION_VERIFY=False by default for emulator via settings, but document and prefer importing the emulator cert on macOS/Linux. Do not globally disable verification outside tests.

5) CI notes
- Start emulator once per job; don’t reset between tests. Optionally run a pre-suite cleanup using scripts/delete_cosmos_emulator_dbs.py to remove strays.

## Acceptance criteria
- After running integration and stress tests locally or in CI, no stray per‑test databases remain in the emulator.
- Tests run in parallel (xdist) without database name collisions.
- No cross-event-loop errors from the Cosmos SDK; repo client binds to the test loop as before.
- Teardown errors are visible in logs; we no longer swallow exceptions silently.

## Requirements coverage
- Implement only needed functionality: per‑test DB create/drop, ordered fixtures, safe TLS, and cleanup logging — Done in plan.
- Identify files to change: listed above — Done in plan.
- No legacy fallbacks: none proposed — Done in plan.
- Functions/fixtures named with purpose: provided — Done in plan.
- Test names with behaviors: provided — Done in plan.
