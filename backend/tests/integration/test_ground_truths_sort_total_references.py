"""Integration tests for sorting by totalReferences field (SA-369).

Tests the database-level sorting by totalReferences, verifying that:
1. The sortBy=totalReferences parameter is accepted by the API
2. Sorting works correctly in ascending and descending order
3. Sorting handles edge cases (items with 0 refs, history vs item-level refs)
4. Pagination works correctly with totalReferences sorting
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.domain.models import GroundTruthListResponse


def make_item_with_refs(
    dataset: str,
    item_id: str,
    *,
    item_refs_count: int = 0,
    history_refs_counts: list[int] | None = None,
) -> dict:
    """Create a test item with specified reference counts.

    Args:
        dataset: Dataset name
        item_id: Item ID
        item_refs_count: Number of item-level refs
        history_refs_counts: List of ref counts per history turn (None = no history)

    Returns:
        Item dict for API submission
    """
    item: dict = {
        "id": item_id,
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": f"Question for {item_id}?",
    }

    # Add item-level refs
    if item_refs_count > 0:
        item["refs"] = [
            {"url": f"https://example.com/{item_id}/item-ref-{i}"} for i in range(item_refs_count)
        ]

    # Add history with refs if specified
    if history_refs_counts:
        history = []
        for turn_idx, ref_count in enumerate(history_refs_counts):
            # User turn (no refs)
            history.append(
                {
                    "role": "user",
                    "msg": f"Turn {turn_idx} question",
                }
            )
            # Assistant turn with refs
            turn: dict = {
                "role": "assistant",
                "msg": f"Turn {turn_idx} answer",
            }
            if ref_count > 0:
                turn["refs"] = [
                    {"url": f"https://example.com/{item_id}/turn{turn_idx}-ref-{i}"}
                    for i in range(ref_count)
                ]
            history.append(turn)
        item["history"] = history

    return item


@pytest.mark.anyio
async def test_sort_by_total_references_descending(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort by totalReferences DESC returns items with most refs first."""
    dataset = f"sort-refs-desc-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-0-refs", item_refs_count=0),
        make_item_with_refs(dataset, "item-3-refs", item_refs_count=3),
        make_item_with_refs(dataset, "item-1-ref", item_refs_count=1),
        make_item_with_refs(dataset, "item-5-refs", item_refs_count=5),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 4

    # Verify descending order (most refs first)
    ref_counts = [item.totalReferences for item in response_data.items]
    assert ref_counts == [5, 3, 1, 0], f"Expected descending order, got {ref_counts}"


@pytest.mark.anyio
async def test_sort_by_total_references_ascending(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort by totalReferences ASC returns items with fewest refs first."""
    dataset = f"sort-refs-asc-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-3-refs", item_refs_count=3),
        make_item_with_refs(dataset, "item-0-refs", item_refs_count=0),
        make_item_with_refs(dataset, "item-5-refs", item_refs_count=5),
        make_item_with_refs(dataset, "item-1-ref", item_refs_count=1),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "asc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 4

    # Verify ascending order (fewest refs first)
    ref_counts = [item.totalReferences for item in response_data.items]
    assert ref_counts == [0, 1, 3, 5], f"Expected ascending order, got {ref_counts}"


@pytest.mark.anyio
async def test_sort_by_total_references_with_history_refs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort works correctly when refs come from history turns."""
    dataset = f"sort-refs-history-{uuid4().hex[:6]}"

    items = [
        # Item with only item-level refs (2 refs)
        make_item_with_refs(dataset, "item-level-2", item_refs_count=2),
        # Item with only history refs (3 refs across turns)
        make_item_with_refs(dataset, "history-3", history_refs_counts=[1, 2]),
        # Item with no refs (0 refs)
        make_item_with_refs(dataset, "no-refs", item_refs_count=0),
        # Item with history refs overriding item refs (history: 4 refs)
        make_item_with_refs(
            dataset, "history-4-override", item_refs_count=10, history_refs_counts=[2, 2]
        ),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 4

    # Expected order: history-4-override (4), history-3 (3), item-level-2 (2), no-refs (0)
    item_ids = [item.id for item in response_data.items]
    ref_counts = [item.totalReferences for item in response_data.items]

    assert ref_counts == [4, 3, 2, 0], f"Expected [4, 3, 2, 0], got {ref_counts}"
    assert item_ids[0] == "history-4-override"
    assert item_ids[1] == "history-3"
    assert item_ids[2] == "item-level-2"
    assert item_ids[3] == "no-refs"


@pytest.mark.anyio
async def test_sort_by_total_references_stable_pagination(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Pagination is stable when sorting by totalReferences."""
    dataset = f"sort-refs-pagination-{uuid4().hex[:6]}"

    # Create 6 items: 2 with 3 refs, 2 with 1 ref, 2 with 0 refs
    items = [
        make_item_with_refs(dataset, "item-3a", item_refs_count=3),
        make_item_with_refs(dataset, "item-3b", item_refs_count=3),
        make_item_with_refs(dataset, "item-1a", item_refs_count=1),
        make_item_with_refs(dataset, "item-1b", item_refs_count=1),
        make_item_with_refs(dataset, "item-0a", item_refs_count=0),
        make_item_with_refs(dataset, "item-0b", item_refs_count=0),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Get all items on page 1 (limit 3)
    res = await async_client.get(
        "/v1/ground-truths",
        params={
            "dataset": dataset,
            "sortBy": "totalReferences",
            "sortOrder": "desc",
            "page": 1,
            "limit": 3,
        },
        headers=user_headers,
    )
    assert res.status_code == 200
    page1 = GroundTruthListResponse.model_validate(res.json())

    # Get page 2
    res = await async_client.get(
        "/v1/ground-truths",
        params={
            "dataset": dataset,
            "sortBy": "totalReferences",
            "sortOrder": "desc",
            "page": 2,
            "limit": 3,
        },
        headers=user_headers,
    )
    assert res.status_code == 200
    page2 = GroundTruthListResponse.model_validate(res.json())

    assert len(page1.items) == 3
    assert len(page2.items) == 3

    # Combine pages and verify no duplicates
    all_ids = [item.id for item in page1.items] + [item.id for item in page2.items]
    assert len(set(all_ids)) == 6, "All 6 items should appear exactly once across pages"

    # Verify page 1 has higher ref counts than page 2
    page1_refs = [item.totalReferences for item in page1.items]
    page2_refs = [item.totalReferences for item in page2.items]
    assert min(page1_refs) >= max(page2_refs), (
        f"Page 1 refs {page1_refs} should be >= page 2 refs {page2_refs}"
    )


@pytest.mark.anyio
async def test_sort_by_total_references_with_status_filter(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort by totalReferences works with status filter."""
    dataset = f"sort-refs-status-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "draft-2", item_refs_count=2),
        make_item_with_refs(dataset, "draft-5", item_refs_count=5),
        make_item_with_refs(dataset, "approved-3", item_refs_count=3),
    ]

    # Create all as draft
    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Approve one item (approved-3)
    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert res.status_code == 200
    all_items = res.json()
    approved_item = next(i for i in all_items if i["id"] == "approved-3")

    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{approved_item['bucket']}/approved-3",
        headers={**user_headers, "If-Match": approved_item["_etag"]},
        json={"status": "approved"},
    )
    assert res.status_code == 200

    # Filter by draft status and sort by totalReferences
    res = await async_client.get(
        "/v1/ground-truths",
        params={
            "dataset": dataset,
            "status": "draft",
            "sortBy": "totalReferences",
            "sortOrder": "desc",
        },
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 2

    # Only draft items (draft-5, draft-2) should be returned, sorted by refs
    ref_counts = [item.totalReferences for item in response_data.items]
    assert ref_counts == [5, 2], f"Expected [5, 2], got {ref_counts}"


@pytest.mark.anyio
async def test_sort_by_total_references_all_zero(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort works when all items have 0 refs (stable by ID)."""
    dataset = f"sort-refs-zeros-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-c", item_refs_count=0),
        make_item_with_refs(dataset, "item-a", item_refs_count=0),
        make_item_with_refs(dataset, "item-b", item_refs_count=0),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "asc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 3

    # All have 0 refs - should be stable sorted by id ASC
    ref_counts = [item.totalReferences for item in response_data.items]
    assert ref_counts == [0, 0, 0]

    # Secondary sort by ID should apply
    ids = [item.id for item in response_data.items]
    assert ids == sorted(ids), f"Expected IDs sorted alphabetically as secondary sort, got {ids}"


@pytest.mark.anyio
async def test_sort_by_total_references_large_counts(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort handles items with many refs correctly."""
    dataset = f"sort-refs-large-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-10", item_refs_count=10),
        make_item_with_refs(dataset, "item-50", item_refs_count=50),
        make_item_with_refs(dataset, "item-25", item_refs_count=25),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 3

    ref_counts = [item.totalReferences for item in response_data.items]
    assert ref_counts == [50, 25, 10], f"Expected [50, 25, 10], got {ref_counts}"


@pytest.mark.anyio
async def test_sort_by_total_references_after_update(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """totalReferences is recalculated on update and sort reflects changes."""
    dataset = f"sort-refs-update-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-to-update", item_refs_count=1),
        make_item_with_refs(dataset, "item-static", item_refs_count=3),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Initial sort - item-static should be first (3 refs vs 1 ref)
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert response_data.items[0].id == "item-static"

    # Get the item to update
    res = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert res.status_code == 200
    all_items = res.json()
    item_to_update = next(i for i in all_items if i["id"] == "item-to-update")

    # Update item-to-update to have 5 refs (more than item-static's 3)
    res = await async_client.put(
        f"/v1/ground-truths/{dataset}/{item_to_update['bucket']}/item-to-update",
        headers={**user_headers, "If-Match": item_to_update["_etag"]},
        json={
            "refs": [
                {"url": "https://example.com/new-ref-1"},
                {"url": "https://example.com/new-ref-2"},
                {"url": "https://example.com/new-ref-3"},
                {"url": "https://example.com/new-ref-4"},
                {"url": "https://example.com/new-ref-5"},
            ]
        },
    )
    assert res.status_code == 200

    # After update - item-to-update should now be first (5 refs vs 3 refs)
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "sortBy": "totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = GroundTruthListResponse.model_validate(res.json())
    assert response_data.items[0].id == "item-to-update"
    assert response_data.items[0].totalReferences == 5


@pytest.mark.anyio
async def test_invalid_sort_field_returns_422(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """API returns 400 for invalid sortBy value."""
    res = await async_client.get(
        "/v1/ground-truths",
        params={"sortBy": "invalidField"},
        headers=user_headers,
    )
    assert res.status_code == 422

    data = res.json()
    detail = data.get("detail")

    assert any(
        ("sortby" in " ".join(map(str, err.get("loc", []))).lower())
        or ("sortby" in err.get("msg", "").lower())
        for err in detail
    ), f"Expected 'sortBy' in validation detail, got: {detail}"
