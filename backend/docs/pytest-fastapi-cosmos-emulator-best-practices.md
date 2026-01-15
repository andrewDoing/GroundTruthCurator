Here’s a tight, battle-tested pattern for pytest + FastAPI when you’re using the Azure Cosmos DB emulator. It’s designed for isolation, parallelism (pytest-xdist), and fast cleanup.

⸻

What to aim for
	1.	Per-test database isolation
Create a unique DB per test (or per module) and delete the whole DB in teardown. Dropping the DB is far faster and simpler than deleting items/containers. The Python SDK exposes database-level operations directly.  ￼
	2.	Async test stack that mirrors your app
Use pytest-asyncio, FastAPI’s async testing guidance, and httpx.AsyncClient with ASGI transport.  ￼
	3.	Safe emulator TLS
Don’t disable SSL verification. Import the emulator’s certificate instead (especially with the Docker/Linux emulator).  ￼
	4.	Parallel runs without collisions
Namespace DB names by worker_id (xdist) + uuid4 so workers never step on each other.
	5.	One reset per CI job, not per test
If you need a “clean slate,” use the emulator’s Reset Data (or start fresh on CI) once before tests, not between tests.  ￼

⸻

Drop-in pytest fixtures (Python SDK v4, async app)

# conftest.py
import os
import uuid
import asyncio
import pytest
from httpx import AsyncClient
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey
from fastapi import FastAPI

# ---- App wiring (example) ----
def create_app() -> FastAPI:
    from myapp.main import app  # wherever your FastAPI app lives
    return app

COSMOS_URL = os.getenv("COSMOS_EMULATOR_URI", "https://localhost:8081")
COSMOS_KEY = os.getenv("COSMOS_EMULATOR_KEY", "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5...")  # emulator master key

@pytest.fixture(scope="session")
def event_loop():
    """pytest-asyncio: use a single loop per session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def cosmos_client():
    # One client per test session per SDK guidance
    # (client is heavy; reuse it) 
    client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
    try:
        yield client
    finally:
        await client.close()

# conftest.py (continued)
@pytest.fixture(scope="function")
async def test_database(cosmos_client, worker_id: str = "gw0"):
    """
    Function-scoped DB for perfect isolation.
    Namespaced by xdist worker_id (gw0, gw1, ...) to avoid collisions in parallel.
    """
    db_name = f"t_{worker_id}_{uuid.uuid4().hex[:10]}"
    db = await cosmos_client.create_database_if_not_exists(id=db_name)

    try:
        yield db
    finally:
        # Drop the entire database — simplest & fastest cleanup
        await cosmos_client.delete_database(db_name)

# conftest.py (continued)
@pytest.fixture(scope="function")
async def test_container(test_database):
    # Minimal example container; adjust PK and throughput as needed
    container = await test_database.create_container_if_not_exists(
        id="items",
        partition_key=PartitionKey(path="/pk"),
        offer_throughput=400
    )
    return container

# conftest.py (continued)
@pytest.fixture(scope="function")
async def async_client():
    """
    FastAPI async test client per FastAPI docs.
    """
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

Why this works well
	•	The session-scoped CosmosClient follows SDK guidance to keep a single client for performance.  ￼
	•	The function-scoped DB guarantees each test starts clean; teardown deletes the whole DB (no item scans). The SDK supports DB create/delete from the client.  ￼
	•	The FastAPI client setup mirrors the official async testing approach.  ￼

⸻

Example test

async def test_create_and_read_item(test_container, async_client):
    item = {"id": "1", "pk": "A", "name": "widget"}
    await test_container.upsert_item(item)

    # Exercise your API endpoint
    r = await async_client.get("/items/1?pk=A")
    assert r.status_code == 200
    assert r.json()["name"] == "widget"


⸻

Parallel runs (pytest-xdist)
	•	Install: pip install pytest-xdist
	•	Run: pytest -n auto
The worker_id baked into the DB name makes DBs unique per worker. No locking needed.

⸻

CI tips for the emulator
	•	Windows GitHub Actions runners have the emulator and PowerShell module available; start it via Start-CosmosDbEmulator before tests.  ￼
	•	Don’t “reset data” between tests—if you must, reset once before the suite. Locally, you can use the tray menu’s Reset Data.  ￼

⸻

TLS with the emulator (Docker/Linux & macOS)

If you’re using the Docker/Linux emulator on macOS, import the emulator certificate (don’t turn off TLS verification):

curl -k https://localhost:8081/_explorer/emulator.pem > cosmos-emulator.crt
# Import into your macOS keychain or trust store, then restart your tooling.

Microsoft’s guidance recommends importing the cert rather than disabling SSL checks.  ￼

⸻

When you don’t want to drop the DB

For data-retention scenarios inside a single DB (e.g., multi-tenant tests), you can selectively delete by partition key. Cosmos now exposes delete-all-items-by-partition-key (public preview). It runs in the background, and effects (no read/query visibility) are immediate—handy for wiping a tenant fast:

# preview API; version-gated
await test_container.delete_all_items_by_partition_key("tenantA")

Be aware it’s preview; prefer whole-DB deletes for test isolation when possible.  ￼

⸻

FastAPI + pytest checklist (emulator)
	•	One CosmosClient per session (reuse).  ￼
	•	Per-test DB (uuid + worker_id), drop DB in teardown.
	•	Async tests per FastAPI docs (pytest-asyncio, httpx.AsyncClient).  ￼
	•	Avoid item-level cleanup; prefer DB drop.
	•	For CI, start emulator once; optionally “Reset Data” once pre-suite.  ￼
	•	Import emulator TLS certificate; don’t disable SSL.  ￼

If you want, I can adapt the fixtures to your actual app wiring (where you initialize the Cosmos repo in FastAPI lifespan) and fold the DB name into your DI container so your routes automatically use the per-test DB.