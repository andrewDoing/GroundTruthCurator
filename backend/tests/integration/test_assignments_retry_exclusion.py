"""Integration tests for self-serve assignment retry with exclusion.

Tests the bug fix for SA-406: when self_assign retries to get more items after
failing to assign some candidates (due to concurrency or other reasons), it should
exclude items that were already attempted, preventing infinite loops of trying
to assign the same items repeatedly.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from pydantic.type_adapter import TypeAdapter
import pytest

from app.domain.models import GroundTruthItem
from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo


def make_unassigned_item(dataset: str, item_id: str | None = None) -> dict[str, Any]:
    """Create a test ground truth item in unassigned state."""
    return {
        "id": item_id or f"gt-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": str(UUID("00000000-0000-0000-0000-000000000000")),
        "status": "draft",
        "samplingBucket": 0,
        "synthQuestion": f"Question about {uuid4().hex[:4]}?",
        "assignedTo": None,
        "refs": [],
        "manualTags": ["source:synthetic", "split:test"],
    }


@pytest.mark.anyio
async def test_sample_unassigned_exclude_ids_prevents_resampling(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that sample_unassigned with exclude_ids prevents re-sampling excluded items.

    **Core SA-406 bug fix test**: Validates that the exclude_ids parameter prevents
    the infinite loop bug where retry would keep sampling the same items that failed
    to assign.

    Without exclude_ids, if items couldn't be assigned (e.g., due to concurrent
    assignment or conflicts), the retry would sample the same failed items repeatedly.
    With exclude_ids, retry samples different items from the pool.
    """
    dataset = f"exclude-{uuid4().hex[:6]}"

    # Import 20 items
    items = [make_unassigned_item(dataset, f"gt-{i:02d}") for i in range(20)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    from app.container import container

    repo = container.repo
    assert isinstance(repo, CosmosGroundTruthRepo)

    user_id = "tester@example.com"

    # First sample: get 10 items
    first_sample = await repo.sample_unassigned(user_id=user_id, limit=10)
    assert len(first_sample) == 10
    first_ids = {item.id for item in first_sample}

    # Second sample with exclusions: get 10 different items
    # This simulates the retry scenario where we exclude items that failed to assign
    second_sample = await repo.sample_unassigned(
        user_id=user_id, limit=10, exclude_ids=list(first_ids)
    )
    assert len(second_sample) == 10
    second_ids = {item.id for item in second_sample}

    # Core assertion: The two samples must be completely disjoint
    # This proves exclude_ids works and prevents the infinite loop bug
    overlap = first_ids.intersection(second_ids)
    assert not overlap, f"Bug: exclude_ids failed to prevent resampling. Overlap: {overlap}"

    # Verify we got all 20 unique items
    all_sampled_ids = first_ids.union(second_ids)
    assert len(all_sampled_ids) == 20


@pytest.mark.anyio
async def test_skipped_items_excluded_from_user_resampling(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that skipped items are properly excluded when user requests more items.

    **Edge case test**: When a user skips an item, subsequent self-serve requests
    should not return that skipped item. The query logic correctly filters out items
    where status='skipped' AND assignedTo=current_user.

    This validates the improved Cosmos query logic from SA-406 that properly handles
    skipped items to avoid showing users items they've explicitly skipped.
    """
    dataset = f"skip-{uuid4().hex[:6]}"

    # Import 5 items
    items = [make_unassigned_item(dataset) for _ in range(5)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # User assigns 2 items
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 2}, headers=user_headers
    )
    assert r.status_code == 200
    first_batch = TypeAdapter(list[GroundTruthItem]).validate_python(r.json().get("assigned") or [])
    assert len(first_batch) == 2

    # Skip one item
    skipped_item = first_batch[0]
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{skipped_item.bucket}/{skipped_item.id}",
        json={"status": "skipped", "etag": skipped_item.etag},
        headers=user_headers,
    )
    assert r.status_code == 200

    # Request 3 more items - should get the non-skipped item + 2 new ones
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 3}, headers=user_headers
    )
    assert r.status_code == 200
    second_batch = TypeAdapter(list[GroundTruthItem]).validate_python(
        r.json().get("assigned") or []
    )
    assert len(second_batch) == 3

    second_batch_ids = {item.id for item in second_batch}
    non_skipped_item = first_batch[1]

    # Core assertions: skipped item not returned, non-skipped item is returned
    assert skipped_item.id not in second_batch_ids, "Bug: Skipped item was resampled"
    assert non_skipped_item.id in second_batch_ids, "Non-skipped item should be included"

    # Should have 2 new items (not from first batch)
    first_batch_ids = {item.id for item in first_batch}
    new_items = second_batch_ids - first_batch_ids
    assert len(new_items) == 2
