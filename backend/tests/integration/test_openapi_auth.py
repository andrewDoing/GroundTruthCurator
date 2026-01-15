import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings


@pytest.mark.anyio
async def test_openapi_requires_auth(live_app, async_client: AsyncClient):
    # Create a separate anonymous client (fixture client includes auth headers)
    anon = AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver")
    try:
        resp = await anon.get(f"{settings.API_PREFIX}/openapi.json")
        assert resp.status_code == 401
    finally:
        await anon.aclose()

    # With valid principal header should succeed (using fixture client already authed)
    resp2 = await async_client.get(f"{settings.API_PREFIX}/openapi.json")
    assert resp2.status_code == 200
    assert resp2.json().get("openapi") in ("3.1.0", "3.0.3")


@pytest.mark.anyio
async def test_docs_requires_auth(live_app, async_client: AsyncClient):
    anon = AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver")
    try:
        resp = await anon.get(f"{settings.API_PREFIX}/docs")
        assert resp.status_code == 401
    finally:
        await anon.aclose()

    resp2 = await async_client.get(f"{settings.API_PREFIX}/docs")
    assert resp2.status_code in (200, 307, 302)
    if resp2.status_code in (302, 307):
        loc = resp2.headers.get("location")
        assert loc
        resp3 = await async_client.get(loc)
        assert resp3.status_code == 200
        assert "Swagger" in resp3.text
    else:
        assert "Swagger" in resp2.text
