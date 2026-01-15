"""Integration tests for reference URL search on GET /v1/ground-truths endpoint."""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.domain.models import GroundTruthListResponse


@pytest.mark.anyio
async def test_ref_url_search_matches_item_level_refs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with ref url containing search term → returns item."""
    dataset = f"ref-search-item-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://example.com/page1"},
            {"url": "https://docs.example.com/guide"},
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for "page1" should find the item
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset, "refUrl": "page1"}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].id == item["id"]


@pytest.mark.anyio
async def test_ref_url_search_matches_history_level_refs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with history turn refs containing search term → returns item."""
    dataset = f"ref-search-history-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "history": [
            {
                "role": "user",
                "msg": "User question",
            },
            {
                "role": "assistant",
                "msg": "Assistant response",
                "refs": [
                    {"url": "https://docs.example.com/article/123"},
                    {"url": "https://support.example.com/kb/456"},
                ],
            },
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for "article" should find the item
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset, "refUrl": "article"}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].id == item["id"]


@pytest.mark.anyio
async def test_ref_url_search_matches_both_levels(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with item-level and history-level refs → search matches either."""
    dataset = f"ref-search-both-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://foo.com/bar"},
        ],
        "history": [
            {
                "role": "assistant",
                "msg": "Response",
                "refs": [
                    {"url": "https://baz.com/bar"},
                ],
            },
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for "bar" should find the item (matches both levels)
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset, "refUrl": "bar"}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].id == item["id"]


@pytest.mark.anyio
async def test_ref_url_search_case_sensitive(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Reference URL search is case-sensitive (Cosmos CONTAINS behavior)."""
    dataset = f"ref-search-case-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://Example.COM/Page"},
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for lowercase "example.com" should NOT find the item (case-sensitive)
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "example.com"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 0

    # Search for exact case "Example.COM" should find it
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "Example.COM"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1


@pytest.mark.anyio
async def test_ref_url_search_partial_match(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Reference URL search supports partial matching."""
    dataset = f"ref-search-partial-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://docs.example.com/guide/introduction"},
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for domain portion
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "docs.example"},
        headers=user_headers,
    )
    assert res.status_code == 200
    assert len(GroundTruthListResponse.model_validate(res.json()).items) == 1

    # Search for path portion
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset, "refUrl": "/guide"}, headers=user_headers
    )
    assert res.status_code == 200
    assert len(GroundTruthListResponse.model_validate(res.json()).items) == 1

    # Search for non-matching substring
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "nonexistent"},
        headers=user_headers,
    )
    assert res.status_code == 200
    assert len(GroundTruthListResponse.model_validate(res.json()).items) == 0


@pytest.mark.anyio
async def test_ref_url_search_no_matches(async_client: AsyncClient, user_headers: dict[str, str]):
    """Search with no matching refs returns empty list."""
    dataset = f"ref-search-nomatch-{uuid4().hex[:6]}"

    items = [
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Question 1",
            "refs": [{"url": "https://foo.com/1"}],
        },
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Question 2",
            "refs": [{"url": "https://bar.com/2"}],
        },
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Search for non-existent URL
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "nonexistent-url"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 0


@pytest.mark.anyio
async def test_ref_url_search_multiple_refs_per_item(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with multiple refs, only one matches → search finds item."""
    dataset = f"ref-search-multi-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://foo.com/1"},
            {"url": "https://bar.com/2"},
            {"url": "https://baz.com/3"},
            {"url": "https://example.com/matching-url"},
            {"url": "https://qux.com/5"},
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    # Search for the matching URL
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "matching-url"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].id == item["id"]


@pytest.mark.anyio
async def test_ref_url_search_combined_with_other_filters(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """refUrl filter works together with dataset and status filters."""
    dataset1 = f"ref-search-combined1-{uuid4().hex[:6]}"
    dataset2 = f"ref-search-combined2-{uuid4().hex[:6]}"

    items = [
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset1,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q1",
            "status": "draft",
            "refs": [{"url": "https://example.com/doc"}],
        },
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset1,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q2",
            "status": "approved",
            "refs": [{"url": "https://example.com/doc"}],
        },
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset2,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q3",
            "status": "draft",
            "refs": [{"url": "https://example.com/doc"}],
        },
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Filter by dataset + refUrl → should get 2 items from dataset1
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset1, "refUrl": "example.com"},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2

    # Filter by dataset + status + refUrl → should get 1 item (approved in dataset1)
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset1, "status": "approved", "refUrl": "example.com"},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].status.value == "approved"


@pytest.mark.anyio
async def test_ref_url_search_with_pagination(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Reference URL search works correctly with pagination."""
    dataset = f"ref-search-page-{uuid4().hex[:6]}"

    # Create 15 items with matching refs
    items = [
        {
            "id": f"test-{i:03d}-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": f"Question {i}",
            "refs": [{"url": f"https://example.com/doc/{i}"}],
        }
        for i in range(15)
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Get first page with limit=10
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "example.com", "page": 1, "limit": 10},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 10
    assert response_data.pagination.total == 15
    assert response_data.pagination.page == 1
    assert response_data.pagination.has_next is True
    assert response_data.pagination.has_prev is False

    # Get second page
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "refUrl": "example.com", "page": 2, "limit": 10},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 5
    assert response_data.pagination.total == 15
    assert response_data.pagination.page == 2
    assert response_data.pagination.has_next is False
    assert response_data.pagination.has_prev is True


@pytest.mark.anyio
async def test_ref_url_search_empty_string_ignored(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Empty or whitespace refUrl behaves like no filter."""
    dataset = f"ref-search-empty-{uuid4().hex[:6]}"

    items = [
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q1",
            "refs": [{"url": "https://foo.com"}],
        },
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q2",
            "refs": [{"url": "https://bar.com"}],
        },
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Empty string
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset, "refUrl": ""}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2  # Returns all items

    # Whitespace only
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset, "refUrl": "   "}, headers=user_headers
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2  # Returns all items


@pytest.mark.anyio
async def test_ref_url_search_omitted_parameter(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Request without refUrl parameter returns all items."""
    dataset = f"ref-search-omit-{uuid4().hex[:6]}"

    items = [
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q1",
            "refs": [{"url": "https://foo.com"}],
        },
        {
            "id": f"test-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Q2",
            "refs": [{"url": "https://bar.com"}],
        },
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Omit refUrl parameter entirely
    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2  # Returns all items


@pytest.mark.anyio
async def test_ref_url_search_too_long_returns_400(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that refUrl longer than 500 characters returns 400 error."""
    long_url = "https://example.com/" + "x" * 500  # >500 characters total

    res = await async_client.get(
        "/v1/ground-truths", params={"refUrl": long_url}, headers=user_headers
    )
    assert res.status_code == 400
    assert "500 characters" in res.json()["detail"]
