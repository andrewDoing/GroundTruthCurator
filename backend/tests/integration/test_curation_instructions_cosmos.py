import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_cosmos_curation_instructions_flow(async_client: AsyncClient, user_headers):
    # Create
    r1 = await async_client.put(
        "/v1/datasets/dsA/curation-instructions",
        json={"instructions": "initial"},
        headers=user_headers,
    )
    assert r1.status_code == 201
    etag1 = r1.json()["_etag"]
    # Bucket should be NIL UUID on create
    assert r1.json()["bucket"] == "00000000-0000-0000-0000-000000000000"

    # Fetch
    r2 = await async_client.get(
        "/v1/datasets/dsA/curation-instructions",
        headers=user_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["instructions"] == "initial"
    # Bucket remains NIL UUID
    assert r2.json()["bucket"] == "00000000-0000-0000-0000-000000000000"

    # Update with ETag
    r3 = await async_client.put(
        "/v1/datasets/dsA/curation-instructions",
        json={"instructions": "updated"},
        headers={**user_headers, "If-Match": etag1},
    )
    assert r3.status_code == 200
    etag2 = r3.json()["_etag"]
    assert etag2 != etag1
    # Bucket still NIL UUID after update
    assert r3.json()["bucket"] == "00000000-0000-0000-0000-000000000000"

    # Mismatch should 412
    r4 = await async_client.put(
        "/v1/datasets/dsA/curation-instructions",
        json={"instructions": "again"},
        headers={**user_headers, "If-Match": "wrong"},
    )
    assert r4.status_code == 412
