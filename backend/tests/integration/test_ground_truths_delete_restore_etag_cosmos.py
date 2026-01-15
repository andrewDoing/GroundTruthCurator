from __future__ import annotations

from typing import Any, cast
from uuid import uuid4, UUID

import pytest
from httpx import AsyncClient


def make_item(dataset: str, item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "datasetName": dataset,
        # Use NIL UUID so tests don't depend on bucket assignment logic
        "bucket": str(UUID("00000000-0000-0000-0000-000000000000")),
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
async def test_delete_then_restore_requires_fresh_etag(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Verify that after updating status to deleted (via PUT), attempting to
    restore using the pre-delete ETag yields 412, and that restoring with the
    latest ETag succeeds.

    This captures the frontend-observed behavior where a stale ETag is reused
    for the restore call.
    """
    dataset = f"gt-del-restore-{uuid4().hex[:6]}"
    item_id = "gt-1"
    item = make_item(dataset, item_id)

    # Import single item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Discover bucket and current ETag
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200
    items = cast(list[dict[str, Any]], r.json())
    row = next(x for x in items if x.get("id") == item_id)
    bucket = cast(str, row["bucket"])  # string UUID
    original_etag = cast(str, row["_etag"])  # Cosmos ETag string (quoted)

    # Update status to deleted using the original ETag
    headers = {**user_headers, "If-Match": original_etag}
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}",
        headers=headers,
        json={"status": "deleted"},
    )
    assert r.status_code == 200

    # Attempt to restore using the stale/original ETag -> expect 412 Precondition Failed
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}",
        headers=headers,  # still using original_etag
        json={"status": "draft"},
    )
    assert r.status_code == 412

    # Fetch the latest ETag and restore successfully
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200
    items = cast(list[dict[str, Any]], r.json())
    row = next(x for x in items if x.get("id") == item_id)
    latest_etag = cast(str, row["_etag"])  # ETag changed after delete
    assert latest_etag != original_etag

    headers2 = {**user_headers, "If-Match": latest_etag}
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}",
        headers=headers2,
        json={"status": "draft"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "draft"
