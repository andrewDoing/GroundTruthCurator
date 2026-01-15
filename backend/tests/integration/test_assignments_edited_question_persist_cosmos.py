from __future__ import annotations

from typing import Any, cast
from uuid import uuid4, UUID

import pytest
from httpx import AsyncClient



def make_item(dataset: str, item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "datasetName": dataset,
        # Fixed bucket UUID for deterministic PK
        "bucket": str(UUID("00000000-0000-0000-0000-000000000000")),
        "synthQuestion": "Original synth question?",
        "answer": None,
        "refs": [],
        "manualTags": [
            "source:synthetic",
            "split:train",
            "answerability:answerable",
            "topic:general",
            "question_length:short",
            "retrieval_behavior:single",
        ],
    }


@pytest.mark.anyio
async def test_assignments_put_persists_edited_question_camel_case(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Ensure that providing editedQuestion (camelCase) in the assignments PUT body
    updates and persists the field (alias -> edited_question) and is reflected on
    subsequent GET/list responses.

    Regression coverage for previous bug where only snake_case 'edited_question'
    was checked, causing the field to be dropped.
    """
    dataset = f"editedq-{uuid4().hex[:6]}"
    item_id = "gt-1"
    item = make_item(dataset, item_id)

    # Import single item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200, r.text

    # Self-serve assign 1 item to current user so we can use assignments PUT
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers
    )
    assert r.status_code == 200, r.text

    # Fetch dataset items to discover bucket + etag
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200, r.text
    items = cast(list[dict[str, Any]], r.json())
    row = next(x for x in items if x.get("id") == item_id)
    bucket = cast(str, row["bucket"])
    etag = cast(str, row.get("_etag"))

    # Update via assignments PUT using camelCase editedQuestion
    new_question = "How do I reset my password (rephrased)?"
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{item_id}",
        headers={**user_headers, "If-Match": etag},
        json={"editedQuestion": new_question},
    )
    assert r.status_code == 200, r.text
    body = cast(dict[str, Any], r.json())
    assert body.get("editedQuestion") == new_question

    # Fetch item directly and assert persistence
    r = await async_client.get(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}", headers=user_headers
    )
    assert r.status_code == 200, r.text
    fetched = cast(dict[str, Any], r.json())
    assert fetched.get("editedQuestion") == new_question

    # List my assignments and ensure enriched view carries updated question
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200, r.text
    my_items = cast(list[dict[str, Any]], r.json())
    mine = next(x for x in my_items if x.get("id") == item_id)
    assert mine.get("editedQuestion") == new_question
