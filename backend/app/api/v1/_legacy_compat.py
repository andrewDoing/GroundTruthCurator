from __future__ import annotations

# Legacy compatibility helpers for API endpoints that still accept raw payloads
# with old RAG-era field names (editedQuestion, answer, refs, etc.).
# Retained because bulk import and PATCH handlers coerce untyped history entries
# and apply legacy field updates from callers that haven't migrated to the
# generic plugin-packed schema. Remove once all API callers send properly-typed
# payloads through AgenticGroundTruthEntry directly.

from typing import Any, cast

from app.domain.models import AgenticGroundTruthEntry, HistoryItem, Reference
from app.services.validation_service import ValidationError


def coerce_history_item(entry: Any) -> HistoryItem:
    message = entry.msg
    extras = entry.model_extra or {}
    if message is None and isinstance(extras.get("content"), str):
        message = extras["content"]
    if not message:
        raise ValidationError("", "history", "history entries must include a non-empty msg")

    refs_data = extras.get("refs")
    refs_list = None
    if refs_data is not None:
        if not isinstance(refs_data, list):
            raise ValidationError("", "history", "history refs must be a list")
        refs_list = [r if isinstance(r, Reference) else Reference(**r) for r in refs_data]

    expected_behavior_data = extras.get("expectedBehavior", extras.get("expected_behavior"))
    if expected_behavior_data is not None and not isinstance(expected_behavior_data, list):
        raise ValidationError(
            "",
            "history",
            "history expectedBehavior must be a list when provided",
        )

    return HistoryItem(
        role=entry.role,
        msg=message,
        refs=refs_list,
        expected_behavior=cast(list[str] | None, expected_behavior_data),
    )


def apply_legacy_compat_fields(item: AgenticGroundTruthEntry, extras: dict[str, Any]) -> None:
    if "editedQuestion" in extras or "edited_question" in extras:
        item.edited_question = cast(str | None, extras.get("editedQuestion", extras.get("edited_question")))

    if "answer" in extras:
        answer_value = extras["answer"]
        if answer_value is not None and not isinstance(answer_value, str):
            raise ValidationError(item.id, "answer", "answer must be a string or null")
        item.answer = cast(str | None, answer_value)

    if "refs" in extras:
        refs_payload = extras["refs"]
        if refs_payload is None:
            item.refs = []
        elif isinstance(refs_payload, list):
            item.refs = [r if isinstance(r, Reference) else Reference(**r) for r in refs_payload]
        else:
            raise ValidationError(item.id, "refs", "refs must be a list or null")
        item.totalReferences = 0
