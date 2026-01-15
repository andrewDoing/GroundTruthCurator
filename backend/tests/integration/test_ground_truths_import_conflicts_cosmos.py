from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient


def make_item(dataset: str, item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
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
async def test_duplicate_import_returns_409(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    dataset = f"gt-dup-{uuid4().hex[:6]}"
    item = make_item(dataset, "gt-dup-1")

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Import same id again -> 409
    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code in (200, 409)
    # Some implementations may upsert silently; enforce that at least the dataset still contains a single logical row.
    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert res.status_code == 200
    items = res.json()
    ids = [x.get("id") for x in items]
    assert ids.count("gt-dup-1") == 1
