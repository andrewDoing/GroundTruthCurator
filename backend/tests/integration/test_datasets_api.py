import uuid

import pytest
from httpx import AsyncClient, ASGITransport


def make_gt_item(dataset: str, *, bucket: str | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        "bucket": bucket or str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "synthQuestion": f"Question for {dataset}?",
        "docType": "ground-truth-item",
    }


@pytest.mark.anyio
async def test_list_datasets_empty_returns_empty_array(async_client: AsyncClient):
    resp = await async_client.get("/v1/datasets")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_datasets_returns_distinct_sorted_names(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    payload = [
        make_gt_item("alpha"),
        make_gt_item("beta"),
        make_gt_item("alpha"),
    ]
    resp = await async_client.post("/v1/ground-truths", json=payload, headers=user_headers)
    assert resp.status_code == 200

    resp2 = await async_client.get("/v1/datasets", headers=user_headers)
    assert resp2.status_code == 200
    assert resp2.json() == ["alpha", "beta"]


@pytest.mark.anyio
async def test_list_datasets_ignores_non_ground_truth_docs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    # Seed a real ground-truth dataset and a non-ground-truth doc for a different dataset.
    resp = await async_client.post(
        "/v1/ground-truths",
        json=[make_gt_item("alpha")],
        headers=user_headers,
    )
    assert resp.status_code == 200

    resp = await async_client.put(
        "/v1/datasets/gamma/curation-instructions",
        json={"instructions": "content"},
        headers=user_headers,
    )
    assert resp.status_code in (200, 201)

    resp2 = await async_client.get("/v1/datasets", headers=user_headers)
    assert resp2.status_code == 200
    assert resp2.json() == ["alpha"]


@pytest.mark.anyio
async def test_list_datasets_requires_auth(live_app, async_client: AsyncClient):
    anon = AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver")
    try:
        resp = await anon.get("/v1/datasets")
        assert resp.status_code == 401
    finally:
        await anon.aclose()

    resp2 = await async_client.get("/v1/datasets")
    assert resp2.status_code == 200


@pytest.mark.anyio
async def test_list_datasets_with_multiple_buckets_same_dataset(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    buckets = [str(uuid.uuid4()), str(uuid.uuid4())]
    payload = [
        make_gt_item("delta", bucket=buckets[0]),
        make_gt_item("delta", bucket=buckets[1]),
    ]
    resp = await async_client.post("/v1/ground-truths", json=payload, headers=user_headers)
    assert resp.status_code == 200

    resp2 = await async_client.get("/v1/datasets", headers=user_headers)
    assert resp2.status_code == 200
    assert resp2.json() == ["delta"]
