from __future__ import annotations

from typing import Any, Optional, cast

from pydantic import TypeAdapter
import pytest
from uuid import uuid4
from httpx import AsyncClient

from app.domain.models import GroundTruthItem


def make_item(dataset: str, *, gid: Optional[str] = None) -> dict[str, Any]:
    return {
        "id": gid or f"gt-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "What is the capital of France?",
        "answer": "Paris",
        "refs": [],
        "manualTags": [
            "source:synthetic",
            "split:validation",
            "answerability:answerable",
            "topic:general",
            "question_length:short",
            "retrieval_behavior:single",
        ],
    }


@pytest.mark.anyio
async def test_get_item_200_and_404(async_client: AsyncClient, user_headers: dict[str, str]):
    dataset = f"gt-get-{uuid4().hex[:6]}"
    item = make_item(dataset, gid="gt-200")
    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # List to discover bucket and etag
    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert res.status_code == 200
    items = cast(list[dict[str, Any]], res.json())
    assert isinstance(items, list) and items, "expected items in dataset"
    got = next((x for x in items if x.get("id") == "gt-200"), None)
    assert got is not None
    bucket = cast(str, got["bucket"])

    # Fetch by id
    res = await async_client.get(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-200", headers=user_headers
    )
    assert res.status_code == 200
    gt_item = TypeAdapter(GroundTruthItem).validate_python(res.json())
    assert gt_item.id == "gt-200"
    assert gt_item.etag

    # 404 for missing
    res = await async_client.get(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-does-not-exist", headers=user_headers
    )
    assert res.status_code == 404


@pytest.mark.anyio
async def test_list_filters_by_status(async_client: AsyncClient, user_headers: dict[str, str]):
    dataset = f"gt-filters-{uuid4().hex[:6]}"

    draft = make_item(dataset, gid="gt-draft")
    approved = make_item(dataset, gid="gt-approved")

    # import with approve=true for the approved doc
    res = await async_client.post(
        "/v1/ground-truths",
        params={"approve": True},
        json=[approved],
        headers=user_headers,
    )
    assert res.status_code == 200

    res = await async_client.post("/v1/ground-truths", json=[draft], headers=user_headers)
    assert res.status_code == 200

    # Mark one as deleted via curator PUT with correct ETag
    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert res.status_code == 200
    items = cast(list[dict[str, Any]], res.json())
    draft_row = next((x for x in items if x.get("id") == "gt-draft"), None)
    assert draft_row is not None
    bucket = cast(str, draft_row["bucket"])
    etag = cast(str, draft_row["_etag"])

    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-draft",
        headers={**user_headers, "If-Match": etag},
        json={"status": "deleted"},
    )
    assert res.status_code == 200

    # Filters
    res = await async_client.get(
        f"/v1/ground-truths/{dataset}", params={"status": "approved"}, headers=user_headers
    )
    assert res.status_code == 200
    arr = cast(list[dict[str, Any]], res.json())
    assert all(x.get("status") == "approved" for x in arr)
    assert any(x.get("id") == "gt-approved" for x in arr)

    res = await async_client.get(
        f"/v1/ground-truths/{dataset}", params={"status": "draft"}, headers=user_headers
    )
    assert res.status_code == 200
    arr = cast(list[dict[str, Any]], res.json())
    assert all(x.get("status") == "draft" for x in arr)

    res = await async_client.get(
        f"/v1/ground-truths/{dataset}", params={"status": "deleted"}, headers=user_headers
    )
    assert res.status_code == 200
    arr = cast(list[dict[str, Any]], res.json())
    assert all(x.get("status") == "deleted" for x in arr)
    assert any(x.get("id") == "gt-draft" for x in arr)
