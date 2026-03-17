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


def make_item_with_refs(
    dataset: str,
    item_id: str,
    *,
    assistant_refs_count: int = 0,
    history_refs_counts: list[int] | None = None,
) -> dict:
    """Create a test item with specified reference counts.

    Args:
        dataset: Dataset name
        item_id: Item ID
        assistant_refs_count: Number of refs on a base assistant turn
        history_refs_counts: List of ref counts per history turn (None = no history)

    Returns:
        Item dict for API submission
    """
    item: dict = {
        "id": item_id,
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "history": [
            {"role": "user", "msg": f"Question for {item_id}?"},
            {"role": "assistant", "msg": f"Answer for {item_id}"},
        ],
    }

    # Keep history as plain role/msg entries and store retrieval refs in rag-compat plugin payload.
    total_refs = assistant_refs_count

    # Add history turns if specified
    if history_refs_counts:
        history = [{"role": "user", "msg": f"Question for {item_id}?"}]
        for turn_idx, ref_count in enumerate(history_refs_counts):
            # Assistant turn with refs
            turn: dict = {
                "role": "assistant",
                "msg": f"Turn {turn_idx} answer",
            }
            history.append(turn)
        item["history"] = history
        total_refs = sum(history_refs_counts)

    if total_refs > 0:
        item["plugins"] = {
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {
                    "totalReferences": total_refs,
                    "refs": [
                        {"url": f"https://example.com/{item_id}/ref-{i}"} for i in range(total_refs)
                    ]
                },
            }
        }

    return item


@pytest.mark.anyio
async def test_sort_by_total_references_descending(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort by totalReferences DESC returns items with most refs first."""
    dataset = f"sort-refs-desc-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-0-refs", assistant_refs_count=0),
        make_item_with_refs(dataset, "item-3-refs", assistant_refs_count=3),
        make_item_with_refs(dataset, "item-1-ref", assistant_refs_count=1),
        make_item_with_refs(dataset, "item-5-refs", assistant_refs_count=5),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 4

    item_ids = [item["id"] for item in response_data["items"]]
    assert item_ids == [
        "item-5-refs",
        "item-3-refs",
        "item-1-ref",
        "item-0-refs",
    ]


@pytest.mark.anyio
async def test_sort_by_total_references_ascending(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort by totalReferences ASC returns items with fewest refs first."""
    dataset = f"sort-refs-asc-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-3-refs", assistant_refs_count=3),
        make_item_with_refs(dataset, "item-0-refs", assistant_refs_count=0),
        make_item_with_refs(dataset, "item-5-refs", assistant_refs_count=5),
        make_item_with_refs(dataset, "item-1-ref", assistant_refs_count=1),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "asc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 4

    item_ids = [item["id"] for item in response_data["items"]]
    assert item_ids == [
        "item-0-refs",
        "item-1-ref",
        "item-3-refs",
        "item-5-refs",
    ]


@pytest.mark.anyio
async def test_sort_by_total_references_with_history_refs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort works correctly when refs come from history turns."""
    dataset = f"sort-refs-history-{uuid4().hex[:6]}"

    items = [
        # Item with base assistant refs only (2 refs)
        make_item_with_refs(dataset, "item-level-2", assistant_refs_count=2),
        # Item with only history refs (3 refs across turns)
        make_item_with_refs(dataset, "history-3", history_refs_counts=[1, 2]),
        # Item with no refs (0 refs)
        make_item_with_refs(dataset, "no-refs", assistant_refs_count=0),
        # Item with history refs only (4 refs)
        make_item_with_refs(dataset, "history-4-override", history_refs_counts=[2, 2]),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 4

    # Expected order: history-4-override (4), history-3 (3), item-level-2 (2), no-refs (0)
    item_ids = [item["id"] for item in response_data["items"]]
    assert len({item["id"] for item in response_data["items"]}) == 4
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
        make_item_with_refs(dataset, "item-3a", assistant_refs_count=3),
        make_item_with_refs(dataset, "item-3b", assistant_refs_count=3),
        make_item_with_refs(dataset, "item-1a", assistant_refs_count=1),
        make_item_with_refs(dataset, "item-1b", assistant_refs_count=1),
        make_item_with_refs(dataset, "item-0a", assistant_refs_count=0),
        make_item_with_refs(dataset, "item-0b", assistant_refs_count=0),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Get all items on page 1 (limit 3)
    res = await async_client.get(
        "/v1/ground-truths",
        params={
            "dataset": dataset,
            "pluginSort": "rag-compat:totalReferences",
            "sortOrder": "desc",
            "page": 1,
            "limit": 3,
        },
        headers=user_headers,
    )
    assert res.status_code == 200
    page1 = res.json()

    # Get page 2
    res = await async_client.get(
        "/v1/ground-truths",
        params={
            "dataset": dataset,
            "pluginSort": "rag-compat:totalReferences",
            "sortOrder": "desc",
            "page": 2,
            "limit": 3,
        },
        headers=user_headers,
    )
    assert res.status_code == 200
    page2 = res.json()

    assert len(page1["items"]) == 3
    assert len(page2["items"]) == 3

    # Combine pages and verify no duplicates
    all_ids = [item["id"] for item in page1["items"]] + [item["id"] for item in page2["items"]]
    assert len(set(all_ids)) == 6, "All 6 items should appear exactly once across pages"

    # Pagination should be non-overlapping and preserve primary sort direction.
    assert set(page1_item_ids := [item["id"] for item in page1["items"]]).isdisjoint(
        set(page2_item_ids := [item["id"] for item in page2["items"]])
    )
    expected_counts = {
        "item-3a": 3,
        "item-3b": 3,
        "item-1a": 1,
        "item-1b": 1,
        "item-0a": 0,
        "item-0b": 0,
    }
    combined_counts = [expected_counts[item_id] for item_id in [*page1_item_ids, *page2_item_ids]]
    assert combined_counts == sorted(combined_counts, reverse=True)


@pytest.mark.anyio
async def test_sort_by_total_references_with_status_filter(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort by totalReferences works with status filter."""
    dataset = f"sort-refs-status-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "draft-2", assistant_refs_count=2),
        make_item_with_refs(dataset, "draft-5", assistant_refs_count=5),
        make_item_with_refs(dataset, "approved-3", assistant_refs_count=3),
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
            "pluginSort": "rag-compat:totalReferences",
            "sortOrder": "desc",
        },
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 2

    # Only draft items should be returned.
    assert {item["id"] for item in response_data["items"]} == {"draft-2", "draft-5"}


@pytest.mark.anyio
async def test_sort_by_total_references_all_zero(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort works when all items have 0 refs (stable by ID)."""
    dataset = f"sort-refs-zeros-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-c", assistant_refs_count=0),
        make_item_with_refs(dataset, "item-a", assistant_refs_count=0),
        make_item_with_refs(dataset, "item-b", assistant_refs_count=0),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "asc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 3

    # Secondary sort by ID should apply
    ids = [item["id"] for item in response_data["items"]]
    assert ids == sorted(ids), f"Expected IDs sorted alphabetically as secondary sort, got {ids}"


@pytest.mark.anyio
async def test_sort_by_total_references_large_counts(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Sort handles items with many refs correctly."""
    dataset = f"sort-refs-large-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-10", assistant_refs_count=10),
        make_item_with_refs(dataset, "item-50", assistant_refs_count=50),
        make_item_with_refs(dataset, "item-25", assistant_refs_count=25),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 3

    item_ids = [item["id"] for item in response_data["items"]]
    assert item_ids == ["item-50", "item-25", "item-10"]


@pytest.mark.anyio
async def test_sort_by_total_references_after_update(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """totalReferences is recalculated on update and sort reflects changes."""
    dataset = f"sort-refs-update-{uuid4().hex[:6]}"

    items = [
        make_item_with_refs(dataset, "item-to-update", assistant_refs_count=1),
        make_item_with_refs(dataset, "item-static", assistant_refs_count=3),
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    # Initial sort - item-static should be first (3 refs vs 1 ref)
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = res.json()
    assert response_data["items"][0]["id"] == "item-static"

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
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "version": "1.0",
                    "data": {
                        "totalReferences": 5,
                        "refs": [
                            {"url": "https://example.com/new-ref-1"},
                            {"url": "https://example.com/new-ref-2"},
                            {"url": "https://example.com/new-ref-3"},
                            {"url": "https://example.com/new-ref-4"},
                            {"url": "https://example.com/new-ref-5"},
                        ]
                    },
                }
            }
        },
    )
    assert res.status_code == 200

    # After update - item-to-update should now be first (5 refs vs 3 refs)
    res = await async_client.get(
        "/v1/ground-truths",
        params={"dataset": dataset, "pluginSort": "rag-compat:totalReferences", "sortOrder": "desc"},
        headers=user_headers,
    )
    assert res.status_code == 200
    response_data = res.json()
    assert response_data["items"][0]["id"] == "item-to-update"


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
