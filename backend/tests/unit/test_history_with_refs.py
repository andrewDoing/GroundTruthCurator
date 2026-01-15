"""
Unit tests for HistoryItem with refs field.
Validates that history items can store references alongside agent messages.
"""

from app.domain.models import HistoryItem, Reference
from app.domain.enums import HistoryItemRole, ExpectedBehavior


def test_history_item_with_refs():
    """Test that HistoryItem can include refs."""
    refs = [
        Reference(url="https://example.com/doc1", content="Content 1"),
        Reference(url="https://example.com/doc2", content="Content 2", bonus=True),
    ]

    history_item = HistoryItem(
        role=HistoryItemRole.assistant,
        msg="Here is the answer based on the documentation.",
        refs=refs,
    )

    assert history_item.role == HistoryItemRole.assistant
    assert history_item.msg == "Here is the answer based on the documentation."
    assert history_item.refs is not None
    assert len(history_item.refs) == 2
    assert history_item.refs[0].url == "https://example.com/doc1"
    assert history_item.refs[1].bonus is True


def test_history_item_without_refs():
    """Test that refs is optional in HistoryItem."""
    history_item = HistoryItem(
        role=HistoryItemRole.user,
        msg="What is the answer?",
    )

    assert history_item.role == HistoryItemRole.user
    assert history_item.msg == "What is the answer?"
    assert history_item.refs is None


def test_history_item_serialization():
    """Test that HistoryItem serializes correctly with refs."""
    refs = [
        Reference(url="https://example.com/doc1", content="Content 1"),
    ]

    history_item = HistoryItem(
        role=HistoryItemRole.assistant,
        msg="Answer text",
        refs=refs,
    )

    # Serialize to dict
    data = history_item.model_dump()

    assert data["role"] == "assistant"
    assert data["msg"] == "Answer text"
    assert data["refs"] is not None
    assert len(data["refs"]) == 1
    assert data["refs"][0]["url"] == "https://example.com/doc1"


def test_history_item_deserialization():
    """Test that HistoryItem can be created from dict with refs."""
    data = {
        "role": "assistant",
        "msg": "Answer text",
        "refs": [
            {"url": "https://example.com/doc1", "content": "Content 1"},
            {"url": "https://example.com/doc2", "content": None, "bonus": True},
        ],
    }

    history_item = HistoryItem(**data)

    assert history_item.role == HistoryItemRole.assistant
    assert history_item.msg == "Answer text"
    assert history_item.refs is not None
    assert len(history_item.refs) == 2
    assert history_item.refs[0].url == "https://example.com/doc1"
    assert history_item.refs[1].bonus is True


def test_user_history_item_typically_no_refs():
    """Test that user messages typically don't have refs (but could)."""
    # User message without refs (typical)
    user_item = HistoryItem(
        role=HistoryItemRole.user,
        msg="What is this product?",
    )
    assert user_item.refs is None

    # User message with refs (uncommon but allowed)
    user_item_with_refs = HistoryItem(
        role=HistoryItemRole.user,
        msg="Based on this document, what is this product?",
        refs=[Reference(url="https://example.com/doc1")],
    )
    assert user_item_with_refs.refs is not None
    assert len(user_item_with_refs.refs) == 1


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
