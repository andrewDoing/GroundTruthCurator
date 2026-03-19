from httpx import AsyncClient
import pytest
import uuid


def make_item(dataset: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        "bucket": str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "history": [
            {"role": "user", "msg": "Q?"},
        ],
        "assignedTo": None,
    }


@pytest.mark.anyio
async def test_sme_update_requires_etag_and_includes_updated_etag(
    async_client: AsyncClient, user_headers
):
    ds = "test-sme-etag"
    item = make_item(ds)
    bucket = item["bucket"]
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Assign using self-serve so it's available under SME routes
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers
    )
    assert r.status_code == 200

    # Try SME update without ETag -> 412
    r = await async_client.put(
        f"/v1/assignments/{ds}/{bucket}/{item['id']}",
        json={"history": [{"role": "user", "msg": "Q?"}, {"role": "assistant", "msg": "A1"}]},
        headers=user_headers,
    )
    assert r.status_code == 412

    # Fetch ETag from curator list endpoint and update via SME with If-Match
    r = await async_client.get(f"/v1/ground-truths/{ds}", headers=user_headers)
    assert r.status_code == 200
    etag = r.json()[0]["_etag"]
    headers = dict(user_headers)
    headers.update({"If-Match": etag})
    r = await async_client.put(
        f"/v1/assignments/{ds}/{bucket}/{item['id']}",
        json={"history": [{"role": "user", "msg": "Q?"}, {"role": "assistant", "msg": "A2"}]},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    history = body.get("history") or []
    assert any(turn.get("role") == "assistant" and turn.get("msg") == "A2" for turn in history)
    assert body.get("_etag") and isinstance(body["_etag"], str)


@pytest.mark.anyio
async def test_sme_etag_mismatch_returns_412(async_client: AsyncClient, user_headers):
    ds = "test-sme-etag-mismatch"
    item = make_item(ds)
    bucket = item["bucket"]
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Assign
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers
    )
    assert r.status_code == 200

    # Get fresh ETag
    r = await async_client.get(f"/v1/ground-truths/{ds}", headers=user_headers)
    etag1 = r.json()[0]["_etag"]

    # First update succeeds
    headers = dict(user_headers)
    headers.update({"If-Match": etag1})
    r = await async_client.put(
        f"/v1/assignments/{ds}/{bucket}/{item['id']}",
        json={"history": [{"role": "user", "msg": "Q?"}, {"role": "assistant", "msg": "v1"}]},
        headers=headers,
    )
    assert r.status_code == 200
    new_etag = r.json().get("_etag")
    assert new_etag and new_etag != etag1

    # Second update with stale ETag should 412
    headers_stale = dict(user_headers)
    headers_stale.update({"If-Match": etag1})
    r = await async_client.put(
        f"/v1/assignments/{ds}/{bucket}/{item['id']}",
        json={"history": [{"role": "user", "msg": "Q?"}, {"role": "assistant", "msg": "v2"}]},
        headers=headers_stale,
    )
    assert r.status_code == 412


@pytest.mark.anyio
async def test_curator_put_plugins_with_etag(async_client: AsyncClient, user_headers):
    ds = "test-curator-plugins"
    item = make_item(ds)
    bucket = item["bucket"]
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # get etag
    r = await async_client.get(f"/v1/ground-truths/{ds}", headers=user_headers)
    assert r.status_code == 200
    etag = r.json()[0]["_etag"]
    headers = dict(user_headers)
    headers.update({"If-Match": etag})

    plugin_data = {
        "score": 0.87,
        "notes": ["source-a", "source-b"],
    }
    payload = {
        "history": [
            {"role": "user", "msg": "Q?"},
            {"role": "assistant", "msg": "Ans"},
        ],
        "plugins": {
            "test-pack": {
                "kind": "test-pack",
                "version": "1.0",
                "data": plugin_data,
            }
        },
    }
    r = await async_client.put(
        f"/v1/ground-truths/{ds}/{bucket}/{item['id']}", json=payload, headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    persisted_data = body.get("plugins", {}).get("test-pack", {}).get("data")
    assert persisted_data == plugin_data
    assert body.get("_etag") and isinstance(body["_etag"], str)
