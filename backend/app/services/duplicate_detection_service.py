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

import json
import re
from typing import Sequence

from pydantic import BaseModel, Field, ConfigDict

from app.domain.models import AgenticGroundTruthEntry
from app.domain.enums import GroundTruthStatus


class DuplicateWarning(BaseModel):
    """Warning about a likely duplicate of an approved item."""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(description="Draft item identifier", alias="itemId")
    duplicate_id: str = Field(
        description="ID of the likely duplicate approved item", alias="duplicateId"
    )
    duplicate_question: str = Field(
        description="Question text from the duplicate item", alias="duplicateQuestion"
    )
    duplicate_status: str = Field(
        description="Status of the duplicate item", alias="duplicateStatus"
    )
    match_reason: str = Field(
        description="Why this was flagged as a duplicate (e.g., 'exact question match', 'question and answer match')",
        alias="matchReason",
    )


def _normalize_text(text: str | None) -> str:
    """Normalize text for comparison by removing extra whitespace and lowercasing."""
    if not text:
        return ""
    # Replace multiple whitespace with single space, strip, lowercase
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized


def _get_question_text(item: AgenticGroundTruthEntry) -> str:
    """Get the effective question text (edited or synth)."""
    return item.edited_question or item.synth_question or ""


def _serialize_generic_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseModel):
        value = value.model_dump(by_alias=True, exclude_none=True)
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _prune_empty(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        value = value.model_dump(by_alias=True, exclude_none=True)
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        pruned = {
            key: pruned_value
            for key, nested in value.items()
            if (pruned_value := _prune_empty(nested)) is not None
        }
        return pruned or None
    if isinstance(value, list):
        pruned = [
            pruned_value for nested in value if (pruned_value := _prune_empty(nested)) is not None
        ]
        return pruned or None
    return value


def _history_signature(item: AgenticGroundTruthEntry) -> str:
    history = item.history or []
    return _normalize_text(
        "\n".join(f"{entry.role}:{entry.msg}" for entry in history if entry.role and entry.msg)
    )


def _generic_signature(item: AgenticGroundTruthEntry) -> str:
    structured_payload = _prune_empty(
        {
            "scenarioId": item.scenario_id,
            "contextEntries": item.context_entries,
            "toolCalls": item.tool_calls,
            "expectedTools": item.expected_tools,
            "feedback": item.feedback,
            "metadata": item.metadata,
            "plugins": item.plugins,
            "traceIds": item.trace_ids,
            "tracePayload": item.trace_payload,
        }
    )
    if structured_payload is None:
        return ""
    return _normalize_text(_serialize_generic_value(structured_payload))


def _items_are_duplicates(
    draft: AgenticGroundTruthEntry, approved: AgenticGroundTruthEntry
) -> tuple[bool, str]:
    """Check if two items are likely duplicates.

    Returns:
        (is_duplicate, match_reason) tuple
    """
    draft_question = _normalize_text(_get_question_text(draft))
    approved_question = _normalize_text(_get_question_text(approved))

    # Check for exact question match when both items expose question text
    if draft_question and approved_question and draft_question == approved_question:
        # Also check answer for stronger signal
        draft_answer = _normalize_text(draft.answer)
        approved_answer = _normalize_text(approved.answer)

        if draft_answer and approved_answer and draft_answer == approved_answer:
            return (True, "exact question and answer match")
        return (True, "exact question match")

    draft_history = _history_signature(draft)
    approved_history = _history_signature(approved)
    if draft_history and draft_history == approved_history:
        draft_generic = _generic_signature(draft)
        approved_generic = _generic_signature(approved)
        if draft_generic and draft_generic == approved_generic:
            return (True, "exact history and generic fields match")
        return (True, "exact history match")

    draft_generic = _generic_signature(draft)
    approved_generic = _generic_signature(approved)
    if draft_generic and draft_generic == approved_generic:
        return (True, "exact generic fields match")

    return (False, "")


def detect_duplicates_for_item(
    draft_item: AgenticGroundTruthEntry,
    approved_items: Sequence[AgenticGroundTruthEntry],
    max_results: int = 3,
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
                    itemId=draft_item.id,
                    duplicateId=approved.id,
                    duplicateQuestion=_get_question_text(approved),
                    duplicateStatus=approved.status.value,
                    matchReason=reason,
                )
            )

            # Limit results for usability
            if len(warnings) >= max_results:
                break

    return warnings


def detect_duplicates_for_bulk_items(
    draft_items: Sequence[AgenticGroundTruthEntry],
    approved_items: Sequence[AgenticGroundTruthEntry],
    max_results_per_item: int = 3,
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
