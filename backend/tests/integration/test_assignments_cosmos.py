import uuid
from typing import Any, cast

import pytest
from httpx import AsyncClient

from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo
from app.container import container


def make_item(dataset: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        # Use NIL UUID for explicit bucket in tests
        "bucket": str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "history": [
            {"role": "user", "msg": "Q?"},
        ],
        "assignedTo": None,
    }


@pytest.mark.anyio
async def test_self_serve_and_list(async_client: AsyncClient, user_headers):
    dataset = "test-assign"
    # import some items
    items = [make_item(dataset) for _ in range(3)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # request 2 assignments
    body = {"limit": 2}
    r = await async_client.post("/v1/assignments/self-serve", json=body, headers=user_headers)
    assert r.status_code == 200
    resp: dict = r.json()
    assert resp.get("assignedCount") == 2

    # list my assignments
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list)
    assert len(docs) == 2


@pytest.mark.anyio
async def test_assigned_ground_truths_update_and_approve(async_client: AsyncClient, user_headers):
    dataset = "test-assign-approve"
    item = make_item(dataset)
    bucket = item["bucket"]
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Assign using self-serve
    body = {"limit": 1}
    r = await async_client.post("/v1/assignments/self-serve", json=body, headers=user_headers)
    assert r.status_code == 200
    data: dict = r.json()
    adocs = cast(list[dict[str, Any]], data.get("assigned") or [])
    assert adocs and len(adocs) >= 1
    gt_id = cast(str, adocs[0]["id"])
    etag = cast(str | None, adocs[0].get("_etag"))
    assert etag

    # SME approves via assignments PUT
    payload = {
        "approve": True,
        "etag": etag,
        "history": [{"role": "user", "msg": "Q?"}, {"role": "assistant", "msg": "ans"}],
    }
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt_id}", json=payload, headers=user_headers
    )
    assert r.status_code == 200
    res: dict = r.json()
    assert res.get("status") == "approved"

    # assignments should be empty now
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list)
    assert len(docs) == 0


# Test user ID used by user_headers fixture
TEST_USER_ID = "tester@example.com"


@pytest.fixture
async def assigned_ground_truth(async_client: AsyncClient, user_headers):
    """Create and assign a ground truth item for testing.

    Note: Depends on async_client which transitively depends on live_app and
    configure_repo_for_test_db, ensuring proper Cosmos setup and teardown.
    """
    dataset = f"test-{uuid.uuid4().hex[:6]}"
    item = make_item(dataset)
    bucket = uuid.UUID(item["bucket"])

    # Create item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Assign via self-serve
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers
    )
    assert r.status_code == 200
    data = r.json()
    adocs = cast(list[dict[str, Any]], data.get("assigned") or [])
    assert adocs and len(adocs) >= 1
    gt = adocs[0]

    # Verify assignment document exists
    repo = container.repo
    assert isinstance(repo, CosmosGroundTruthRepo)
    assignment = await repo.get_assignment_by_gt(TEST_USER_ID, cast(str, gt["id"]))
    assert assignment is not None, "Assignment document should exist after self-serve"

    yield {
        "dataset": dataset,
        "bucket": bucket,
        "gt": gt,
        "repo": repo,
        "user_id": TEST_USER_ID,
    }
    # Cleanup is handled by conftest's close_repo_client_after_test fixture


@pytest.mark.anyio
async def test_approve_deletes_assignment_document(
    async_client: AsyncClient, user_headers, assigned_ground_truth
):
    """Verify that approving a ground truth item deletes the assignment document from the container."""
    dataset = assigned_ground_truth["dataset"]
    bucket = assigned_ground_truth["bucket"]
    gt = assigned_ground_truth["gt"]
    repo = assigned_ground_truth["repo"]
    user_id = assigned_ground_truth["user_id"]

    # SME approves via assignments PUT
    etag = cast(str | None, gt.get("_etag"))
    assert etag
    payload = {
        "approve": True,
        "etag": etag,
        "history": [{"role": "user", "msg": "Q?"}, {"role": "assistant", "msg": "ans"}],
    }
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt['id']}", json=payload, headers=user_headers
    )
    assert r.status_code == 200
    res: dict = r.json()
    assert res.get("status") == "approved"

    # Verify assignment document is deleted after approval
    assignment_after = await repo.get_assignment_by_gt(user_id, cast(str, gt["id"]))
    assert assignment_after is None, "Assignment document should be deleted after approval"


@pytest.mark.anyio
async def test_delete_deletes_assignment_document(
    async_client: AsyncClient, user_headers, assigned_ground_truth
):
    """Verify that soft-deleting a ground truth item deletes the assignment document from the container."""
    dataset = assigned_ground_truth["dataset"]
    bucket = assigned_ground_truth["bucket"]
    gt = assigned_ground_truth["gt"]
    repo = assigned_ground_truth["repo"]
    user_id = assigned_ground_truth["user_id"]

    # SME soft-deletes via assignments PUT with status=deleted
    etag = cast(str | None, gt.get("_etag"))
    assert etag
    payload = {"status": "deleted", "etag": etag}
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt['id']}", json=payload, headers=user_headers
    )
    assert r.status_code == 200
    res: dict = r.json()
    assert res.get("status") == "deleted"

    # Verify assignment document is deleted after soft-delete
    assignment_after = await repo.get_assignment_by_gt(user_id, cast(str, gt["id"]))
    assert assignment_after is None, "Assignment document should be deleted after soft-delete"
