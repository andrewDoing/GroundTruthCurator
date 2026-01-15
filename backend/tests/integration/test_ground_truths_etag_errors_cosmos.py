from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest
from httpx import AsyncClient


def make_item(dataset: str, item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "How do I reset my password?",
        "answer": "Use the reset link",
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
async def test_put_requires_etag_and_rejects_mismatch(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    dataset = f"gt-etag-{uuid4().hex[:6]}"
    item = make_item(dataset, "gt-1")

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Discover bucket and etag
    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert res.status_code == 200
    items = cast(list[dict[str, Any]], res.json())
    row = next(x for x in items if x.get("id") == "gt-1")
    bucket = cast(str, row["bucket"])
    etag = cast(str, row["_etag"])

    # Missing If-Match -> 412
    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-1",
        headers=user_headers,
        json={"answer": "Updated"},
    )
    assert res.status_code == 412

    # Mismatched If-Match -> 412
    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-1",
        headers={**user_headers, "If-Match": '"bogus-etag"'},
        json={"answer": "Updated"},
    )
    assert res.status_code == 412

    # Correct If-Match -> 200
    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-1",
        headers={**user_headers, "If-Match": etag},
        json={"answer": "Updated again"},
    )
    assert res.status_code == 200


@pytest.mark.anyio
async def test_put_rejects_computed_tags_and_legacy_tags(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """PUT rejects 'computedTags' (system-generated) and deprecated 'tags' field."""
    dataset = f"gt-tags-{uuid4().hex[:6]}"
    item = make_item(dataset, "gt-1")

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    items = cast(list[dict[str, Any]], res.json())
    row = next(x for x in items if x.get("id") == "gt-1")
    bucket, etag = row["bucket"], row["_etag"]

    # computedTags -> 400
    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-1",
        headers={**user_headers, "If-Match": etag},
        json={"computedTags": ["turns:multiturn"]},
    )
    assert res.status_code == 400
    assert "computedTags" in res.json().get("detail", "")

    # legacy 'tags' -> 400
    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/gt-1",
        headers={**user_headers, "If-Match": etag},
        json={"tags": ["source:manual"]},
    )
    assert res.status_code == 400
    assert "deprecated" in res.json().get("detail", "")
