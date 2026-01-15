# moved from unit to integration tests
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_get_returns_404(async_client: AsyncClient, user_headers):
    r = await async_client.get(
        "/v1/datasets/ds1/curation-instructions",
        headers=user_headers,
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_put_create_201(async_client: AsyncClient, user_headers):
    r = await async_client.put(
        "/v1/datasets/ds1/curation-instructions",
        json={"instructions": "hello"},
        headers=user_headers,
    )
    assert r.status_code == 201
    body: dict = r.json()
    assert body["instructions"] == "hello"
    assert body.get("_etag")


@pytest.mark.anyio
async def test_put_update_200_with_etag(async_client: AsyncClient, user_headers):
    # create first
    r1 = await async_client.put(
        "/v1/datasets/ds1/curation-instructions",
        json={"instructions": "v1"},
        headers=user_headers,
    )
    assert r1.status_code == 201
    etag = r1.json()["_etag"]

    # update with If-Match
    r2 = await async_client.put(
        "/v1/datasets/ds1/curation-instructions",
        json={"instructions": "v2"},
        headers={**user_headers, "If-Match": etag},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["instructions"] == "v2"
    assert body["_etag"] != etag


@pytest.mark.anyio
async def test_put_update_412_on_mismatch(async_client: AsyncClient, user_headers):
    # create first
    r1 = await async_client.put(
        "/v1/datasets/ds1/curation-instructions",
        json={"instructions": "v1"},
        headers=user_headers,
    )
    assert r1.status_code == 201

    # update with wrong etag
    r2 = await async_client.put(
        "/v1/datasets/ds1/curation-instructions",
        json={"instructions": "v2"},
        headers={**user_headers, "If-Match": "wrong"},
    )
    assert r2.status_code == 412
