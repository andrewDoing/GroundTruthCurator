from httpx import AsyncClient
from pydantic import TypeAdapter
import pytest
import uuid

from app.domain.models import GroundTruthItem
from app.container import container
from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo


def make_item(dataset: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        # Use NIL UUID for explicit bucket in tests
        "bucket": str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "synthQuestion": "Q?",
        "samplingBucket": 0,
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
    # mypy: data.get returns Optional[Any]; use default [] to ensure list type
    adocs = TypeAdapter(list[GroundTruthItem]).validate_python(data.get("assigned") or [])
    assert adocs and len(adocs) >= 1
    gt_id = adocs[0].id

    # SME approves via assignments PUT
    payload = {"approve": True, "answer": "ans", "etag": adocs[0].etag}
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
    adocs = TypeAdapter(list[GroundTruthItem]).validate_python(data.get("assigned") or [])
    assert adocs and len(adocs) >= 1
    gt = adocs[0]

    # Verify assignment document exists
    repo = container.repo
    assert isinstance(repo, CosmosGroundTruthRepo)
    assignment = await repo.get_assignment_by_gt(TEST_USER_ID, gt.id)
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
    payload = {"approve": True, "answer": "ans", "etag": gt.etag}
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt.id}", json=payload, headers=user_headers
    )
    assert r.status_code == 200
    res: dict = r.json()
    assert res.get("status") == "approved"

    # Verify assignment document is deleted after approval
    assignment_after = await repo.get_assignment_by_gt(user_id, gt.id)
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
    payload = {"status": "deleted", "etag": gt.etag}
    r = await async_client.put(
        f"/v1/assignments/{dataset}/{bucket}/{gt.id}", json=payload, headers=user_headers
    )
    assert r.status_code == 200
    res: dict = r.json()
    assert res.get("status") == "deleted"

    # Verify assignment document is deleted after soft-delete
    assignment_after = await repo.get_assignment_by_gt(user_id, gt.id)
    assert assignment_after is None, "Assignment document should be deleted after soft-delete"
