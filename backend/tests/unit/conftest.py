import asyncio
import pytest

from httpx import AsyncClient, ASGITransport

from app.core.config import settings


from app.container import container
from app.services.assignment_service import AssignmentService
from app.services.snapshot_service import SnapshotService
from app.services.search_service import SearchService
from app.services.curation_service import CurationService
from app.services.tag_registry_service import TagRegistryService
from app.services.chat_service import ChatService


# Use pytest-asyncio "auto mode"/anyio; legacy markers in tests use anyio/anyio_backend
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def configure_unit_test_settings():
    """Configure settings for unit tests before app creation.

    This session-scoped autouse fixture ensures auth and other settings are
    properly configured before the live_app fixture creates the FastAPI app.
    This runs for EVERY test session, ensuring unit tests work even if run
    after integration tests that may have modified settings.
    """
    # Save original values
    orig_ezauth = settings.EZAUTH_ENABLED
    orig_auth_mode = settings.AUTH_MODE
    orig_chat_enabled = settings.CHAT_ENABLED
    orig_store_steps = settings.STORE_AGENT_STEPS
    orig_anon_paths = settings.EZAUTH_ALLOW_ANONYMOUS_PATHS
    orig_allowed_domains = settings.EZAUTH_ALLOWED_EMAIL_DOMAINS
    orig_allowed_object_ids = settings.EZAUTH_ALLOWED_OBJECT_IDS

    # Set unit test defaults - disable Easy Auth for unit tests
    settings.EZAUTH_ENABLED = False
    settings.AUTH_MODE = "dev"
    settings.EZAUTH_ALLOW_ANONYMOUS_PATHS = "/healthz"
    settings.CHAT_ENABLED = True
    settings.STORE_AGENT_STEPS = False
    settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = None
    settings.EZAUTH_ALLOWED_OBJECT_IDS = None

    yield

    # Restore on session teardown
    settings.EZAUTH_ENABLED = orig_ezauth
    settings.AUTH_MODE = orig_auth_mode
    settings.CHAT_ENABLED = orig_chat_enabled
    settings.STORE_AGENT_STEPS = orig_store_steps
    settings.EZAUTH_ALLOW_ANONYMOUS_PATHS = orig_anon_paths
    settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = orig_allowed_domains
    settings.EZAUTH_ALLOWED_OBJECT_IDS = orig_allowed_object_ids


@pytest.fixture(scope="session")
async def live_app(configure_unit_test_settings):
    """Create the FastAPI app once per test session and run startup/shutdown once.

    Unit tests avoid real datastores by injecting a lightweight fake repo.
    Explicitly depends on configure_unit_test_settings to ensure settings are
    correct before app creation.
    """
    from app.main import create_app

    app = create_app()

    # --- Minimal in-memory fakes for unit tests ---
    # Provide a repo with the attributes tests clean up and methods that raise
    # if accidentally exercised in unit scope. Integration tests use real repos.
    class _NoopMemoryRepo:
        def __init__(self) -> None:
            # Containers cleared by clear_db fixture
            self.items: dict = {}
            self._curation: dict = {}

        # GroundTruthRepo contract — raise if called in unit tests
        async def import_bulk_gt(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_gt_by_dataset(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_all_gt(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_gt_paginated(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_datasets(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def get_gt(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def upsert_gt(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def soft_delete_gt(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def delete_dataset(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def stats(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_unassigned(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def sample_unassigned(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def assign_to(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_assigned(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def upsert_assignment_doc(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def list_assignments_by_user(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def get_assignment_by_gt(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def delete_assignment_doc(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def get_curation_instructions(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

        async def upsert_curation_instructions(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError("GroundTruthRepo not available in unit tests")

    # Global tag registry in-memory implementation for unit tests
    class _InMemoryTagsRepo:
        def __init__(self) -> None:
            self.tags: list[str] = []

        async def get_global_tags(self) -> list[str]:
            return list(self.tags)

        async def save_global_tags(self, tags: list[str]) -> list[str]:
            self.tags = list(tags)
            return list(self.tags)

        async def upsert_add(self, tags_to_add):
            cur = set(self.tags)
            for t in tags_to_add:
                cur.add(str(t))
            self.tags = sorted(cur)
            return list(self.tags)

        async def upsert_remove(self, tags_to_remove):
            cur = set(self.tags)
            rem = {str(t) for t in tags_to_remove}
            self.tags = sorted(cur - rem)
            return list(self.tags)

    # Wire fakes into the global container for unit test scope
    try:
        container.repo = _NoopMemoryRepo()
    except Exception:
        # If container is immutable in some contexts, continue with None
        pass
    container.assignment_service = AssignmentService(container.repo)
    container.snapshot_service = SnapshotService(container.repo)
    container.search_service = SearchService()
    container.curation_service = CurationService(container.repo)
    container.tag_registry_service = TagRegistryService(_InMemoryTagsRepo())
    container.inference_service = None  # No real agent in unit tests
    container.chat_service = ChatService(
        inference_service=None,
        steps_store=None,
        store_steps=False,
    )
    # Import LifespanManager lazily so tests can still run without the
    # optional dev dependency installed. If missing, we yield the app and
    # rely on FastAPI's lifespan being a no-op (it will still run, but
    # this avoids an import error during test collection).
    try:
        from asgi_lifespan import LifespanManager

        async with LifespanManager(app):
            yield app
    except Exception:
        yield app


@pytest.fixture(scope="session")
async def async_client(live_app):
    """Session-scoped HTTPX AsyncClient using ASGITransport (no sockets).

    Reusing the client for the session avoids creating one per test and keeps
    the app lifespan active.
    """
    transport = ASGITransport(app=live_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture()
def user_headers():
    return {"X-User-Id": "test-user"}


@pytest.fixture(autouse=True)
def force_unit_test_auth_mode():
    """Force auth settings to unit test defaults before EACH test.

    This is critical when running all tests together via VS Code, as integration
    tests may have set EZAUTH_ENABLED=True, and unit tests need it to be False.
    This function-scoped fixture runs before each test and overrides any
    session-level settings from integration tests.
    """
    settings.EZAUTH_ENABLED = False
    settings.AUTH_MODE = "dev"
    settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = None
    settings.EZAUTH_ALLOWED_OBJECT_IDS = None
    yield


@pytest.fixture(autouse=True)
def clear_db():
    """Reset the fake repo state before each test.

    This is a sync fixture to avoid warnings with sync tests.
    """
    repo = container.repo
    items = getattr(repo, "items", None)
    if isinstance(items, dict):
        items.clear()
    cur = getattr(repo, "_curation", None)
    if isinstance(cur, dict):
        cur.clear()
    yield


@pytest.fixture(autouse=True)
def reset_chat_state():
    orig_service = container.chat_service
    orig_inference = container.inference_service
    orig_store = container.agent_steps_store
    chat_enabled = settings.CHAT_ENABLED
    store_steps = settings.STORE_AGENT_STEPS
    yield
    container.chat_service = orig_service
    container.inference_service = orig_inference
    container.agent_steps_store = orig_store
    settings.CHAT_ENABLED = chat_enabled
    settings.STORE_AGENT_STEPS = store_steps
    try:
        container.chat_service.set_store_steps(settings.STORE_AGENT_STEPS)
        container.chat_service.set_steps_store(container.agent_steps_store)
    except Exception:
        pass


# Optional: use uvloop for faster event loop if installed. This is safe to
# execute — if uvloop is missing we silently skip it.
try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


# Helper fixture to override dependencies conveniently in tests.
def use_fakes(app, overrides: dict):
    """Apply dependency overrides to the FastAPI app.

    `overrides` should be a mapping from original dependency callables to a
    replacement callable (or object). This is a small helper for tests that
    want to swap in-memory repos or fake clients.
    """
    app.dependency_overrides.update(overrides)


# Provide a respx fixture to make external HTTP mocking straightforward. Tests
# that need to mock HTTP should depend on the `respx_mock` fixture.
@pytest.fixture
def respx_mock():
    try:
        import respx

        with respx.mock:
            yield respx
    except Exception:
        # If respx isn't installed, yield None — tests that require respx will
        # fail and should add it to dev-deps. This keeps the fixture import
        # safe for environments without respx.
        yield None
