"""Integration tests for ID search functionality on GET /v1/ground-truths endpoint.

Note: ID search is case-sensitive when using Cosmos DB emulator due to limitations.
In production Azure Cosmos DB, case-insensitive search can be enabled using LOWER()/UPPER() functions.
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.domain.models import GroundTruthListResponse


def make_item(dataset: str, gid: str | None = None) -> dict:
    """Helper to create a minimal ground truth item for testing."""
    return {
        "id": gid or f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
    }


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_exact_match(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test exact ID match (case-sensitive)."""
    dataset = f"gt-id-exact-{uuid4().hex[:6]}"
    item_id = f"test-exact-{uuid4().hex[:8]}"

    # Create item
    item = make_item(dataset, gid=item_id)
    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search with exact ID
    res = await async_client.get(
        "/v1/ground-truths", params={"itemId": item_id}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].id == item_id


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_partial_match(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test partial ID match finds items containing search term."""
    dataset = f"gt-id-partial-{uuid4().hex[:6]}"
    unique = uuid4().hex[:6]

    # Create multiple items with common substring
    items = [
        make_item(dataset, gid=f"{unique}-suffix1"),
        make_item(dataset, gid=f"{unique}-end"),
        make_item(dataset, gid="no-match-here"),
    ]
    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Search for common substring
    res = await async_client.get(
        "/v1/ground-truths", params={"itemId": unique}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2
    found_ids = {item.id for item in response_data.items}
    assert f"{unique}-suffix1" in found_ids
    assert f"{unique}-end" in found_ids


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_with_whitespace_trimming(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test whitespace trimming in search parameter."""
    dataset = f"gt-id-trim-{uuid4().hex[:6]}"
    item_id = f"trim-test-{uuid4().hex[:6]}"

    item = make_item(dataset, gid=item_id)
    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search with leading/trailing whitespace
    res = await async_client.get(
        "/v1/ground-truths", params={"itemId": f"  {item_id}  "}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].id == item_id


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_whitespace_only_returns_all(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that whitespace-only itemId is treated as omitted."""
    dataset = f"gt-id-ws-{uuid4().hex[:6]}"

    # Create multiple items
    items = [make_item(dataset) for _ in range(3)]
    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Search with whitespace-only (should return all items in dataset)
    res = await async_client.get(
        "/v1/ground-truths", params={"itemId": "   ", "dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    # Should return all items from dataset (whitespace-only treated as omitted)
    assert len(response_data.items) >= 3


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_combined_with_other_filters(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test ID search combined with dataset filters."""
    dataset = f"gt-id-combo-{uuid4().hex[:6]}"
    unique = uuid4().hex[:6]

    # Create items in test dataset
    items = [
        make_item(dataset, gid=f"{unique}-1"),
        make_item(dataset, gid=f"{unique}-2"),
        make_item(dataset, gid=f"nomatch-{uuid4().hex[:6]}"),
    ]
    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Search with ID + dataset filter
    res = await async_client.get(
        "/v1/ground-truths",
        params={"itemId": unique, "dataset": dataset},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    # Should find the 2 items with matching ID in this dataset
    assert len(response_data.items) == 2
    assert all(unique in item.id for item in response_data.items)


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_empty_results(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test empty results when no IDs match search term."""
    dataset = f"gt-id-empty-{uuid4().hex[:6]}"

    item = make_item(dataset, gid=f"known-id-{uuid4().hex[:6]}")
    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for non-existent ID substring
    res = await async_client.get(
        "/v1/ground-truths",
        params={"itemId": "this-will-not-match-anything", "dataset": dataset},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 0


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_pagination(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test pagination works correctly with ID search."""
    dataset = f"gt-id-page-{uuid4().hex[:6]}"
    unique = uuid4().hex[:6]

    # Create multiple matching items
    items = [make_item(dataset, gid=f"{unique}-{i}") for i in range(5)]
    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Get first page with limit=2
    res = await async_client.get(
        "/v1/ground-truths",
        params={"itemId": unique, "limit": 2, "page": 1},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2
    assert response_data.pagination.has_next is True
    assert response_data.pagination.total == 5


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_too_long_returns_400(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that itemId longer than 200 characters returns 400 error."""
    long_id = "x" * 201  # 201 characters

    res = await async_client.get(
        "/v1/ground-truths", params={"itemId": long_id}, headers=user_headers
    )
    assert res.status_code == 400
    assert "200 characters" in res.json()["detail"]


@pytest.mark.anyio
async def test_list_ground_truths_search_by_id_no_param_returns_all(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that omitting itemId parameter returns all items (existing behavior unchanged)."""
    dataset = f"gt-id-nofilter-{uuid4().hex[:6]}"

    items = [make_item(dataset) for _ in range(3)]
    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Query without itemId parameter
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) >= 3
