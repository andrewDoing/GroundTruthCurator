"""Integration tests for the recompute-tags endpoint."""

import uuid

import pytest
from httpx import AsyncClient


def make_item(dataset: str, status: str = "draft") -> dict:
    """Create a test ground truth item."""
    return {
        "id": str(uuid.uuid4()),
        "datasetName": dataset,
        "bucket": str(uuid.UUID("00000000-0000-0000-0000-000000000000")),
        "synthQuestion": "What is the capital of France?",
        "status": status,
    }


@pytest.mark.anyio
async def test_recompute_tags_dry_run(async_client: AsyncClient, user_headers):
    """Test recompute with dry_run=true doesn't persist changes."""
    dataset = "test-recompute-dry"
    items = [make_item(dataset) for _ in range(3)]

    # Import items
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200
    assert r.json()["imported"] == 3

    # Call recompute with dry_run=true
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"dry_run": True},
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["dry_run"] is True
    assert data["total"] >= 3
    assert data["processed"] == data["updated"] + data["skipped"]
    assert "duration_ms" in data
    assert isinstance(data["errors"], list)


@pytest.mark.anyio
async def test_recompute_tags_with_dataset_filter(async_client: AsyncClient, user_headers):
    """Test recompute filtered by dataset."""
    dataset = "test-recompute-filter-ds"
    other_dataset = "test-recompute-other-ds"
    items_ds = [make_item(dataset) for _ in range(2)]
    items_other = [make_item(other_dataset) for _ in range(3)]

    # Import items to both datasets
    r = await async_client.post("/v1/ground-truths", json=items_ds, headers=user_headers)
    assert r.status_code == 200
    r = await async_client.post("/v1/ground-truths", json=items_other, headers=user_headers)
    assert r.status_code == 200

    # Call recompute with dataset filter
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"dataset": dataset, "dry_run": True},
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should only process items from the filtered dataset
    assert data["total"] == 2
    assert data["processed"] == data["total"]


@pytest.mark.anyio
async def test_recompute_tags_with_status_filter(async_client: AsyncClient, user_headers):
    """Test recompute filtered by status."""
    dataset = "test-recompute-filter-status"
    draft_items = [make_item(dataset, status="draft") for _ in range(2)]
    approved_items = [make_item(dataset, status="approved") for _ in range(3)]

    # Import items
    r = await async_client.post(
        "/v1/ground-truths", json=draft_items + approved_items, headers=user_headers
    )
    assert r.status_code == 200

    # Call recompute with status filter for approved items only
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"status": "approved", "dry_run": True},
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should only process approved items
    assert data["total"] == 3
    assert data["dry_run"] is True


@pytest.mark.anyio
async def test_recompute_tags_empty_result(async_client: AsyncClient, user_headers):
    """Test recompute with no matching items returns empty response."""
    # Use a dataset name that definitely doesn't exist
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"dataset": "nonexistent-dataset-12345", "dry_run": True},
        headers=user_headers,
    )

    # Should return 200 with total=0 (empty result set)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["processed"] == 0
    assert data["updated"] == 0
    assert data["skipped"] == 0


@pytest.mark.anyio
async def test_recompute_tags_persists_changes(async_client: AsyncClient, user_headers):
    """Test that items are updated when dry_run=false."""
    dataset = "test-recompute-persist"
    items = [make_item(dataset) for _ in range(2)]

    # Import items
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # Get the first item's ID for verification
    item_id = items[0]["id"]
    bucket = items[0]["bucket"]

    # Call recompute with dry_run=false
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"dataset": dataset, "dry_run": False},
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is False

    # Fetch the item and verify it still exists (wasn't corrupted)
    get_response = await async_client.get(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}",
        headers=user_headers,
    )
    assert get_response.status_code == 200
    fetched_item = get_response.json()
    assert fetched_item["id"] == item_id
    # Verify computedTags field exists
    assert "computedTags" in fetched_item


@pytest.mark.anyio
async def test_recompute_tags_response_structure(async_client: AsyncClient, user_headers):
    """Test that response contains all expected fields with correct types."""
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"dry_run": True},
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all fields are present
    assert "total" in data
    assert "processed" in data
    assert "updated" in data
    assert "skipped" in data
    assert "errors" in data
    assert "dry_run" in data
    assert "duration_ms" in data

    # Verify types
    assert isinstance(data["total"], int)
    assert isinstance(data["processed"], int)
    assert isinstance(data["updated"], int)
    assert isinstance(data["skipped"], int)
    assert isinstance(data["errors"], list)
    assert isinstance(data["dry_run"], bool)
    assert isinstance(data["duration_ms"], int)


@pytest.mark.anyio
async def test_recompute_tags_combined_filters(async_client: AsyncClient, user_headers):
    """Test recompute with both dataset and status filters."""
    dataset = "test-recompute-combined"
    # Create mix of statuses
    draft_items = [make_item(dataset, status="draft") for _ in range(2)]
    approved_items = [make_item(dataset, status="approved") for _ in range(1)]

    # Import items
    r = await async_client.post(
        "/v1/ground-truths", json=draft_items + approved_items, headers=user_headers
    )
    assert r.status_code == 200

    # Call recompute with both filters
    response = await async_client.post(
        "/v1/ground-truths/recompute-tags",
        params={"dataset": dataset, "status": "draft", "dry_run": True},
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should only process draft items from the specific dataset
    assert data["total"] == 2
    assert data["processed"] == 2
