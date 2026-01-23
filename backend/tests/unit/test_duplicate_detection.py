"""Unit tests for duplicate detection service."""

import pytest
from app.services.duplicate_detection_service import (
    DuplicateWarning,
    _normalize_text,
    _get_question_text,
    _items_are_duplicates,
    detect_duplicates_for_item,
    detect_duplicates_for_bulk_items,
)
from app.domain.models import GroundTruthItem
from app.domain.enums import GroundTruthStatus


def test_normalize_text_basic():
    """Test basic text normalization."""
    assert _normalize_text("Hello World") == "hello world"
    assert _normalize_text("  Multiple   Spaces  ") == "multiple spaces"
    assert _normalize_text("Case\nWith\tWhitespace") == "case with whitespace"


def test_normalize_text_none_and_empty():
    """Test normalization with None and empty strings."""
    assert _normalize_text(None) == ""
    assert _normalize_text("") == ""
    assert _normalize_text("   ") == ""


def test_get_question_text_edited_preferred():
    """Test that edited question is preferred over synth question."""
    item = GroundTruthItem(
        id="test-1",
        datasetName="test",
        synth_question="Original question",
        edited_question="Edited question",
        status=GroundTruthStatus.draft,
    )
    assert _get_question_text(item) == "Edited question"


def test_get_question_text_synth_fallback():
    """Test fallback to synth question when edited is missing."""
    item = GroundTruthItem(
        id="test-1",
        datasetName="test",
        synth_question="Original question",
        status=GroundTruthStatus.draft,
    )
    assert _get_question_text(item) == "Original question"


def test_items_are_duplicates_exact_question_match():
    """Test detection of exact question match."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="What is the capital of France?",
        status=GroundTruthStatus.draft,
    )
    approved = GroundTruthItem(
        id="approved-1",
        datasetName="test",
        synth_question="WHAT IS THE CAPITAL OF FRANCE?",  # Different case
        status=GroundTruthStatus.approved,
    )
    
    is_dup, reason = _items_are_duplicates(draft, approved)
    assert is_dup
    assert reason == "exact question match"


def test_items_are_duplicates_question_and_answer_match():
    """Test detection with both question and answer match."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="What is 2+2?",
        answer="The answer is 4",
        status=GroundTruthStatus.draft,
    )
    approved = GroundTruthItem(
        id="approved-1",
        datasetName="test",
        synth_question="what is 2+2?",
        answer="THE ANSWER IS 4",
        status=GroundTruthStatus.approved,
    )
    
    is_dup, reason = _items_are_duplicates(draft, approved)
    assert is_dup
    assert reason == "exact question and answer match"


def test_items_are_duplicates_whitespace_normalized():
    """Test that whitespace differences don't prevent match."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="What   is\n\nthe    answer?",
        status=GroundTruthStatus.draft,
    )
    approved = GroundTruthItem(
        id="approved-1",
        datasetName="test",
        synth_question="What is the answer?",
        status=GroundTruthStatus.approved,
    )
    
    is_dup, reason = _items_are_duplicates(draft, approved)
    assert is_dup
    assert "question match" in reason


def test_items_are_not_duplicates_different_questions():
    """Test that different questions are not flagged."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="What is the capital of France?",
        status=GroundTruthStatus.draft,
    )
    approved = GroundTruthItem(
        id="approved-1",
        datasetName="test",
        synth_question="What is the capital of Germany?",
        status=GroundTruthStatus.approved,
    )
    
    is_dup, reason = _items_are_duplicates(draft, approved)
    assert not is_dup
    assert reason == ""


def test_items_are_not_duplicates_missing_question():
    """Test that items without questions are not flagged."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="",
        status=GroundTruthStatus.draft,
    )
    approved = GroundTruthItem(
        id="approved-1",
        datasetName="test",
        synth_question="What is the answer?",
        status=GroundTruthStatus.approved,
    )
    
    is_dup, reason = _items_are_duplicates(draft, approved)
    assert not is_dup


def test_detect_duplicates_for_item_finds_match():
    """Test detecting duplicates for a single item."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="What is Python?",
        status=GroundTruthStatus.draft,
    )
    approved_items = [
        GroundTruthItem(
            id="approved-1",
            datasetName="test",
            synth_question="What is Java?",
            status=GroundTruthStatus.approved,
        ),
        GroundTruthItem(
            id="approved-2",
            datasetName="test",
            synth_question="What is Python?",
            status=GroundTruthStatus.approved,
        ),
    ]
    
    warnings = detect_duplicates_for_item(draft, approved_items)
    assert len(warnings) == 1
    assert warnings[0].item_id == "draft-1"
    assert warnings[0].duplicate_id == "approved-2"
    assert "python" in warnings[0].duplicate_question.lower()


def test_detect_duplicates_for_item_respects_max_results():
    """Test that max_results limit is enforced."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="Common question",
        status=GroundTruthStatus.draft,
    )
    approved_items = [
        GroundTruthItem(
            id=f"approved-{i}",
            datasetName="test",
            synth_question="Common question",
            status=GroundTruthStatus.approved,
        )
        for i in range(10)
    ]
    
    warnings = detect_duplicates_for_item(draft, approved_items, max_results=2)
    assert len(warnings) == 2


def test_detect_duplicates_for_item_ignores_non_approved():
    """Test that non-approved items are ignored."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="What is the answer?",
        status=GroundTruthStatus.draft,
    )
    other_items = [
        GroundTruthItem(
            id="draft-2",
            datasetName="test",
            synth_question="What is the answer?",
            status=GroundTruthStatus.draft,  # Not approved
        ),
        GroundTruthItem(
            id="deleted-1",
            datasetName="test",
            synth_question="What is the answer?",
            status=GroundTruthStatus.deleted,  # Not approved
        ),
    ]
    
    warnings = detect_duplicates_for_item(draft, other_items)
    assert len(warnings) == 0


def test_detect_duplicates_for_item_ignores_self():
    """Test that an item is not flagged as duplicate of itself."""
    item = GroundTruthItem(
        id="same-id",
        datasetName="test",
        synth_question="What is the answer?",
        status=GroundTruthStatus.approved,
    )
    
    # Check item against itself
    warnings = detect_duplicates_for_item(item, [item])
    assert len(warnings) == 0


def test_detect_duplicates_for_bulk_items():
    """Test bulk duplicate detection."""
    draft_items = [
        GroundTruthItem(
            id="draft-1",
            datasetName="test",
            synth_question="What is Python?",
            status=GroundTruthStatus.draft,
        ),
        GroundTruthItem(
            id="draft-2",
            datasetName="test",
            synth_question="What is Java?",
            status=GroundTruthStatus.draft,
        ),
    ]
    approved_items = [
        GroundTruthItem(
            id="approved-1",
            datasetName="test",
            synth_question="What is Python?",
            status=GroundTruthStatus.approved,
        ),
        GroundTruthItem(
            id="approved-2",
            datasetName="test",
            synth_question="What is C++?",
            status=GroundTruthStatus.approved,
        ),
    ]
    
    warnings = detect_duplicates_for_bulk_items(draft_items, approved_items)
    assert len(warnings) == 1
    assert warnings[0].item_id == "draft-1"
    assert warnings[0].duplicate_id == "approved-1"


def test_detect_duplicates_for_bulk_items_only_checks_drafts():
    """Test that only draft items are checked for duplicates."""
    items = [
        GroundTruthItem(
            id="approved-new",
            datasetName="test",
            synth_question="What is Python?",
            status=GroundTruthStatus.approved,  # Not a draft
        ),
        GroundTruthItem(
            id="draft-1",
            datasetName="test",
            synth_question="What is Java?",
            status=GroundTruthStatus.draft,
        ),
    ]
    approved_items = [
        GroundTruthItem(
            id="approved-1",
            datasetName="test",
            synth_question="What is Python?",
            status=GroundTruthStatus.approved,
        ),
    ]
    
    warnings = detect_duplicates_for_bulk_items(items, approved_items)
    # Should not flag approved-new as duplicate of approved-1
    assert len(warnings) == 0


def test_duplicate_warning_model():
    """Test DuplicateWarning model serialization."""
    warning = DuplicateWarning(
        item_id="draft-1",
        duplicate_id="approved-1",
        duplicate_question="What is Python?",
        duplicate_status="approved",
        match_reason="exact question match",
    )
    
    data = warning.model_dump(by_alias=True)
    assert data["itemId"] == "draft-1"
    assert data["duplicateId"] == "approved-1"
    assert data["duplicateQuestion"] == "What is Python?"
    assert data["duplicateStatus"] == "approved"
    assert data["matchReason"] == "exact question match"


def test_detect_duplicates_uses_edited_question():
    """Test that edited question is used when present."""
    draft = GroundTruthItem(
        id="draft-1",
        datasetName="test",
        synth_question="Original question",
        edited_question="What is the edited question?",
        status=GroundTruthStatus.draft,
    )
    approved = GroundTruthItem(
        id="approved-1",
        datasetName="test",
        synth_question="Different original",
        edited_question="What is the edited question?",
        status=GroundTruthStatus.approved,
    )
    
    warnings = detect_duplicates_for_item(draft, [approved])
    assert len(warnings) == 1
    assert warnings[0].duplicate_id == "approved-1"
