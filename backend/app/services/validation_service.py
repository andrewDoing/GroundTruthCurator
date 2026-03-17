"""Validation service for generic ground truth items during bulk import and approval."""

from __future__ import annotations

import asyncio
import logging

from app.domain.conversation_fields import answer_text_from_item, question_text_from_item
from app.domain.models import AgenticGroundTruthEntry, BulkImportError, HistoryEntry
from app.services.tagging_service import validate_tags_with_cache

logger = logging.getLogger(__name__)
container = None


def _resolve_plugin_pack_registry(plugin_pack_registry=None):
    if plugin_pack_registry is not None:
        return plugin_pack_registry

    global container
    if container is None:
        from app.container import container as runtime_container

        container = runtime_container
    return container.plugin_pack_registry


def _resolve_tag_registry_service(tag_registry_service=None):
    if tag_registry_service is not None:
        return tag_registry_service

    global container
    if container is None:
        from app.container import container as runtime_container

        container = runtime_container
    return container.tag_registry_service


class ValidationError(Exception):
    """Raised when validation fails for a ground truth item."""

    def __init__(self, item_id: str, field: str, message: str):
        self.item_id = item_id
        self.field = field
        self.message = message
        super().__init__(f"Item '{item_id}': {field} - {message}")


class ApprovalValidationError(Exception):
    """Raised when a ground truth item fails generic approval validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _normalized_history(item: AgenticGroundTruthEntry) -> list[HistoryEntry]:
    history = list(item.history or [])
    question_text = question_text_from_item(item)
    answer_text = answer_text_from_item(item)
    if history:
        roles = {entry.role.strip().lower() for entry in history}
        if "user" not in roles and question_text:
            history.insert(0, HistoryEntry(role="user", msg=question_text))
        if "assistant" not in roles and answer_text:
            history.append(HistoryEntry(role="assistant", msg=answer_text))
        return history

    synthesized: list[HistoryEntry] = []
    if question_text:
        synthesized.append(HistoryEntry(role="user", msg=question_text))
    if answer_text:
        synthesized.append(HistoryEntry(role="assistant", msg=answer_text))
    return synthesized


def collect_approval_validation_errors(item: AgenticGroundTruthEntry) -> list[str]:
    """Return generic approval validation errors for an item.

    The generic core enforces conversation integrity and expected-tool consistency.
    Legacy RAG-shaped data is tolerated through compatibility helpers so existing
    assignment/export flows remain intact during the migration.
    """

    errors: list[str] = []
    history = _normalized_history(item)

    if not history:
        errors.append("history must contain at least one conversation message")
    else:
        user_messages = [entry for entry in history if entry.role.strip().lower() == "user"]
        assistant_messages = [
            entry for entry in history if entry.role.strip().lower() == "assistant"
        ]
        if not user_messages:
            errors.append("history must include at least one user message")
        if not assistant_messages:
            errors.append("history must include at least one assistant message")

    tool_call_names = {tool.name for tool in item.tool_calls if tool.name}
    required_tools = [tool.name for tool in item.expected_tools.required if tool.name]

    if item.tool_calls and not required_tools:
        errors.append(
            "expectedTools.required must include at least one tool before approval when toolCalls are present"
        )

    missing_required_tools = sorted(
        {name for name in required_tools if name not in tool_call_names}
    )
    if missing_required_tools:
        errors.append(
            "expectedTools.required references toolCalls that do not exist: "
            + ", ".join(missing_required_tools)
        )

    return errors


def validate_item_for_approval(item: AgenticGroundTruthEntry, plugin_pack_registry=None) -> None:
    registry = _resolve_plugin_pack_registry(plugin_pack_registry)
    errors = collect_approval_validation_errors(item)
    # Let plugin packs waive specific core errors (e.g. RagCompatPack waives
    # the assistant-message requirement for retrieval-only items).
    errors = registry.filter_core_errors(item, errors)
    # Run plugin-pack approval hooks after the generic core checks.
    # Each registered pack may contribute additional domain-specific errors
    # (e.g. RagCompatPack enforcing per-retrieval-call selection completeness).
    pack_errors = registry.collect_approval_errors(item)
    errors.extend(pack_errors)
    if errors:
        raise ApprovalValidationError(errors)


async def validate_ground_truth_item(
    item: AgenticGroundTruthEntry,
    item_index: int,
    valid_tags_cache: set[str] | None = None,
    tag_registry_service=None,
) -> list[BulkImportError]:
    """Validate a ground truth item for bulk import.

    Returns a list of structured validation error objects. Empty list means valid.
    Used instead of pydantic as tag validation requires an async call for the cache.
    """

    errors: list[BulkImportError] = []
    item_id = item.id or "(no ID)"

    # Validate manual tag values (computed tags are system-generated and don't need validation)
    if item.manual_tags:
        registry_service = _resolve_tag_registry_service(tag_registry_service)
        if valid_tags_cache is None:
            valid_tags_cache = set(await registry_service.list_tags())
        try:
            validate_tags_with_cache(item.manual_tags, valid_tags_cache)
            logger.debug(
                "Tag validation passed | item_id: %s | manualTags: %s",
                item_id,
                item.manual_tags,
            )
        except ValueError as e:
            errors.append(
                BulkImportError(
                    index=item_index,
                    item_id=item_id,
                    field="manualTags",
                    code="INVALID_TAG",
                    message=str(e),
                )
            )
            logger.warning(
                "Tag validation failed during bulk import | ID: %s | Dataset: %s | ManualTags: %s | Error: %s",
                item_id,
                item.datasetName,
                item.manual_tags,
                str(e),
            )

    return errors


async def validate_bulk_items(
    items: list[AgenticGroundTruthEntry],
    *,
    tag_registry_service=None,
) -> dict[int, list[BulkImportError]]:
    """Validate a list of ground truth items for bulk import.

    Returns a dict mapping request-position index to list of structured validation
    errors.  Keyed by index rather than item.id so duplicate IDs in one request
    do not collapse per-entry error attribution or undercount failed request entries.
    Items with no errors are not included in the result.
    """

    validation_results: dict[int, list[BulkImportError]] = {}

    valid_tags_cache: set[str] | None = None
    has_items_with_tags = any(item.manual_tags for item in items)
    if has_items_with_tags:
        valid_tags_cache = set(
            await _resolve_tag_registry_service(tag_registry_service).list_tags()
        )

    validation_tasks = [
        validate_ground_truth_item(
            item,
            index,
            valid_tags_cache,
            tag_registry_service=tag_registry_service,
        )
        for index, item in enumerate(items)
    ]

    results = await asyncio.gather(*validation_tasks, return_exceptions=False)

    for index, item_errors in enumerate(results):
        if item_errors:
            validation_results[index] = item_errors

    return validation_results
