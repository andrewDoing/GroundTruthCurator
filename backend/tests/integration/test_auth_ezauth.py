from __future__ import annotations

import base64
import json
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import create_app


def _b64_json(obj) -> str:
    return base64.b64encode(json.dumps(obj).encode("utf-8")).decode("utf-8")


@pytest.fixture(scope="function")
async def live_app(require_cosmos_backend, configure_repo_for_test_db):
    # Ensure Easy Auth is enabled for these tests
    settings.EZAUTH_ENABLED = True
    settings.EZAUTH_ALLOW_ANONYMOUS_PATHS = "/healthz"
    settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = "example.com"
    app = create_app()
    try:
        from asgi_lifespan import LifespanManager  # type: ignore

        async with LifespanManager(app):
            yield app
    except Exception:
        yield app


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_healthz_allows_anonymous(async_client: AsyncClient):
    # Using conftest's async_client which uses default live_app (EZAUTH enabled in env)
    r = await async_client.get("/healthz")
    assert r.status_code == 200


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_protected_route_requires_identity(live_app):
    transport = ASGITransport(app=live_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.get("/v1/ground-truths/stats")
        assert r.status_code == 401


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_protected_route_allows_valid_domain(live_app):
    transport = ASGITransport(app=live_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {"claims": [{"typ": "emails", "val": "user@example.com"}]}
        headers = {"X-MS-CLIENT-PRINCIPAL": _b64_json(payload)}
        r = await client.get("/v1/ground-truths/stats", headers=headers)
        assert r.status_code in (200, 204)


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_protected_route_denies_invalid_identity(live_app):
    transport = ASGITransport(app=live_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {"claims": [{"typ": "emails", "val": "user@notallowed.com"}]}
        headers = {"X-MS-CLIENT-PRINCIPAL": _b64_json(payload)}
        r = await client.get("/v1/ground-truths/stats", headers=headers)
        assert r.status_code == 403


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_protected_route_allows_allowlisted_oid(live_app):
    settings.EZAUTH_ALLOWED_EMAIL_DOMAINS = None
    settings.EZAUTH_ALLOWED_OBJECT_IDS = "00000000-0000-0000-0000-000000000999"
    transport = ASGITransport(app=live_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {"claims": [{"typ": "oid", "val": "00000000-0000-0000-0000-000000000999"}]}
        headers = {"X-MS-CLIENT-PRINCIPAL": _b64_json(payload)}
        r = await client.get("/v1/ground-truths/stats", headers=headers)
        assert r.status_code in (200, 204)
