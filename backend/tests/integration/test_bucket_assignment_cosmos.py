from httpx import AsyncClient
import pytest
import uuid


def make_item(dataset: str, with_bucket: bool = False, bucket: str | None = None) -> dict:
    item = {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        "synthQuestion": "Q?",
    }
    if with_bucket:
        item["bucket"] = bucket or str(uuid.uuid4())
    return item


@pytest.mark.anyio
async def test_import_assigns_uuid_buckets_even_distribution(
    async_client: AsyncClient, user_headers
):
    ds = "ds-bkt-dist"
    # 10 items without bucket -> expect 3 UUID buckets distributed round-robin
    items = [make_item(ds) for _ in range(10)]
    r = await async_client.post("/v1/ground-truths?buckets=3", json=items, headers=user_headers)
    assert r.status_code == 200

    r = await async_client.get(f"/v1/ground-truths/{ds}", headers=user_headers)
    assert r.status_code == 200
    data: list[dict] = r.json()
    assert len(data) == 10
    buckets = [it["bucket"] for it in data]
    # All buckets should be valid UUID strings
    for b in buckets:
        uuid.UUID(str(b))
    unique = sorted(set(buckets))
    assert len(unique) == 3
    # Distribution should be balanced: difference between max and min counts <= 1
    from collections import Counter

    counts = Counter(buckets)
    mx = max(counts.values())
    mn = min(counts.values())
    assert mx - mn <= 1


@pytest.mark.anyio
async def test_import_respects_preassigned_buckets(async_client: AsyncClient, user_headers):
    ds = "ds-bkt-pre"
    pre1 = str(uuid.uuid4())
    pre2 = str(uuid.UUID("00000000-0000-0000-0000-000000000000"))
    # 2 pre-bucketed, 3 without -> new buckets generated only for missing
    items = [
        make_item(ds, with_bucket=True, bucket=pre1),
        make_item(ds, with_bucket=True, bucket=pre2),
        make_item(ds),
        make_item(ds),
        make_item(ds),
    ]
    r = await async_client.post("/v1/ground-truths?buckets=2", json=items, headers=user_headers)
    assert r.status_code == 200

    r = await async_client.get(f"/v1/ground-truths/{ds}", headers=user_headers)
    assert r.status_code == 200
    data: list[dict] = r.json()
    assert len(data) == 5
    buckets = [it["bucket"] for it in data]
    # Preassigned buckets should appear
    assert pre1 in buckets
    assert pre2 in buckets
    # All bucket values must be valid UUID strings
    for b in buckets:
        uuid.UUID(str(b))
