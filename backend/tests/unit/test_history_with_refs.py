"""Unit tests for canonical HistoryItem validation semantics."""

import pytest
from pydantic import ValidationError

from app.domain.models import HistoryItem, Reference
from app.domain.enums import HistoryItemRole, ExpectedBehavior


def test_history_item_rejects_refs():
    """HistoryItem rejects legacy refs; refs are plugin-owned canonical data."""
    refs = [
        Reference(url="https://example.com/doc1", content="Content 1"),
        Reference(url="https://example.com/doc2", content="Content 2", bonus=True),
    ]

    with pytest.raises(ValidationError):
        HistoryItem(
            role=HistoryItemRole.assistant,
            msg="Here is the answer based on the documentation.",
            refs=refs,
        )


def test_history_item_without_refs():
    """HistoryItem remains valid with canonical role/msg content only."""
    history_item = HistoryItem(
        role=HistoryItemRole.user,
        msg="What is the answer?",
    )

    assert history_item.role == HistoryItemRole.user
    assert history_item.msg == "What is the answer?"
    assert "refs" not in history_item.model_dump()


def test_history_item_serialization():
    """HistoryItem serialization excludes legacy refs field."""
    history_item = HistoryItem(role=HistoryItemRole.assistant, msg="Answer text")

    # Serialize to dict
    data = history_item.model_dump()

    assert data["role"] == "assistant"
    assert data["msg"] == "Answer text"
    assert "refs" not in data


def test_history_item_deserialization_rejects_refs():
    """HistoryItem rejects dict payloads containing legacy refs."""
    data = {
        "role": "assistant",
        "msg": "Answer text",
        "refs": [
            {"url": "https://example.com/doc1", "content": "Content 1"},
            {"url": "https://example.com/doc2", "content": None, "bonus": True},
        ],
    }

    with pytest.raises(ValidationError):
        HistoryItem(**data)


def test_user_history_item_rejects_refs():
    """User history items also reject legacy refs."""
    user_item = HistoryItem(
        role=HistoryItemRole.user,
        msg="What is this product?",
    )
    assert "refs" not in user_item.model_dump()

    with pytest.raises(ValidationError):
        HistoryItem(
            role=HistoryItemRole.user,
            msg="Based on this document, what is this product?",
            refs=[Reference(url="https://example.com/doc1")],
        )


def test_history_item_with_expected_behavior():
    """Test that HistoryItem can include expected_behavior with multiple values."""
    history_item = HistoryItem(
        role=HistoryItemRole.assistant,
        msg="Here is how you extrude a shape in a CAD application version 9...",
        expectedBehavior=[ExpectedBehavior.tool_search, ExpectedBehavior.generation_answer],
    )

    assert history_item.expected_behavior is not None
    assert len(history_item.expected_behavior) == 2
    assert ExpectedBehavior.tool_search in history_item.expected_behavior
    assert ExpectedBehavior.generation_answer in history_item.expected_behavior


def test_history_item_expected_behavior_serialization():
    """Test that expected_behavior serializes to wire format (expectedBehavior)."""
    history_item = HistoryItem(
        role=HistoryItemRole.assistant,
        msg="Are you trying to install using the Tool Manager or command line?",
        expectedBehavior=[ExpectedBehavior.tool_search, ExpectedBehavior.generation_clarification],
    )

    # Serialize to dict using by_alias=True to match wire format
    data = history_item.model_dump(by_alias=True)

    assert data["expectedBehavior"] is not None
    assert len(data["expectedBehavior"]) == 2
    assert "tool:search" in data["expectedBehavior"]
    assert "generation:clarification" in data["expectedBehavior"]


def test_history_item_expected_behavior_deserialization():
    """Test that HistoryItem can be created from dict with expectedBehavior."""
    data = {
        "role": "assistant",
        "msg": "I'm sorry, I can only help with questions related to this product.",
        "expectedBehavior": ["generation:out-of-domain"],
    }

    history_item = HistoryItem(**data)

    assert history_item.expected_behavior is not None
    assert len(history_item.expected_behavior) == 1
    assert history_item.expected_behavior[0] == ExpectedBehavior.generation_out_of_domain
