from httpx import AsyncClient
import pytest
import uuid

from app.domain.enums import GroundTruthStatus


def make_item(dataset: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        # Use NIL UUID for explicit bucket in tests
        "bucket": str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "synthQuestion": "What is the capital of France?",
    }


@pytest.mark.anyio
async def test_import_and_list(async_client: AsyncClient, user_headers):
    dataset = "test-ds"
    items = [make_item(dataset) for _ in range(2)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200
    data: dict = r.json()
    assert data.get("imported") == 2

    # list
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) == 2


@pytest.mark.anyio
async def test_update_with_etag(async_client: AsyncClient, user_headers):
    dataset = "test-ds-upsert"
    item = make_item(dataset)
    # import
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # get list to fetch etag
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200
    data = r.json()
    assert data and data[0]["id"] == item["id"]
    etag = data[0].get("_etag")
    assert etag
    # use the stored bucket value
    bucket = data[0]["bucket"]

    # try update without ETag -> 412
    payload = {"answer": "Paris"}
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item['id']}", json=payload, headers=user_headers
    )
    assert r.status_code == 412

    # update with If-Match header
    headers = dict(user_headers)
    headers.update({"If-Match": etag})
    payload = {"answer": "Paris", "status": "approved"}
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item['id']}", json=payload, headers=headers
    )
    assert r.status_code == 200
    res = r.json()
    assert res["answer"] == "Paris"
    assert res["status"] == GroundTruthStatus.approved.value


@pytest.mark.anyio
async def test_delete_item_and_dataset(async_client: AsyncClient, user_headers):
    dataset = "test-ds-delete"
    items = [make_item(dataset) for _ in range(3)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # delete single item
    item_id = items[0]["id"]
    # use the bucket set on the item
    bucket = items[0]["bucket"]
    r = await async_client.delete(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}", headers=user_headers
    )
    assert r.status_code == 200

    # stats should reflect one deleted
    r = await async_client.get("/v1/ground-truths/stats", headers=user_headers)
    assert r.status_code == 200
    s = r.json()
    assert s["deleted"] >= 1

    # delete dataset
    r = await async_client.delete(f"/v1/datasets/{dataset}", headers=user_headers)
    assert r.status_code == 200


@pytest.mark.anyio
async def test_snapshot_and_stats(async_client: AsyncClient, user_headers):
    dataset = "test-snapshot"
    item = make_item(dataset)
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # approve it so snapshot picks it up
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    data = r.json()
    etag = data[0]["_etag"]
    bucket = data[0]["bucket"]
    headers = dict(user_headers)
    headers.update({"If-Match": etag})
    payload = {"answer": "Paris", "status": "approved"}
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item['id']}", json=payload, headers=headers
    )
    assert r.status_code == 200

    # snapshot
    r = await async_client.post("/v1/ground-truths/snapshot", json={}, headers=user_headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"

    # stats should show at least one approved
    r = await async_client.get("/v1/ground-truths/stats", headers=user_headers)
    assert r.status_code == 200
    s = r.json()
    assert s["approved"] >= 1


@pytest.mark.anyio
async def test_import_with_approve_flag(async_client: AsyncClient, user_headers):
    dataset = "test-approve-on-import"
    item = make_item(dataset)
    # Import with approve=true so items are automatically approved
    r = await async_client.post("/v1/ground-truths?approve=true", json=[item], headers=user_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("imported") == 1

    # Verify the item is approved on read
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200
    lst = r.json()
    assert lst and lst[0]["status"] == GroundTruthStatus.approved.value

    # Stats should include at least one approved
    r = await async_client.get("/v1/ground-truths/stats", headers=user_headers)
    assert r.status_code == 200
    s = r.json()
    assert s["approved"] >= 1
