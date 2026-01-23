"""Duplicate detection service for ground truth items.

This service detects likely duplicates of approved items when working with draft items.
Detection is informational only - warnings are returned but do not block writes.

Detection strategy:
- Normalize whitespace and casing for comparison
- Compare editedQuestion or synthQuestion (whichever is present)
- Compare answer content
- Only check against approved items (drafts can have temporary duplicates)
"""

from __future__ import annotations

import re
from typing import Sequence

from pydantic import BaseModel, Field, ConfigDict

from app.domain.models import GroundTruthItem
from app.domain.enums import GroundTruthStatus


class DuplicateWarning(BaseModel):
    """Warning about a likely duplicate of an approved item."""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(description="Draft item identifier", alias="itemId")
    duplicate_id: str = Field(description="ID of the likely duplicate approved item", alias="duplicateId")
    duplicate_question: str = Field(
        description="Question text from the duplicate item",
        alias="duplicateQuestion"
    )
    duplicate_status: str = Field(
        description="Status of the duplicate item",
        alias="duplicateStatus"
    )
    match_reason: str = Field(
        description="Why this was flagged as a duplicate (e.g., 'exact question match', 'question and answer match')",
        alias="matchReason"
    )


def _normalize_text(text: str | None) -> str:
    """Normalize text for comparison by removing extra whitespace and lowercasing."""
    if not text:
        return ""
    # Replace multiple whitespace with single space, strip, lowercase
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized


def _get_question_text(item: GroundTruthItem) -> str:
    """Get the effective question text (edited or synth)."""
    return item.edited_question or item.synth_question or ""


def _items_are_duplicates(draft: GroundTruthItem, approved: GroundTruthItem) -> tuple[bool, str]:
    """Check if two items are likely duplicates.
    
    Returns:
        (is_duplicate, match_reason) tuple
    """
    draft_question = _normalize_text(_get_question_text(draft))
    approved_question = _normalize_text(_get_question_text(approved))
    
    # Must have a question to compare
    if not draft_question or not approved_question:
        return (False, "")
    
    # Check for exact question match
    if draft_question == approved_question:
        # Also check answer for stronger signal
        draft_answer = _normalize_text(draft.answer)
        approved_answer = _normalize_text(approved.answer)
        
        if draft_answer and approved_answer and draft_answer == approved_answer:
            return (True, "exact question and answer match")
        return (True, "exact question match")
    
    return (False, "")


def detect_duplicates_for_item(
    draft_item: GroundTruthItem,
    approved_items: Sequence[GroundTruthItem],
    max_results: int = 3
) -> list[DuplicateWarning]:
    """Detect duplicate approved items for a single draft item.
    
    Args:
        draft_item: The draft item to check
        approved_items: List of approved items to check against
        max_results: Maximum number of duplicate warnings to return
        
    Returns:
        List of DuplicateWarning objects (up to max_results)
    """
    warnings: list[DuplicateWarning] = []
    
    for approved in approved_items:
        # Only check against approved items
        if approved.status != GroundTruthStatus.approved:
            continue
            
        # Don't compare an item to itself
        if draft_item.id == approved.id:
            continue
        
        is_dup, reason = _items_are_duplicates(draft_item, approved)
        if is_dup:
            warnings.append(
                DuplicateWarning(
                    item_id=draft_item.id,
                    duplicate_id=approved.id,
                    duplicate_question=_get_question_text(approved),
                    duplicate_status=approved.status.value,
                    match_reason=reason
                )
            )
            
            # Limit results for usability
            if len(warnings) >= max_results:
                break
    
    return warnings


def detect_duplicates_for_bulk_items(
    draft_items: Sequence[GroundTruthItem],
    approved_items: Sequence[GroundTruthItem],
    max_results_per_item: int = 3
) -> list[DuplicateWarning]:
    """Detect duplicates for multiple draft items against approved items.
    
    This is the main entry point for bulk import duplicate detection.
    
    Args:
        draft_items: List of draft items to check
        approved_items: List of approved items to check against
        max_results_per_item: Maximum warnings per draft item
        
    Returns:
        List of DuplicateWarning objects for all draft items
    """
    all_warnings: list[DuplicateWarning] = []
    
    for draft in draft_items:
        # Only check draft items (don't warn about approved duplicates)
        if draft.status == GroundTruthStatus.draft:
            warnings = detect_duplicates_for_item(draft, approved_items, max_results_per_item)
            all_warnings.extend(warnings)
    
    return all_warnings
