"""Integration tests for canonical rag-compat reference count behavior."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


def total_refs(item: dict[str, object]) -> int:
    assert "refs" not in item
    assert "totalReferences" not in item
    assert "total_references" not in item
    plugins = item.get("plugins")
    if not isinstance(plugins, dict):
        return 0
    rag_plugin = plugins.get("rag-compat")
    if not isinstance(rag_plugin, dict):
        return 0
    data = rag_plugin.get("data")
    if not isinstance(data, dict):
        return 0
    refs = data.get("references")
    if not isinstance(refs, list):
        return 0
    return len(refs)


def plugin_refs(item: dict[str, object]) -> list[dict[str, object]]:
    plugins = item.get("plugins")
    if not isinstance(plugins, dict):
        return []
    rag_plugin = plugins.get("rag-compat")
    if not isinstance(rag_plugin, dict):
        return []
    data = rag_plugin.get("data")
    if not isinstance(data, dict):
        return []
    refs = data.get("references")
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict)]


def make_history_item(
    *,
    dataset: str,
    item_id: str,
    question: str,
    assistant_refs: list[dict[str, str]] | None = None,
    assistant_msg: str = "Answer",
) -> dict[str, object]:
    item: dict[str, object] = {
        "id": item_id,
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "history": [
            {"role": "user", "msg": question},
            {
                "role": "assistant",
                "msg": assistant_msg,
            },
        ],
    }
    if assistant_refs is not None:
        normalized_refs = [dict(ref, messageIndex=1) for ref in assistant_refs]
        item["plugins"] = {
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": normalized_refs},
            }
        }
    return item


@pytest.mark.anyio
async def test_ground_truth_item_includes_total_references_field(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Verify canonical plugin references are present in response."""
    dataset = f"ref-count-exists-{uuid4().hex[:6]}"

    item = make_history_item(
        dataset=dataset,
        item_id=f"test-{uuid4().hex[:8]}",
        question="Test question?",
        assistant_refs=[],
    )

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 1
    assert "plugins" in response_data["items"][0]
    assert total_refs(response_data["items"][0]) == 0  # No refs yet


@pytest.mark.anyio
async def test_total_references_counts_item_level_refs_only(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with 3 assistant-turn refs → totalReferences=3."""
    dataset = f"ref-count-item-{uuid4().hex[:6]}"

    item = make_history_item(
        dataset=dataset,
        item_id=f"test-{uuid4().hex[:8]}",
        question="Test question?",
        assistant_refs=[
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
            {"url": "https://example.com/3"},
        ],
    )

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 1
    assert response_data["items"][0]["id"].startswith("test-")
    assert total_refs(response_data["items"][0]) == 3
    assert {ref.get("messageIndex") for ref in plugin_refs(response_data["items"][0])} == {1}


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
        "history": [
            {
                "role": "user",
                "msg": "First question",
            },
            {
                "role": "assistant",
                "msg": "First answer",
            },
            {
                "role": "user",
                "msg": "Follow-up question",
            },
            {
                "role": "assistant",
                "msg": "Follow-up answer",
            },
        ],
        "plugins": {
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {
                    "references": [
                        {"url": "https://example.com/turn1-ref1", "messageIndex": 1},
                        {"url": "https://example.com/turn1-ref2", "messageIndex": 1},
                        {"url": "https://example.com/turn2-ref1", "messageIndex": 3},
                    ],
                },
            }
        },
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 1
    assert response_data["items"][0]["id"].startswith("test-")
    assert total_refs(response_data["items"][0]) == 3
    assert {ref.get("messageIndex") for ref in plugin_refs(response_data["items"][0])} == {1, 3}


@pytest.mark.anyio
async def test_total_references_counts_both_levels(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with refs on multiple assistant turns counts all assistant-turn refs."""
    dataset = f"ref-count-both-{uuid4().hex[:6]}"

    item = {
        "id": f"test-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "history": [
            {
                "role": "user",
                "msg": "Question",
            },
            {
                "role": "assistant",
                "msg": "Answer 1",
            },
            {
                "role": "assistant",
                "msg": "Answer 2",
            },
        ],
        "plugins": {
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {
                    "references": [
                        {"url": "https://example.com/history-ref1"},
                        {"url": "https://example.com/history-ref2"},
                        {"url": "https://example.com/history-ref3"},
                    ],
                },
            }
        },
    }

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 1
    assert response_data["items"][0]["id"].startswith("test-")
    assert total_refs(response_data["items"][0]) == 3


@pytest.mark.anyio
async def test_total_references_zero_when_no_refs(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Item with empty refs and no history → totalReferences=0."""
    dataset = f"ref-count-zero-{uuid4().hex[:6]}"

    item = make_history_item(
        dataset=dataset,
        item_id=f"test-{uuid4().hex[:8]}",
        question="Test question?",
        assistant_refs=[],
    )

    res = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 1
    assert response_data["items"][0]["id"].startswith("test-")
    assert total_refs(response_data["items"][0]) == 0


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
            "history": [
                {"role": "user", "msg": "Question 1?"},
                {
                    "role": "assistant",
                    "msg": "Answer 1",
                },
            ],
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "version": "1.0",
                    "data": {"references": [{"url": "https://example.com/1"}]},
                }
            },
        },
        {
            "id": f"item2-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "history": [
                {"role": "user", "msg": "Question 2?"},
                {
                    "role": "assistant",
                    "msg": "Answer 2",
                },
                {
                    "role": "assistant",
                    "msg": "Follow up answer",
                },
            ],
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "version": "1.0",
                    "data": {
                        "references": [
                            {"url": "https://example.com/2a"},
                            {"url": "https://example.com/2c"},
                        ],
                    },
                }
            },
        },
        {
            "id": f"item3-{uuid4().hex[:8]}",
            "datasetName": dataset,
            "bucket": "00000000-0000-0000-0000-000000000000",
            "history": [
                {"role": "user", "msg": "Question 3?"},
                {"role": "assistant", "msg": "Answer 3"},
            ],
        },
    ]

    res = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert res.status_code == 200

    res = await async_client.get(
        "/v1/ground-truths", params={"dataset": dataset}, headers=user_headers
    )
    assert res.status_code == 200

    response_data = res.json()
    assert len(response_data["items"]) == 3

    # Find items by question text to verify independent counts
    items_by_question = {
        next(turn["msg"] for turn in item["history"] if turn["role"] == "user"): item
        for item in response_data["items"]
    }

    assert set(items_by_question.keys()) == {"Question 1?", "Question 2?", "Question 3?"}
    assert total_refs(items_by_question["Question 1?"]) == 1
    assert total_refs(items_by_question["Question 2?"]) == 2
    assert total_refs(items_by_question["Question 3?"]) == 0
