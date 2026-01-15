from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from httpx import AsyncClient
import pytest


def make_item(dataset: str, *, assigned_to: str | None = None) -> dict[str, Any]:
    return {
        "id": f"gt-{uuid.uuid4().hex[:8]}",
        "datasetName": dataset,
        # Use NIL UUID for explicit bucket to keep PK simple in tests
        "bucket": str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "synthQuestion": "Q?",
        "samplingBucket": 0,
        "assignedTo": assigned_to,
        "refs": [],
        "manualTags": ["source:synthetic"],
    }


@pytest.mark.anyio
async def test_duplicate_creates_new_item_with_rephrase_tag_and_assignment(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    ds = f"dup-int-{uuid.uuid4().hex[:6]}"
    item = make_item(ds)
    bucket = item["bucket"]
    orig_id = item["id"]

    # Import original item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Duplicate as rephrase
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{orig_id}/duplicate", headers=user_headers
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] != orig_id
    assert body["datasetName"] == ds
    assert body["bucket"] == bucket
    assert body["status"] == "draft"
    # Effective user id comes from Easy Auth principal provided by user_headers
    assert body["assignedTo"] == "tester@example.com"
    assert any(t == f"rephrase:{orig_id}" for t in (body.get("tags") or []))


@pytest.mark.anyio
async def test_duplicate_missing_original_returns_404(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    ds = f"dup-404-int-{uuid.uuid4().hex[:6]}"
    bucket = str(uuid.UUID("00000000-0000-0000-0000-000000000000"))
    missing_id = "nope"
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{missing_id}/duplicate", headers=user_headers
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_duplicate_assigned_to_other_returns_403(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    ds = f"dup-403-int-{uuid.uuid4().hex[:6]}"
    other_user = "someone-else@example.com"
    item = make_item(ds, assigned_to=other_user)
    item["assignedAt"] = datetime.now(timezone.utc).isoformat()
    bucket = item["bucket"]
    orig_id = item["id"]

    # Import the item that's assigned to another user
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Attempt to duplicate should be forbidden
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{orig_id}/duplicate", headers=user_headers
    )
    assert r.status_code == 403
