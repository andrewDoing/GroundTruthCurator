from __future__ import annotations

import ast
import json
import shlex
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.domain.enums import GroundTruthStatus
from app.domain.models import (
    AgenticGroundTruthEntry,
    ContextEntry,
    FeedbackEntry,
    HistoryEntry,
    ToolCallRecord,
)


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _slug(value: object) -> str:
    cleaned = _clean_text(value).lower()
    if not cleaned:
        return ""
    chars: list[str] = []
    last_dash = False
    for char in cleaned:
        if char.isalnum():
            chars.append(char)
            last_dash = False
            continue
        if last_dash:
            continue
        chars.append("-")
        last_dash = True
    return "".join(chars).strip("-")


def _coerce_datetime(trace: Mapping[str, Any]) -> datetime:
    iso_value = trace.get("feedback_datetime_utc")
    if isinstance(iso_value, str) and iso_value.strip():
        return datetime.fromisoformat(iso_value.replace("Z", "+00:00"))

    epoch_value = trace.get("feedback_date")
    if isinstance(epoch_value, (int, float)):
        return datetime.fromtimestamp(epoch_value, tz=timezone.utc)

    return datetime.now(timezone.utc)


def _parse_jsonish(value: object) -> Any:
    if not isinstance(value, str):
        return value

    cleaned = value.strip()
    if not cleaned:
        return {}

    if cleaned[0] in "{[":
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw": cleaned}

    return {"raw": cleaned}


def _parse_tool_arguments(raw_arguments: object) -> dict[str, Any] | None:
    if not isinstance(raw_arguments, str) or not raw_arguments.strip():
        return None

    try:
        tokens = shlex.split(raw_arguments)
    except ValueError:
        return {"raw": raw_arguments}

    parsed: dict[str, Any] = {}
    for token in tokens:
        if "=" not in token:
            return {"raw": raw_arguments}
        key, raw_value = token.split("=", 1)
        key = key.strip()
        if not key:
            return {"raw": raw_arguments}
        try:
            parsed[key] = ast.literal_eval(raw_value)
        except (ValueError, SyntaxError):
            parsed[key] = raw_value
    return parsed or {"raw": raw_arguments}


def _build_tool_response(tool_call: Mapping[str, Any]) -> Any:
    result = _parse_jsonish(tool_call.get("function_result"))
    execution_time = tool_call.get("execution_time")
    run_id = tool_call.get("run_id")

    if execution_time is None and run_id is None:
        return result

    response: dict[str, Any] = {"result": result}
    if execution_time is not None:
        response["executionTimeSeconds"] = execution_time
    if run_id is not None:
        response["runId"] = run_id
    return response


def _build_history(chat_history: list[Mapping[str, Any]]) -> list[HistoryEntry]:
    history: list[HistoryEntry] = []
    for chat_item in chat_history:
        user_query = _clean_text(chat_item.get("user_query"))
        if user_query:
            history.append(HistoryEntry(role="user", msg=user_query))

        chat_response = _clean_text(chat_item.get("chat_response"))
        if chat_response:
            history.append(HistoryEntry(role="orchestrator-agent", msg=chat_response))

        rca = _clean_text(chat_item.get("rca"))
        if rca:
            history.append(HistoryEntry(role="output-agent", msg=rca))
    return history


def _build_context_entries(trace: Mapping[str, Any], chat_history_count: int) -> list[ContextEntry]:
    entries: list[ContextEntry] = []
    for key in (
        "uid",
        "cid_list",
        "impacted_device_type",
        "impacted_device",
        "metric_name",
        "type",
        "resolution",
        "feedback_datetime_utc",
    ):
        value = trace.get(key)
        if value in (None, "", []):
            continue
        entries.append(ContextEntry(key=key, value=value))

    entries.append(ContextEntry(key="chat_history_count", value=chat_history_count))
    return entries


def _build_feedback(trace: Mapping[str, Any]) -> list[FeedbackEntry]:
    additional_feedback = trace.get("additional_feedback")
    summary_values = {
        "metricName": trace.get("metric_name"),
        "feedbackType": trace.get("type"),
        "comment": trace.get("comment"),
        "resolution": trace.get("resolution"),
    }

    feedback: list[FeedbackEntry] = [
        FeedbackEntry(
            source="trace-export-summary",
            values={key: value for key, value in summary_values.items() if value not in (None, "")},
        )
    ]
    if isinstance(additional_feedback, dict) and additional_feedback:
        feedback.append(
            FeedbackEntry(source="trace-export-ratings", values=dict(additional_feedback))
        )
    return feedback


def _build_trace_ids(trace: Mapping[str, Any]) -> dict[str, str] | None:
    trace_ids: dict[str, str] = {}
    trace_id = _clean_text(trace.get("id"))
    if trace_id:
        trace_ids["traceId"] = trace_id

    cid_list = trace.get("cid_list")
    if isinstance(cid_list, list) and cid_list:
        first_cid = cid_list[0]
        if isinstance(first_cid, str) and first_cid.strip():
            trace_ids["conversationId"] = first_cid.strip()

    uid = _clean_text(trace.get("uid"))
    if uid:
        trace_ids["userId"] = uid

    return trace_ids or None


def _build_manual_tags(trace: Mapping[str, Any]) -> list[str]:
    tags = [
        "source:trace-export",
        "workflow:agentic-rca",
    ]
    metric = _slug(trace.get("metric_name"))
    feedback_type = _slug(trace.get("type"))
    device_type = _slug(trace.get("impacted_device_type"))
    if metric:
        tags.append(f"metric:{metric}")
    if feedback_type:
        tags.append(f"feedback:{feedback_type}")
    if device_type:
        tags.append(f"device:{device_type}")
    return sorted(set(tags))


class TraceExportAdapter:
    def __init__(
        self,
        *,
        dataset_name: str,
        bucket: UUID | None = None,
        status: GroundTruthStatus = GroundTruthStatus.draft,
        created_by: str = "trace-export-adapter",
    ) -> None:
        self._dataset_name = dataset_name
        self._bucket = bucket
        self._status = status
        self._created_by = created_by

    def adapt_payload(self, payload: Mapping[str, Any]) -> list[AgenticGroundTruthEntry]:
        traces = payload.get("traces")
        if not isinstance(traces, list):
            raise ValueError("trace export payload must contain a 'traces' list")

        items: list[AgenticGroundTruthEntry] = []
        for index, trace in enumerate(traces, start=1):
            if not isinstance(trace, Mapping):
                raise ValueError(f"trace at index {index - 1} must be an object")
            items.append(self.adapt_trace(trace, index=index))
        return items

    def adapt_trace(
        self, trace: Mapping[str, Any], *, index: int = 1
    ) -> AgenticGroundTruthEntry:
        trace_id = _clean_text(trace.get("id")) or f"trace-{index}"
        created_at = _coerce_datetime(trace)

        raw_chat_history = trace.get("chat_history")
        if raw_chat_history is None:
            chat_history: list[Mapping[str, Any]] = []
        elif isinstance(raw_chat_history, list):
            chat_history = [
                chat_item for chat_item in raw_chat_history if isinstance(chat_item, Mapping)
            ]
        else:
            raise ValueError(f"trace '{trace_id}' has a non-list chat_history value")

        history = _build_history(chat_history)

        tool_calls: list[ToolCallRecord] = []
        for step_number, chat_item in enumerate(chat_history, start=1):
            raw_context = chat_item.get("context")
            if raw_context is None:
                continue
            if not isinstance(raw_context, list):
                raise ValueError(f"trace '{trace_id}' chat_history[{step_number - 1}] context must be a list")
            for raw_tool_call in raw_context:
                if not isinstance(raw_tool_call, Mapping):
                    raise ValueError(
                        f"trace '{trace_id}' chat_history[{step_number - 1}] context entries must be objects"
                    )
                tool_calls.append(
                    ToolCallRecord(
                        id=_clean_text(raw_tool_call.get("id")) or f"{trace_id}:tool:{len(tool_calls) + 1}",
                        name=_clean_text(raw_tool_call.get("function_name")) or f"tool-{len(tool_calls) + 1}",
                        callType="tool",
                        arguments=_parse_tool_arguments(raw_tool_call.get("function_arguments")),
                        stepNumber=len(tool_calls) + 1,
                        response=_build_tool_response(raw_tool_call),
                    )
                )

        metadata = {
            "sourceFormat": "trace-export",
            "metricName": trace.get("metric_name"),
            "feedbackType": trace.get("type"),
            "chatHistoryCount": len(chat_history),
            "toolCallCount": len(tool_calls),
        }

        return AgenticGroundTruthEntry.model_validate(
            {
                "id": f"trace-{trace_id}",
                "datasetName": self._dataset_name,
                "bucket": self._bucket,
                "status": self._status,
                "manualTags": _build_manual_tags(trace),
                "comment": _clean_text(trace.get("comment"))
                or _clean_text(trace.get("resolution")),
                "updatedAt": created_at,
                "createdAt": created_at,
                "createdBy": self._created_by,
                "scenarioId": f"trace-export:{trace_id}",
                "history": history,
                "contextEntries": _build_context_entries(trace, len(chat_history)),
                "traceIds": _build_trace_ids(trace),
                "toolCalls": tool_calls,
                "feedback": _build_feedback(trace),
                "metadata": {
                    key: value for key, value in metadata.items() if value not in (None, "")
                },
                "tracePayload": dict(trace),
            }
        )
