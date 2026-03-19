from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast, Sequence

from app.domain.enums import GroundTruthStatus
from app.domain.models import (
    AgenticGroundTruthEntry,
    ContextEntry,
    ExpectedTools,
    FeedbackEntry,
    HistoryEntry,
    HistoryItem,
    PluginPayload,
    ToolCallRecord,
)
from app.services.tagging_service import apply_computed_tags
from app.services.validation_service import ValidationError, validate_item_for_approval


class ETagRequiredError(Exception):
    """Raised when an update request omits optimistic-concurrency state."""


class ETagMismatchError(Exception):
    """Raised when the provided ETag no longer matches persisted state."""


@dataclass(slots=True)
class UpdateMutationResult:
    should_delete_assignment: bool = False


def _parse_status(value: GroundTruthStatus | str | None) -> GroundTruthStatus:
    if value is None:
        raise ValidationError(
            "", "status", "status cannot be null; omit the field to leave it unchanged"
        )
    try:
        if isinstance(value, GroundTruthStatus):
            return value
        return GroundTruthStatus(str(value))
    except (ValueError, KeyError) as exc:
        raise ValidationError(
            "",
            "status",
            f"Invalid status value: {value}. Must be one of: draft, approved, skipped, deleted",
        ) from exc


def parse_history_entries(entries: Sequence[Any]) -> list[HistoryItem]:
    history: list[HistoryItem] = []
    for entry in entries:
        message = getattr(entry, "msg", None)
        extras = getattr(entry, "model_extra", None) or {}
        if message is None and isinstance(extras.get("content"), str):
            message = extras["content"]
        if not message:
            raise ValidationError("", "history", "history entries must include a non-empty msg")

        expected_behavior = extras.get("expectedBehavior", extras.get("expected_behavior"))
        if expected_behavior is not None and not isinstance(expected_behavior, list):
            raise ValidationError(
                "",
                "history",
                "history expectedBehavior must be a list when provided",
            )

        history.append(
            HistoryItem(
                role=getattr(entry, "role"),
                msg=message,
                expected_behavior=expected_behavior,
            )
        )
    return history


def apply_shared_update(
    item: AgenticGroundTruthEntry,
    *,
    provided_fields: set[str],
    comment: str | None = None,
    history_entries: Sequence[Any] | None = None,
    context_entries: list[ContextEntry] | None = None,
    tool_calls: list[ToolCallRecord] | None = None,
    expected_tools: ExpectedTools | None = None,
    feedback: list[FeedbackEntry] | None = None,
    metadata: dict[str, Any] | None = None,
    plugins: dict[str, PluginPayload] | None = None,
    trace_ids: dict[str, str] | None = None,
    trace_payload: dict[str, Any] | None = None,
    scenario_id: str | None = None,
    manual_tags: list[str] | None = None,
    status: GroundTruthStatus | str | None = None,
    approve: bool = False,
    actor_user_id: str,
    clear_assignment_on_statuses: set[GroundTruthStatus] | None = None,
) -> UpdateMutationResult:
    now = datetime.now(timezone.utc)
    deletion_statuses = clear_assignment_on_statuses or set()
    should_delete_assignment = False

    if "comment" in provided_fields:
        item.comment = comment or ""

    if "history" in provided_fields:
        if history_entries is None:
            item.history = []
        else:
            # HistoryItem is a subclass of HistoryEntry, so this is safe
            item.history = cast(list[HistoryEntry], parse_history_entries(history_entries))

    if "context_entries" in provided_fields:
        item.context_entries = context_entries or []
    if "tool_calls" in provided_fields:
        item.tool_calls = tool_calls or []
    if "expected_tools" in provided_fields:
        if expected_tools is None:
            raise ValidationError(
                "",
                "expectedTools",
                "expectedTools cannot be null; omit the field to leave it unchanged",
            )
        item.expected_tools = expected_tools
    if "feedback" in provided_fields:
        item.feedback = feedback or []
    if "metadata" in provided_fields:
        item.metadata = metadata or {}
    if "plugins" in provided_fields:
        item.plugins = plugins or {}
    if "trace_ids" in provided_fields:
        item.trace_ids = trace_ids
    if "trace_payload" in provided_fields:
        item.trace_payload = trace_payload or {}
    if "scenario_id" in provided_fields:
        item.scenario_id = scenario_id or ""
    if "manual_tags" in provided_fields:
        item.manual_tags = manual_tags or []

    if approve:
        item.status = GroundTruthStatus.approved
        item.reviewed_at = now
        item.updatedBy = actor_user_id
        if GroundTruthStatus.approved in deletion_statuses:
            item.assignedTo = None
            item.assigned_at = None
            should_delete_assignment = True

    if "status" in provided_fields:
        item.status = _parse_status(status)
        if item.status in deletion_statuses:
            item.assignedTo = None
            item.assigned_at = None
            should_delete_assignment = True
        if item.status == GroundTruthStatus.approved:
            item.reviewed_at = now
            item.updatedBy = actor_user_id

    return UpdateMutationResult(should_delete_assignment=should_delete_assignment)


async def persist_shared_update(
    repo: Any,
    item: AgenticGroundTruthEntry,
    *,
    if_match: str | None,
    payload_etag: str | None,
) -> None:
    if not if_match and not payload_etag:
        raise ETagRequiredError()
    item.etag = if_match or payload_etag

    if item.status == GroundTruthStatus.approved:
        validate_item_for_approval(item)
    apply_computed_tags(item)

    try:
        await repo.upsert_gt(item)
    except ValueError as exc:
        if str(exc) == "etag_mismatch":
            raise ETagMismatchError() from exc
        raise
