"""Test helpers for creating AgenticGroundTruthEntry fixtures.

After Phase 6: canonical state is history[]; question/answer are derived from
history and plugin-owned reference compatibility lives in
plugins["rag-compat"].data.references.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.enums import GroundTruthStatus
from app.domain.models import AgenticGroundTruthEntry


def make_test_entry(
    *,
    id: str = "test-item",
    dataset_name: str = "test-dataset",
    status: GroundTruthStatus = GroundTruthStatus.draft,
    history: list[dict[str, Any]] | None = None,
    synth_question: str | None = None,
    edited_question: str | None = None,
    answer: str | None = None,
    refs: list[dict[str, Any]] | None = None,
    manual_tags: list[str] | None = None,
    comment: str = "",
    reviewed_at: datetime | None = None,
    **kwargs: Any,
) -> AgenticGroundTruthEntry:
    """Create a test entry with canonical history-based construction.

    Args:
        id: Item ID (default: "test-item")
        dataset_name: Dataset name (default: "test-dataset")
        status: Item status (default: draft)
        history: Explicit history array. If None and question/answer inputs are provided,
                  a simple Q&A history will be auto-generated.
        synth_question: Fallback question text used when edited_question is absent
        edited_question: Preferred question text for generated history
        answer: Answer text used for generated history
        refs: References stored in rag-compat plugin data
        manual_tags: Manual tags list
        comment: Item comment
        reviewed_at: Review timestamp
        **kwargs: Additional fields to pass to AgenticGroundTruthEntry

    Returns:
        AgenticGroundTruthEntry: A properly constructed test entry

    Examples:
        # Simple Q&A entry:
        entry = make_test_entry(
            id="item-1",
            synth_question="What is X?",
            answer="X is Y"
        )

        # Entry with explicit history:
        entry = make_test_entry(
            id="item-2",
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi there"}
            ]
        )

        # Entry with refs in rag-compat plugin:
        entry = make_test_entry(
            id="item-3",
            synth_question="What?",
            answer="Answer",
            refs=[{"url": "https://example.com", "title": "Example"}]
        )
    """
    # Build base payload
    payload: dict[str, Any] = {
        "id": id,
        "datasetName": dataset_name,
        "status": status.value if isinstance(status, GroundTruthStatus) else status,
        "manualTags": manual_tags or [],
        "comment": comment,
        **kwargs,
    }

    if reviewed_at is not None:
        payload["reviewedAt"] = (
            reviewed_at.isoformat() if isinstance(reviewed_at, datetime) else reviewed_at
        )

    # Handle history construction
    if history is not None:
        # Use explicit history
        payload["history"] = history
    elif edited_question or synth_question or answer:
        # Auto-generate simple Q&A history from legacy-style params
        auto_history: list[dict[str, Any]] = []
        question = edited_question or synth_question
        if question:
            auto_history.append({"role": "user", "msg": question})
        if answer:
            auto_history.append({"role": "assistant", "msg": answer})
        payload["history"] = auto_history

    # Build rag-compat plugin data when references are provided
    rag_compat_data: dict[str, Any] = {}
    if refs is not None:
        rag_compat_data["references"] = [
            ref.model_dump(by_alias=True, exclude_none=True) if hasattr(ref, "model_dump") else ref
            for ref in refs
        ]

    if rag_compat_data:
        payload["plugins"] = {
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": rag_compat_data,
            }
        }

    # Validate and return
    return AgenticGroundTruthEntry.model_validate(payload)


def make_simple_qa_entry(
    question: str,
    answer: str,
    *,
    id: str = "test-item",
    dataset_name: str = "test-dataset",
    refs: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> AgenticGroundTruthEntry:
    """Create a simple Q&A entry (convenience wrapper).

    Args:
        question: The question text
        answer: The answer text
        id: Item ID
        dataset_name: Dataset name
        refs: Optional references
        **kwargs: Additional fields

    Returns:
        AgenticGroundTruthEntry: A test entry with Q&A history
    """
    return make_test_entry(
        id=id,
        dataset_name=dataset_name,
        synth_question=question,
        answer=answer,
        refs=refs,
        **kwargs,
    )


def make_history_entry(
    role: str,
    msg: str,
    refs: list[dict[str, Any]] | None = None,
    expected_behavior: list[str] | None = None,
) -> dict[str, Any]:
    """Create a single history entry dict for use in history arrays.

    Args:
        role: Role (e.g., "user", "assistant")
        msg: Message content
        refs: Optional references for this turn
        expected_behavior: Optional expected behavior annotations

    Returns:
        dict: A history entry dict ready for inclusion in entry.history
    """
    entry: dict[str, Any] = {"role": role, "msg": msg}
    if refs is not None:
        entry["refs"] = refs
    if expected_behavior is not None:
        entry["expectedBehavior"] = expected_behavior
    return entry
