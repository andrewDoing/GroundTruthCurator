from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.enums import GroundTruthStatus


def build_item(
    dataset: str,
    *,
    idx: int,
    status: str = GroundTruthStatus.draft.value,
    tags: list[str] | None = None,
    answer: str | None = None,
    reviewed_at: datetime | None = None,
    updated_at: datetime | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    reviewed = reviewed_at or now
    updated = updated_at or reviewed
    return {
        "id": item_id or f"{dataset}-{idx}-{uuid4().hex[:6]}",
        "datasetName": dataset,
        "bucket": str(uuid4()),
        "status": status,
        "synthQuestion": f"Question {idx}",
        "answer": answer,
        "refs": [],
        "manualTags": tags or ["source:sme"],
        "reviewedAt": reviewed.isoformat(),
        "updatedAt": updated.isoformat(),
    }


async def import_items(
    async_client: AsyncClient, user_headers: dict[str, str], items: list[dict[str, Any]]
) -> None:
    response = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_list_all_ground_truths_default_params(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"default-{uuid4().hex[:6]}"
    base = datetime.now(timezone.utc)
    items = [
        build_item(
            dataset,
            idx=0,
            status=GroundTruthStatus.approved.value,
            reviewed_at=base - timedelta(days=1),
        ),
        build_item(dataset, idx=1, status=GroundTruthStatus.draft.value, reviewed_at=base),
    ]

    # import items
    await import_items(async_client, user_headers, items)

    response = await async_client.get("/v1/ground-truths", headers=user_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["limit"] == 25
    assert body["pagination"]["total"] == len(items)
    assert body["pagination"]["hasNext"] is False
    assert body["pagination"]["hasPrev"] is False
    returned_ids = [entry["id"] for entry in body["items"]]
    assert len(returned_ids) == 2
    assert returned_ids[0] == items[1]["id"]


@pytest.mark.anyio
async def test_list_all_ground_truths_filter_by_status(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"status-{uuid4().hex[:6]}"
    entries = [
        build_item(dataset, idx=0, status=GroundTruthStatus.approved.value),
        build_item(dataset, idx=1, status=GroundTruthStatus.draft.value),
    ]
    await import_items(async_client, user_headers, entries)

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"status": GroundTruthStatus.approved.value},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert all(item["status"] == GroundTruthStatus.approved.value for item in payload["items"])


@pytest.mark.anyio
async def test_list_all_ground_truths_filter_by_dataset(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset_primary = f"dataset-{uuid4().hex[:6]}"
    dataset_other = f"other-{uuid4().hex[:6]}"
    await import_items(
        async_client,
        user_headers,
        [
            build_item(dataset_primary, idx=0),
            build_item(dataset_other, idx=0),
        ],
    )

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"dataset": dataset_primary},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 1
    assert all(item["datasetName"] == dataset_primary for item in data["items"])


@pytest.mark.anyio
async def test_list_all_ground_truths_filter_by_tags(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"tags-{uuid4().hex[:6]}"
    await import_items(
        async_client,
        user_headers,
        [
            build_item(dataset, idx=0, tags=["source:sme", "split:validation"]),
            build_item(dataset, idx=1, tags=["source:sme", "split:test"]),
        ],
    )

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"tags": "source:sme,split:validation"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["items"][0]["id"].startswith(dataset)
    assert "split:validation" in payload["items"][0]["tags"]


@pytest.mark.anyio
async def test_list_all_ground_truths_sort_by_updated_at_desc(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"sort-{uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    entries = [
        build_item(
            dataset,
            idx=0,
            updated_at=now + timedelta(minutes=5),
            reviewed_at=now + timedelta(minutes=5),
        ),
        build_item(dataset, idx=1, updated_at=now, reviewed_at=now),
        build_item(
            dataset,
            idx=2,
            updated_at=now - timedelta(minutes=5),
            reviewed_at=now - timedelta(minutes=5),
        ),
    ]
    await import_items(async_client, user_headers, entries)

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"sortBy": "updatedAt", "sortOrder": "desc"},
    )
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert ids[0] == entries[0]["id"]
    assert ids[-1] == entries[2]["id"]


async def _seed_paginated_dataset(
    async_client: AsyncClient,
    user_headers: dict[str, str],
    dataset: str,
    total: int,
) -> list[str]:
    base = datetime.now(timezone.utc)
    items = [
        build_item(
            dataset,
            idx=i,
            reviewed_at=base - timedelta(minutes=i),
            updated_at=base - timedelta(minutes=i),
            item_id=f"{dataset}-{i:03d}",
        )
        for i in range(total)
    ]
    await import_items(async_client, user_headers, items)
    return [item["id"] for item in items]


@pytest.mark.anyio
async def test_list_all_ground_truths_pagination_first_page(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"page1-{uuid4().hex[:6]}"
    await _seed_paginated_dataset(async_client, user_headers, dataset, total=12)

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"limit": 5, "page": 1, "sortBy": "id", "sortOrder": "asc", "dataset": dataset},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["hasNext"] is True
    assert body["pagination"]["hasPrev"] is False
    assert len(body["items"]) == 5


@pytest.mark.anyio
async def test_list_all_ground_truths_pagination_middle_page(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"page2-{uuid4().hex[:6]}"
    await _seed_paginated_dataset(async_client, user_headers, dataset, total=12)

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"limit": 5, "page": 2, "sortBy": "id", "sortOrder": "asc", "dataset": dataset},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 2
    assert body["pagination"]["hasNext"] is True
    assert body["pagination"]["hasPrev"] is True
    assert len(body["items"]) == 5


@pytest.mark.anyio
async def test_list_all_ground_truths_pagination_last_page(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"page3-{uuid4().hex[:6]}"
    await _seed_paginated_dataset(async_client, user_headers, dataset, total=11)

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"limit": 5, "page": 3, "sortBy": "id", "sortOrder": "asc", "dataset": dataset},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 3
    assert body["pagination"]["hasNext"] is False
    assert body["pagination"]["hasPrev"] is True
    assert len(body["items"]) == 1


@pytest.mark.anyio
async def test_list_all_ground_truths_empty_results(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset = f"empty-{uuid4().hex[:6]}"
    await import_items(
        async_client,
        user_headers,
        [build_item(dataset, idx=0, status=GroundTruthStatus.draft.value)],
    )

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"status": GroundTruthStatus.deleted.value},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 0
    assert body["pagination"]["totalPages"] == 0


@pytest.mark.anyio
async def test_list_all_ground_truths_combined_filters(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    dataset_target = f"combo-{uuid4().hex[:6]}"
    await import_items(
        async_client,
        user_headers,
        [
            build_item(
                dataset_target,
                idx=0,
                status=GroundTruthStatus.approved.value,
                tags=["source:sme", "split:validation"],
            ),
            build_item(
                dataset_target,
                idx=1,
                status=GroundTruthStatus.draft.value,
                tags=["source:sme", "split:validation"],
            ),
            build_item(
                "other",
                idx=0,
                status=GroundTruthStatus.approved.value,
                tags=["source:sme", "split:validation"],
            ),
        ],
    )

    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={
            "status": GroundTruthStatus.approved.value,
            "dataset": dataset_target,
            "tags": "source:sme,split:validation",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    item = body["items"][0]
    assert item["status"] == GroundTruthStatus.approved.value
    assert item["datasetName"] == dataset_target
    assert set(["source:sme", "split:validation"]).issubset(set(item["tags"]))


@pytest.mark.anyio
async def test_list_all_ground_truths_invalid_limit_exceeds_max(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"limit": 150},
    )
    assert response.status_code == 400
    assert "limit" in response.json().get("detail", "")


@pytest.mark.anyio
async def test_list_all_ground_truths_invalid_page_zero(
    async_client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await async_client.get(
        "/v1/ground-truths",
        headers=user_headers,
        params={"page": 0},
    )
    assert response.status_code == 400
    assert "page" in response.json().get("detail", "")
