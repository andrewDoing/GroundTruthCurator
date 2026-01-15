# ruff: noqa: E402
from __future__ import annotations

import base64
import inspect
import json
import sys
from uuid import uuid4
import os
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError

# Add scripts to path for cosmos_container_manager import
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from cosmos_container_manager import (
    create_cosmos_client,
    get_default_container_specs,
    initialize_containers,
)

# Ensure integration tests load committed baseline env files by default.
# This must be set before importing settings or app modules.
os.environ.setdefault(
    "GTC_ENV_FILE",
    "environments/sample.env,environments/integration-tests.env,environments/local.env",
)

from app.main import create_app
from app.container import container
from app.core.config import settings


# Use pytest-asyncio/anyio with the standard asyncio backend
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


# Note: anyio manages the event loop per test when using @pytest.mark.anyio.
# We intentionally avoid sharing long-lived async clients across tests to
# prevent cross-loop Future errors.


@pytest.fixture(scope="function")
def require_cosmos_backend():
    """Skip tests if the repo backend isn't set to Cosmos.

    This keeps integration tests honest and avoids silently using the
    in-memory backend.
    """
    if getattr(settings, "REPO_BACKEND", None) != "cosmos":
        pytest.fail("Integration tests require REPO_BACKEND=cosmos")


# Intentionally no session-scoped CosmosClient to avoid binding it to a loop
# different from the one AnyIO uses for each test.


@pytest.fixture(scope="function")
def test_db_name() -> str:
    """Return a unique database name per test, namespaced by worker.

    Does not depend on pytest-xdist. If running under xdist, uses the
    PYTEST_XDIST_WORKER environment variable (e.g., gw0); otherwise defaults
    to "gw0" for single-process runs.

    Example: t_gw0_ab12cd34ef
    """
    worker = os.getenv("PYTEST_XDIST_WORKER", "gw0")
    return f"t_{worker}_{uuid4().hex[:10]}"


@pytest.fixture(scope="function")
async def init_emulator_containers(test_db_name: str):
    """Initialize Cosmos emulator containers for the test database.

    This fixture creates all required containers with correct partition keys
    and indexing policies before the test runs. Uses indexing-policy.json as
    the single source of truth for the ground_truth container indexing policy.
    """
    endpoint = settings.COSMOS_ENDPOINT
    key = settings.COSMOS_KEY.get_secret_value() if settings.COSMOS_KEY else None

    if not endpoint or not key:
        pytest.fail("Cosmos settings not configured")

    # Build container specs using the unified manager
    container_specs = get_default_container_specs(
        gt_container=settings.COSMOS_CONTAINER_GT,
        assignments_container=settings.COSMOS_CONTAINER_ASSIGNMENTS,
        tags_container=settings.COSMOS_CONTAINER_TAGS,
    )

    # Create client and initialize containers
    client = create_cosmos_client(
        endpoint=endpoint,
        key=key,
        connection_verify=settings.COSMOS_CONNECTION_VERIFY,
    )

    try:
        results = await initialize_containers(client, test_db_name, container_specs)
    finally:
        await client.close()

    for container_name, result in results.items():
        print(f"[setup] Container '{container_name}': {result['status']}")

    yield results


@pytest.fixture(scope="function")
async def configure_repo_for_test_db(
    require_cosmos_backend,
    test_db_name: str,
    init_emulator_containers,
) -> None:
    """Point the DI container's repo to a unique per-test Cosmos DB.

    This fixture depends on init_emulator_containers (an async fixture) to ensure
    the database and containers exist before the repository is configured.
    pytest-asyncio handles the async/sync fixture interaction correctly.

    The repo itself is lazily initialized on first use, binding its aiohttp
    session to the current event loop.
    """
    # Close any previous Cosmos async client bound to a different lifecycle
    try:
        prev_repo = getattr(container, "repo", None)
        client = getattr(prev_repo, "_client", None)
        if client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                res = close()
                if inspect.isawaitable(res):
                    await res
    except Exception:
        pass
    container.init_cosmos_repo(db_name=test_db_name)


@pytest.fixture(scope="function", autouse=True)
async def clear_cosmos_db(test_db_name: str):
    """Drop the per-test database after each test.

    If the DB was never created during the test, deletion will 404 and we
    quietly ignore it.
    """
    yield
    try:
        # Use a short-lived client bound to the current test's event loop
        endpoint = settings.COSMOS_ENDPOINT
        key = settings.COSMOS_KEY.get_secret_value() if settings.COSMOS_KEY else None
        # If settings are missing, nothing to clean up; exit quietly.
        if endpoint is None or key is None:
            return
        client = CosmosClient(
            endpoint,
            credential=key,
            connection_verify=settings.COSMOS_CONNECTION_VERIFY,
        )
        try:
            await client.delete_database(test_db_name)  # type: ignore[func-returns-value]
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                cres = close()
                if inspect.isawaitable(cres):
                    await cres
    except CosmosHttpResponseError as e:  # type: ignore[misc]
        if getattr(e, "status_code", None) == 404:
            return
        # Log but do not fail the test teardown
        print(f"[teardown] Failed to delete Cosmos DB {test_db_name}: {repr(e)}")
    except Exception as e:  # pragma: no cover - safety net for unexpected SDK errors
        print(f"[teardown] Unexpected error deleting DB {test_db_name}: {repr(e)}")


@pytest.fixture(scope="function")
async def live_app(require_cosmos_backend, configure_repo_for_test_db):
    """Create the FastAPI app for a test using the Cosmos backend.

    Lifespan is managed by the test HTTP client via ASGITransport(lifespan="on").
    """
    if CosmosClient is None:
        pytest.fail("azure-cosmos SDK not available; cannot run Cosmos integration tests")

    app = create_app()
    # Manage app lifespan explicitly to ensure startup/shutdown run with tests
    try:
        from asgi_lifespan import LifespanManager  # type: ignore

        async with LifespanManager(app):
            yield app
    except Exception:
        # If asgi-lifespan isn't installed, yield the app without explicit lifespan
        # management; most routes lazily init their dependencies anyway.
        yield app


@pytest.fixture(scope="function")
async def async_client(live_app):
    """Async HTTP client against the in-process FastAPI app.

    Ensures FastAPI lifespan events run and the ASGI transport is closed on teardown.
    """
    transport = ASGITransport(app=live_app)
    # Default headers include a valid ACA Easy Auth principal for allowed domain
    payload = {
        "claims": [{"typ": "emails", "val": "tester@example.com"}, {"typ": "name", "val": "tester"}]
    }
    headers = {
        "X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(payload).encode("utf-8")).decode(
            "utf-8"
        )
    }
    client = AsyncClient(transport=transport, base_url="http://testserver", headers=headers)
    try:
        yield client
    finally:
        try:
            await client.aclose()
        finally:
            try:
                await transport.aclose()
            except Exception:
                pass


@pytest.fixture(scope="session", autouse=True)
def enable_cosmos_test_mode():
    """Enable Cosmos test mode for integration tests.

    Prevents app lifespan from re-initializing repos and seeding default tags.
    """
    original = settings.COSMOS_TEST_MODE
    settings.COSMOS_TEST_MODE = True
    yield
    settings.COSMOS_TEST_MODE = original


@pytest.fixture(scope="session", autouse=True)
def configure_ezauth_for_tests():
    """Baseline Easy Auth configuration for the test session."""
    try:
        settings.EZAUTH_ENABLED = True
        settings.EZAUTH_ALLOW_ANONYMOUS_PATHS = "/healthz"
        settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = "example.com"
        settings.EZAUTH_ALLOWED_OBJECT_IDS = None
    except Exception:
        pass


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply default skips for integration tests that require external services."""
    chat_configured = bool(
        settings.AZURE_AI_PROJECT_ENDPOINT and settings.AZURE_AI_AGENT_ID and settings.CHAT_ENABLED
    )
    search_configured = bool(settings.AZ_SEARCH_ENDPOINT and settings.AZ_SEARCH_INDEX)

    for item in items:
        if item.get_closest_marker("requires_chat") and not chat_configured:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "Azure AI Foundry agent not configured; set "
                        "GTC_AZURE_AI_PROJECT_ENDPOINT, GTC_AZURE_AI_AGENT_ID, "
                        "and GTC_CHAT_ENABLED=true"
                    )
                )
            )
        if item.get_closest_marker("requires_search") and not search_configured:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "Azure AI Search not configured; set "
                        "GTC_AZ_SEARCH_ENDPOINT and GTC_AZ_SEARCH_INDEX"
                    )
                )
            )


@pytest.fixture(autouse=True)
def reset_ezauth_between_tests():
    """Reset Easy Auth allow lists before each test to avoid leakage from tests that mutate settings."""
    try:
        settings.EZAUTH_ENABLED = True
        settings.EZAUTH_ALLOW_ANONYMOUS_PATHS = "/healthz"
        settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = "example.com"
        settings.EZAUTH_ALLOWED_OBJECT_IDS = None
    except Exception:
        pass


@pytest.fixture(scope="function")
def user_headers() -> dict[str, str]:
    """Per-test headers for requests with a valid Easy Auth principal.

    Useful for tests that construct their own AsyncClient without default headers.
    """
    payload = {
        "claims": [{"typ": "emails", "val": "tester@example.com"}, {"typ": "name", "val": "tester"}]
    }
    b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return {"X-MS-CLIENT-PRINCIPAL": b64}


@pytest.fixture(scope="function", autouse=True)
async def close_repo_client_after_test():
    """Ensure repo's underlying Cosmos client is closed after each test.

    Prevents leftover tasks or event loop bound transports from leaking across tests.
    """
    yield
    try:
        prev_repo = getattr(container, "repo", None)
        client = getattr(prev_repo, "_client", None)
        if client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                res = close()
                if inspect.isawaitable(res):
                    await res
    except Exception:
        # Best-effort teardown
        pass


@pytest.fixture(scope="function", autouse=True)
async def close_tags_repo_client_after_test():
    """Ensure tags repo's underlying Cosmos client is closed after each test.

    Avoids cross-loop usage if a subsequent test initializes tags on a new loop.
    """
    yield
    try:
        tags_repo = getattr(container, "tags_repo", None)
        client = getattr(tags_repo, "_client", None)
        if client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                res = close()
                if inspect.isawaitable(res):
                    await res
    except Exception:
        # Best-effort teardown
        pass


@pytest.fixture(autouse=True)
def reset_sampling_allocation_env(monkeypatch: pytest.MonkeyPatch):
    """Ensure sampling allocation env var is clean at test start.

    Individual tests may override with monkeypatch.setenv.
    """
    monkeypatch.delenv("GTC_SAMPLING_ALLOCATION", raising=False)


@pytest.fixture(autouse=True)
async def seed_default_tags(
    async_client: AsyncClient, user_headers: dict[str, str], request: pytest.FixtureRequest
):
    if request.node.get_closest_marker("no_seed_tags") or "no_seed_tags" in request.node.keywords:
        return  # Skip seeding for this test

    default_tags = {
        "tags": [
            "source:synthetic",
            "source:sme",
            "split:train",
            "split:validation",
            "split:test",
            "answerability:answerable",
            "topic:general",
            "question_length:short",
            "retrieval_behavior:single",
        ]
    }
    response = await async_client.post("/v1/tags", json=default_tags, headers=user_headers)
    assert response.status_code == 200
