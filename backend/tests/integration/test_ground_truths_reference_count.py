"""Integration tests for totalReferences computed field on GroundTruthItem."""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.domain.models import GroundTruthListResponse


@pytest.mark.anyio
async def test_ground_truth_item_includes_total_references_field(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Verify totalReferences field exists in response."""
    dataset = f"ref-count-exists-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert hasattr(response_data.items[0], "totalReferences")
    assert response_data.items[0].totalReferences == 0  # No refs yet


@pytest.mark.anyio
async def test_total_references_counts_item_level_refs_only(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with 3 item-level refs, no history → totalReferences=3."""
    dataset = f"ref-count-item-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
            {"url": "https://example.com/3"},
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].totalReferences == 3


@pytest.mark.anyio
async def test_total_references_counts_history_level_refs_only(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with no item-level refs, 2 history turns with refs → correct count."""
    dataset = f"ref-count-history-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "history": [
            {
                "role": "user",
                "msg": "First question",
                "refs": None,
            },
            {
                "role": "assistant",
                "msg": "First answer",
                "refs": [
                    {"url": "https://example.com/turn1-ref1"},
                    {"url": "https://example.com/turn1-ref2"},
                ],
            },
            {
                "role": "user",
                "msg": "Follow-up question",
                "refs": None,
            },
            {
                "role": "assistant",
                "msg": "Follow-up answer",
                "refs": [
                    {"url": "https://example.com/turn2-ref1"},
                ],
            },
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    # 2 refs from first assistant turn + 1 ref from second assistant turn = 3 total
    assert response_data.items[0].totalReferences == 3


@pytest.mark.anyio
async def test_total_references_counts_both_levels(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with item-level refs + history turn refs → only history turn refs counted."""
    dataset = f"ref-count-both-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
        "refs": [
            {"url": "https://example.com/item-ref1"},
            {"url": "https://example.com/item-ref2"},
        ],
        "history": [
            {
                "role": "user",
                "msg": "Question",
                "refs": None,
            },
            {
                "role": "assistant",
                "msg": "Answer",
                "refs": [
                    {"url": "https://example.com/history-ref1"},
                    {"url": "https://example.com/history-ref2"},
                    {"url": "https://example.com/history-ref3"},
                ],
            },
        ],
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    # 2 item-level refs , 3 history refs ignore the item-level refs = 3 total
    assert response_data.items[0].totalReferences == 3


@pytest.mark.anyio
async def test_total_references_zero_when_no_refs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with empty refs and no history → totalReferences=0."""
    dataset = f"ref-count-zero-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Test question?",
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 1
    assert response_data.items[0].totalReferences == 0


@pytest.mark.anyio
async def test_total_references_multiple_items_independent(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Multiple items each have correct independent counts."""
    dataset = f"ref-count-multi-{uuid4().hex[:6]}"

    items = [
        {
            "id": f"item1-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Question 1?",
            "refs": [{"url": "https://example.com/1"}],
        },
        {
            "id": f"item2-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Question 2?",
            "refs": [
                {"url": "https://example.com/2a"},
                {"url": "https://example.com/2b"},
            ],
            "history": [
                {"role": "user", "msg": "Follow up"},
                {
                    "role": "assistant",
                    "msg": "Answer",
                    "refs": [{"url": "https://example.com/2c"}],
                },
            ],
        },
        {
            "id": f"item3-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "synthQuestion": "Question 3?",
            # No refs
        },
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = GroundTruthListResponse.model_validate(res.json())
    assert len(response_data.items) == 3

    # Find items by checking synthQuestion to verify independent counts
    items_by_question = {item.synth_question: item for item in response_data.items}

    assert items_by_question["Question 1?"].totalReferences == 1  # 1 item-level ref
    assert (
        items_by_question["Question 2?"].totalReferences == 1
    )  # 2 item-level , 1 history ref then count only history = 1
    assert items_by_question["Question 3?"].totalReferences == 0  # No refs
