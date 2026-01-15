from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from pydantic.type_adapter import TypeAdapter
import pytest
from httpx import AsyncClient

from app.domain.models import GroundTruthItem


def make_item(dataset: str) -> dict[str, Any]:
    return {
        "id": f"gt-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "status": "draft",
        "samplingBucket": 0,
        "synthQuestion": "Q?",
        "answer": None,
        "refs": [],
        "manualTags": ["source:synthetic", "topic:general"],
    }


@pytest.mark.anyio
async def test_self_serve_list_and_approve(async_client: AsyncClient, user_headers: dict[str, str]):
    dataset = f"assign-{uuid4().hex[:6]}"
    items = [make_item(dataset) for _ in range(3)]
    bucket = items[0]["bucket"]

    # Import  items
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # Request 2 assignments
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 2}, headers=user_headers
    )
    assert r.status_code == 200
    resp = cast(dict[str, Any], r.json())
    assert resp.get("assignedCount") == 2
    assigned = TypeAdapter(list[GroundTruthItem]).validate_python(resp.get("assigned") or [])
    assert len(assigned) == 2

    # List my assignments
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200
    docs = TypeAdapter(list[GroundTruthItem]).validate_python(r.json())
    assert len(docs) == 2

    # Approve first via assignments PUT
    gt_id = docs[0].id
    etag = docs[0].etag
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt_id}",
        headers=user_headers,
        json={"approve": True, "answer": "ans", "etag": etag},
    )
    assert r.status_code == 200
    res = cast(dict[str, Any], r.json())
    assert res.get("status") == "approved"

    # Now my assignments should be 1
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200
    docs2 = cast(list[dict[str, Any]], r.json())
    assert len(docs2) == 1


@pytest.mark.anyio
async def test_assignment_put_persists_manual_tags(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """PUT /v1/assignments/{dataset}/{bucket}/{id} should persist manualTags."""
    dataset = f"tags-{uuid4().hex[:6]}"
    item = make_item(dataset)
    bucket = item["bucket"]

    # Import and self-assign
    await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    await async_client.post("/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers)

    # Get assigned item
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assigned = r.json()
    gt_id = assigned[0]["id"]
    etag = assigned[0]["_etag"]

    # Update with new manualTags
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt_id}",
        headers=user_headers,
        json={"manualTags": ["source:sme", "topic:general"], "etag": etag},
    )
    assert r.status_code == 200
    updated = r.json()

    # Verify manualTags are persisted
    assert "source:sme" in updated["manualTags"]
    assert "topic:general" in updated["manualTags"]


@pytest.mark.anyio
async def test_assignment_put_rejects_exclusive_tag_violations(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """PUT /v1/assignments should reject multiple exclusive tags with HTTP 400."""
    dataset = f"excl-{uuid4().hex[:6]}"
    item = make_item(dataset)
    bucket = item["bucket"]

    # Import and self-assign
    await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    await async_client.post("/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers)

    # Get assigned item
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assigned = r.json()
    gt_id = assigned[0]["id"]
    etag = assigned[0]["_etag"]

    # Attempt to update with conflicting exclusive tags (source is exclusive)
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt_id}",
        headers=user_headers,
        json={
            "manualTags": ["source:sme", "source:synthetic"],  # Both source tags - conflict!
            "etag": etag,
        },
    )

    # Should return 400 Bad Request
    assert r.status_code == 400
    error_detail = r.json()["detail"]
    assert "Group 'source' is exclusive" in error_detail
    assert "sme" in error_detail
    assert "synthetic" in error_detail


@pytest.mark.anyio
async def test_exclusive_tag_error_prevents_persistence(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Verify that validation failure does not modify the database."""
    dataset = f"persist-{uuid4().hex[:6]}"
    item = make_item(dataset)
    bucket = item["bucket"]

    # Import and self-assign
    await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    await async_client.post("/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers)

    # Get assigned item
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assigned = r.json()
    gt_id = assigned[0]["id"]
    actual_dataset = assigned[0]["datasetName"]
    actual_bucket = assigned[0]["bucket"]
    etag = assigned[0]["_etag"]
    original_tags = assigned[0]["manualTags"]

    # Attempt invalid update with exclusive tag conflict
    r = await async_client.put(
        f"/v1/assignments/{actual_dataset}/{actual_bucket}/{gt_id}",
        headers=user_headers,
        json={
            "manualTags": [
                "difficulty:easy",
                "difficulty:hard",
            ],  # Both difficulty tags - conflict!
            "answer": "This should not be saved",
            "etag": etag,
        },
    )

    # Should fail
    assert r.status_code == 400

    # Verify item was NOT modified - fetch from backend to confirm
    r = await async_client.get(
        f"/v1/ground-truths/{actual_dataset}/{actual_bucket}/{gt_id}", headers=user_headers
    )
    assert r.status_code == 200
    item_after = r.json()

    # Tags should still be the original ones
    assert item_after["manualTags"] == original_tags
    # Answer should still be None (not the rejected value)
    assert item_after["answer"] is None


@pytest.mark.anyio
async def test_assignment_allows_valid_exclusive_tag_replacement(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Verify that replacing one exclusive tag with another is allowed."""
    dataset = f"replace-{uuid4().hex[:6]}"
    item = make_item(dataset)
    item["manualTags"] = ["source:synthetic"]  # Start with one source tag
    bucket = item["bucket"]

    # Import and self-assign
    await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    await async_client.post("/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers)

    # Get assigned item
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assigned = r.json()
    gt_id = assigned[0]["id"]
    actual_dataset = assigned[0]["datasetName"]
    actual_bucket = assigned[0]["bucket"]
    etag = assigned[0]["_etag"]

    # Replace source:synthetic with source:sme (valid - only one at a time)
    r = await async_client.put(
        f"/v1/assignments/{actual_dataset}/{actual_bucket}/{gt_id}",
        headers=user_headers,
        json={
            "manualTags": ["source:sme"],  # Replace with different source
            "etag": etag,
        },
    )

    # Should succeed
    assert r.status_code == 200
    updated = r.json()
    assert "source:sme" in updated["manualTags"]
    assert "source:synthetic" not in updated["manualTags"]


@pytest.mark.anyio
async def test_assignment_allows_multiple_non_exclusive_tags(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Verify that multiple tags from non-exclusive groups are allowed."""
    dataset = f"multi-{uuid4().hex[:6]}"
    item = make_item(dataset)
    bucket = item["bucket"]

    # Import and self-assign
    await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    await async_client.post("/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers)

    # Get assigned item
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assigned = r.json()
    gt_id = assigned[0]["id"]
    actual_dataset = assigned[0]["datasetName"]
    actual_bucket = assigned[0]["bucket"]
    etag = assigned[0]["_etag"]

    # Add multiple topic tags (topic is NOT exclusive)
    r = await async_client.put(
        f"/v1/assignments/{actual_dataset}/{actual_bucket}/{gt_id}",
        headers=user_headers,
        json={
            "manualTags": ["topic:general", "topic:simulation", "topic:technical"],
            "etag": etag,
        },
    )

    # Should succeed - topic allows multiple values
    assert r.status_code == 200
    updated = r.json()
    assert "topic:general" in updated["manualTags"]
    assert "topic:simulation" in updated["manualTags"]
    assert "topic:technical" in updated["manualTags"]
