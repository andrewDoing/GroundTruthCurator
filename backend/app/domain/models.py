from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Optional, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, computed_field, field_validator, model_validator

from app.domain.enums import GroundTruthStatus
from app.domain.validators import GroundTruthItemTagValidators


class Reference(BaseModel):
    """Legacy RAG reference object retained for compatibility helpers and tests."""

    url: str = Field(description="Reference URL (required, non-empty)")
    title: str | None = Field(default=None, description="Human-readable title for the reference")
    content: str | None = None
    keyExcerpt: str | None = None
    type: str | None = None
    bonus: bool = False
    messageIndex: Optional[int] = None

    @field_validator("url")
    @classmethod
    def validate_url_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Reference URL cannot be empty")
        return value.strip()


class HistoryEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    role: str
    msg: str

    @field_validator("role", "msg")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("history fields cannot be empty")
        return cleaned


class HistoryItem(HistoryEntry):
    """Legacy RAG-compatible history item retained for internal compatibility."""

    refs: Optional[list[Reference]] = None
    expected_behavior: Optional[list[str]] = Field(default=None, alias="expectedBehavior")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ContextEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    key: str
    value: Any

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("contextEntries[].key cannot be empty")
        return cleaned


class FeedbackEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source: str = ""
    values: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = ""
    name: str
    call_type: Literal["tool", "subagent"] = Field("tool", alias="callType")
    arguments: dict[str, Any] | None = None
    agent: str | None = None
    step_number: int | None = Field(None, alias="stepNumber")
    parallel_group: str | None = Field(None, alias="parallelGroup")
    parent_call_id: str | None = Field(None, alias="parentCallId")
    response: Any = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("toolCalls[].name cannot be empty")
        return cleaned

    @field_validator("step_number")
    @classmethod
    def validate_step_number(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("toolCalls[].stepNumber cannot be negative")
        return value


class PluginPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    kind: str
    version: str = "1.0"
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("plugins[].kind cannot be empty")
        return cleaned


class ToolExpectation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    arguments: dict[str, Any] | str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("expectedTools entries must include a non-empty name")
        return cleaned


class ExpectedTools(BaseModel):
    """Tool expectations. Tools are implicitly allowed unless listed here."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    required: list[ToolExpectation] = Field(default_factory=list)
    optional: list[ToolExpectation] = Field(default_factory=list)
    not_needed: list[ToolExpectation] = Field(default_factory=list, alias="notNeeded")

    @field_validator("required", "optional", "not_needed", mode="before")
    @classmethod
    def coerce_string_entries(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            normalized.append({"name": item} if isinstance(item, str) else item)
        return normalized

    @model_validator(mode="after")
    def reject_overlap(self) -> ExpectedTools:
        required_names = {tool.name for tool in self.required}
        optional_names = {tool.name for tool in self.optional}
        not_needed_names = {tool.name for tool in self.not_needed}
        overlap = sorted(
            (required_names & optional_names)
            | (required_names & not_needed_names)
            | (optional_names & not_needed_names)
        )
        if overlap:
            raise ValueError(
                f"tools cannot appear in more than one category: {', '.join(overlap)}"
            )
        return self


class RetrievalCandidate(BaseModel):
    """A single retrieval result that can be associated with a specific tool call.

    Supports per-tool-call ownership instead of flat top-level references,
    and preserves the raw search payload alongside normalised fields.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    url: str
    title: str | None = None
    chunk: str | None = None
    raw_payload: dict[str, Any] | None = Field(None, alias="rawPayload")
    relevance: str | None = None
    tool_call_id: str | None = Field(None, alias="toolCallId")

    @field_validator("url")
    @classmethod
    def validate_url_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RetrievalCandidate.url cannot be empty")
        return cleaned

    @field_validator("relevance")
    @classmethod
    def validate_relevance(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"relevant", "partially_relevant", "not_relevant"}
        if value not in allowed:
            raise ValueError(
                f"relevance must be one of {sorted(allowed)}, got '{value}'"
            )
        return value


class AgenticGroundTruthEntry(GroundTruthItemTagValidators, BaseModel):
    """Generic agentic-first host model.

    The core contract intentionally exposes only the generic schema in OpenAPI. Legacy
    RAG-shaped payloads are translated into this shape when validating this base class so
    existing data can be carried forward without remaining top-level contract fields.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(alias="id")
    datasetName: str = Field(alias="datasetName")
    bucket: Optional[UUID] = None
    status: GroundTruthStatus = GroundTruthStatus.draft
    docType: str = Field(default="ground-truth-item", alias="docType")
    schemaVersion: str = Field(default="v2", alias="schemaVersion")

    manual_tags: list[str] = Field(default_factory=list, alias="manualTags")
    computed_tags: list[str] = Field(default_factory=list, alias="computedTags")
    comment: str = ""

    assignedTo: Optional[str] = Field(default=None, alias="assignedTo")
    assigned_at: Optional[datetime] = Field(default=None, alias="assignedAt")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt"
    )
    updatedBy: Optional[str] = None
    reviewed_at: Optional[datetime] = Field(default=None, alias="reviewedAt")
    etag: Optional[str] = Field(default=None, alias="_etag")

    scenario_id: str = Field(default="", alias="scenarioId")
    history: list[HistoryEntry] = Field(default_factory=list)
    context_entries: list[ContextEntry] = Field(default_factory=list, alias="contextEntries")

    trace_ids: dict[str, str] | None = Field(default=None, alias="traceIds")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, alias="toolCalls")
    expected_tools: ExpectedTools = Field(default_factory=ExpectedTools, alias="expectedTools")

    feedback: list[FeedbackEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    plugins: dict[str, PluginPayload] = Field(default_factory=dict)

    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    trace_payload: dict[str, Any] = Field(default_factory=dict, alias="tracePayload")

    _RAG_COMPAT_PLUGIN: ClassVar[str] = "rag-compat"

    # --- Legacy compatibility layer ---
    # The model_validator, computed_fields, and property accessors below exist because
    # stored Cosmos DB documents may still carry top-level RAG fields (synthQuestion,
    # editedQuestion, answer, refs, etc.). They transparently relocate those fields into
    # plugins["rag-compat"] on read and re-expose them for internal code that still
    # accesses .synth_question, .answer, .refs, .totalReferences. Remove once all stored
    # documents have been migrated to the plugin-packed format.

    @model_validator(mode="before")
    @classmethod
    def translate_legacy_payload_for_core_model(cls, value: object) -> object:
        if cls is not AgenticGroundTruthEntry or not isinstance(value, dict):
            return value

        data = dict(value)
        data.pop("tags", None)
        legacy_payload: dict[str, Any] = {}

        for field_name in (
            "synthQuestion",
            "editedQuestion",
            "answer",
            "refs",
            "contextUsedForGeneration",
            "contextSource",
            "modelUsedForGeneration",
            "semanticClusterNumber",
            "weight",
            "samplingBucket",
            "questionLength",
            "totalReferences",
        ):
            if field_name in data:
                legacy_payload[field_name] = data.pop(field_name)

        if "refs" in legacy_payload and isinstance(legacy_payload["refs"], list):
            legacy_payload["refs"] = [
                ref if isinstance(ref, Reference) else Reference.model_validate(ref)
                for ref in legacy_payload["refs"]
            ]

        history_value = data.get("history")
        if isinstance(history_value, list):
            normalized_history: list[dict[str, Any]] = []
            history_annotations: list[dict[str, Any]] = []
            saw_history_annotations = False
            for raw_entry in history_value:
                if isinstance(raw_entry, BaseModel):
                    entry_dict = raw_entry.model_dump(by_alias=True, exclude_none=True)
                elif isinstance(raw_entry, dict):
                    entry_dict = dict(raw_entry)
                else:
                    normalized_history.append(raw_entry)
                    history_annotations.append({})
                    continue

                annotation: dict[str, Any] = {}
                if "refs" in entry_dict:
                    raw_refs = entry_dict.pop("refs")
                    if isinstance(raw_refs, list):
                        annotation["refs"] = [
                            ref if isinstance(ref, Reference) else Reference.model_validate(ref)
                            for ref in raw_refs
                        ]
                    else:
                        annotation["refs"] = raw_refs
                    saw_history_annotations = True
                expected_behavior = entry_dict.pop(
                    "expectedBehavior", entry_dict.pop("expected_behavior", None)
                )
                if expected_behavior is not None:
                    annotation["expectedBehavior"] = expected_behavior
                    saw_history_annotations = True

                message = entry_dict.get("msg")
                if message is None and "content" in entry_dict:
                    message = entry_dict.pop("content")
                normalized_history.append(
                    {
                        "role": entry_dict.get("role", ""),
                        "msg": message or "",
                    }
                )
                history_annotations.append(annotation)

            data["history"] = normalized_history
            if saw_history_annotations:
                legacy_payload["historyAnnotations"] = history_annotations
        elif history_value is None and (
            legacy_payload.get("editedQuestion")
            or legacy_payload.get("synthQuestion")
            or legacy_payload.get("answer")
        ):
            generated_history: list[dict[str, Any]] = []
            question_text = legacy_payload.get("editedQuestion") or legacy_payload.get("synthQuestion")
            if question_text:
                generated_history.append({"role": "user", "msg": question_text})
            if legacy_payload.get("answer"):
                generated_history.append({"role": "assistant", "msg": legacy_payload["answer"]})
            data["history"] = generated_history

        if legacy_payload:
            plugins_payload = dict(data.get("plugins") or {})
            existing_plugin = plugins_payload.get(cls._RAG_COMPAT_PLUGIN)
            if isinstance(existing_plugin, PluginPayload):
                plugin_dict = existing_plugin.model_dump(by_alias=True)
            elif isinstance(existing_plugin, dict):
                plugin_dict = dict(existing_plugin)
            else:
                plugin_dict = {"kind": cls._RAG_COMPAT_PLUGIN, "version": "1.0", "data": {}}
            plugin_data_raw = plugin_dict.get("data")
            plugin_data = dict(plugin_data_raw) if isinstance(plugin_data_raw, dict) else {}
            plugin_data.update(legacy_payload)
            plugin_dict["kind"] = plugin_dict.get("kind") or cls._RAG_COMPAT_PLUGIN
            plugin_dict["version"] = plugin_dict.get("version") or "1.0"
            plugin_dict["data"] = plugin_data
            plugins_payload[cls._RAG_COMPAT_PLUGIN] = plugin_dict
            data["plugins"] = plugins_payload

        return data

    @computed_field
    @property
    def tags(self) -> list[str]:
        merged = set(self.manual_tags or []) | set(self.computed_tags or [])
        return sorted(merged)

    @computed_field(alias="synthQuestion")
    @property
    def compat_synth_question(self) -> str | None:
        return self.synth_question

    @computed_field(alias="editedQuestion")
    @property
    def compat_edited_question(self) -> str | None:
        return self.edited_question

    @computed_field(alias="answer")
    @property
    def compat_answer(self) -> str | None:
        return self.answer

    @computed_field(alias="refs")
    @property
    def compat_refs(self) -> list[Reference]:
        return self.refs

    @computed_field(alias="totalReferences")
    @property
    def compat_total_references(self) -> int:
        return self.totalReferences

    def set_plugin(self, slot: str, data: dict[str, Any], *, version: str = "1.0") -> None:
        self.plugins[slot] = PluginPayload(kind=slot, version=version, data=data)

    def get_plugin_data(self, slot: str) -> dict[str, Any] | None:
        plugin = self.plugins.get(slot)
        return None if plugin is None else plugin.data

    def export_json_schema(self) -> dict[str, Any]:
        return self.model_json_schema()

    def _rag_compat_data(self) -> dict[str, Any]:
        plugin = self.plugins.get(self._RAG_COMPAT_PLUGIN)
        if plugin is None:
            return {}
        return plugin.data

    def _set_rag_compat_value(self, key: str, value: Any) -> None:
        plugin = self.plugins.get(self._RAG_COMPAT_PLUGIN)
        if plugin is None:
            plugin = PluginPayload(kind=self._RAG_COMPAT_PLUGIN, version="1.0", data={})
            self.plugins[self._RAG_COMPAT_PLUGIN] = plugin
        if value is None:
            plugin.data.pop(key, None)
        else:
            plugin.data[key] = value

    def _find_history_message(self, role: str, *, reverse: bool = False) -> str | None:
        history = self.history or []
        history_iterable = reversed(history) if reverse else history
        for turn in history_iterable:
            if turn.role == role and turn.msg:
                return turn.msg
        return None

    def _find_last_agent_message(self) -> str | None:
        """Return the last non-user history message (any agent role)."""
        for turn in reversed(self.history or []):
            if turn.role != "user" and turn.msg:
                return turn.msg
        return None

    @property
    def synth_question(self) -> str | None:
        if "synth_question" in self.__dict__:
            return cast(str | None, self.__dict__.get("synth_question"))
        compat = self._rag_compat_data()
        return cast(str | None, compat.get("synthQuestion")) or self._find_history_message("user")

    @synth_question.setter
    def synth_question(self, value: str | None) -> None:
        if "synth_question" in getattr(type(self), "model_fields", {}):
            self.__dict__["synth_question"] = value
            return
        self._set_rag_compat_value("synthQuestion", value)

    @property
    def edited_question(self) -> str | None:
        if "edited_question" in self.__dict__:
            return cast(str | None, self.__dict__.get("edited_question"))
        compat = self._rag_compat_data()
        return cast(str | None, compat.get("editedQuestion")) or self.synth_question

    @edited_question.setter
    def edited_question(self, value: str | None) -> None:
        if "edited_question" in getattr(type(self), "model_fields", {}):
            self.__dict__["edited_question"] = value
            return
        self._set_rag_compat_value("editedQuestion", value)

    @property
    def answer(self) -> str | None:
        if "answer" in self.__dict__:
            return cast(str | None, self.__dict__.get("answer"))
        compat = self._rag_compat_data()
        return cast(str | None, compat.get("answer")) or self._find_last_agent_message()

    @answer.setter
    def answer(self, value: str | None) -> None:
        if "answer" in getattr(type(self), "model_fields", {}):
            self.__dict__["answer"] = value
            return
        self._set_rag_compat_value("answer", value)

    @property
    def refs(self) -> list[Reference]:
        direct_value = self.__dict__.get("refs")
        if isinstance(direct_value, list):
            return [
                ref if isinstance(ref, Reference) else Reference.model_validate(ref)
                for ref in direct_value
            ]
        compat = self._rag_compat_data()
        raw_refs = compat.get("refs") or []
        return [ref if isinstance(ref, Reference) else Reference.model_validate(ref) for ref in raw_refs]

    @refs.setter
    def refs(self, value: list[Reference] | None) -> None:
        if "refs" in getattr(type(self), "model_fields", {}):
            self.__dict__["refs"] = list(value or [])
            return
        serialized = [ref.model_dump(by_alias=True) for ref in (value or [])]
        self._set_rag_compat_value("refs", serialized)

    @property
    def totalReferences(self) -> int:
        direct_value = self.__dict__.get("totalReferences")
        if isinstance(direct_value, int):
            return direct_value
        compat = self._rag_compat_data()
        if isinstance(compat.get("totalReferences"), int):
            return cast(int, compat["totalReferences"])
        history_count = 0
        history_annotations = compat.get("historyAnnotations")
        if isinstance(history_annotations, list):
            for annotation in history_annotations:
                if isinstance(annotation, dict) and isinstance(annotation.get("refs"), list):
                    history_count += len(annotation["refs"])
        if history_count:
            return history_count
        return len(self.refs)

    @totalReferences.setter
    def totalReferences(self, value: int | None) -> None:
        if "totalReferences" in getattr(type(self), "model_fields", {}):
            self.__dict__["totalReferences"] = 0 if value is None else int(value)
            return
        self._set_rag_compat_value("totalReferences", None if value is None else int(value))

    # NOTE: Informational RAG-era accessors (contextUsedForGeneration, contextSource,
    # modelUsedForGeneration, semanticClusterNumber, weight, samplingBucket, questionLength)
    # removed in Phase 7 legacy retirement. No callers accessed them via
    # AgenticGroundTruthEntry; GroundTruthItem still has explicit fields for Cosmos
    # backward-compat reads.


class GroundTruthItem(AgenticGroundTruthEntry):
    """Legacy compatibility model used internally by existing services/tests.

    This subclass keeps historical top-level RAG fields available for internal code while the
    public API moves to AgenticGroundTruthEntry.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    synth_question: str | None = Field(default=None, alias="synthQuestion")
    edited_question: str | None = Field(default=None, alias="editedQuestion")
    answer: str | None = None
    refs: list[Reference] = Field(default_factory=list, alias="refs")
    history: Optional[list[HistoryItem]] = None
    contextUsedForGeneration: Optional[str] = None
    contextSource: Optional[str] = None
    modelUsedForGeneration: Optional[str] = None
    semanticClusterNumber: Optional[int] = None
    weight: Optional[float] = None
    samplingBucket: Optional[int] = None
    questionLength: Optional[int] = None
    totalReferences: int = Field(default=0, alias="totalReferences")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_response_payload(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        data = dict(value)
        data.pop("tags", None)
        data.pop("curationInstructions", None)
        if data.get("history") is None:
            data["history"] = []
        if data.get("refs") is None:
            data["refs"] = []
        if data.get("totalReferences") is None:
            data["totalReferences"] = 0
        return data

    @model_validator(mode="after")
    def compute_total_references_if_needed(self) -> GroundTruthItem:
        if self.totalReferences == 0:
            history_refs = sum(len(turn.refs or []) for turn in (self.history or []))
            self.totalReferences = history_refs if history_refs > 0 else len(self.refs or [])
        return self


class PaginationMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(description="Current page number (1-indexed)")
    limit: int = Field(description="Items per page")
    total: int = Field(description="Total number of items matching filters")
    total_pages: int = Field(alias="totalPages", description="Total number of pages")
    has_next: bool = Field(alias="hasNext", description="Whether there is a next page")
    has_prev: bool = Field(alias="hasPrev", description="Whether there is a previous page")


class GroundTruthListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AgenticGroundTruthEntry]
    pagination: PaginationMetadata


class AssignmentDocument(BaseModel):
    id: str
    pk: str
    ground_truth_id: str
    datasetName: str
    bucket: UUID
    docType: str = Field(default="sme-assignment", alias="docType")
    schemaVersion: str = Field(default="v1", alias="schemaVersion")


class Stats(BaseModel):
    draft: int = 0
    approved: int = 0
    deleted: int = 0


class BulkImportError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(description="0-based position in request array")
    item_id: str | None = Field(
        default=None,
        alias="itemId",
        description="ID of the failed item (if available)",
    )
    field: str | None = Field(default=None, description="Field that caused the error (if applicable)")
    code: str = Field(description="Error code: INVALID_TAG, DUPLICATE_ID, CREATE_FAILED, etc.")
    message: str = Field(description="Human-readable error description")


class ValidationSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(description="Total items in request")
    succeeded: int = Field(description="Items successfully imported")
    failed: int = Field(description="Items that failed")


class BulkImportPersistenceError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(description="Human-readable persistence error description")
    item_id: str | None = Field(
        default=None,
        alias="itemId",
        description="ID of the failed item when the repository can identify it",
    )
    persistence_index: int | None = Field(
        default=None,
        alias="persistenceIndex",
        description="0-based position in the repository persistence batch",
    )


class BulkImportResult(BaseModel):
    imported: int = 0
    errors: list[str] = Field(default_factory=list)
    persistence_errors: list[BulkImportPersistenceError] = Field(default_factory=list)


class DatasetCurationInstructions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    datasetName: str = Field(alias="datasetName")
    bucket: UUID = Field(default_factory=lambda: UUID("00000000-0000-0000-0000-000000000000"))
    docType: str = Field(default="curation-instructions", alias="docType")
    schemaVersion: str = Field(default="v1", alias="schemaVersion")

    instructions: str

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt"
    )
    updatedBy: Optional[str] = None
    etag: Optional[str] = Field(default=None, alias="_etag")


class TagDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tag_key: str
    description: str
    created_by: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), alias="createdAt"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt"
    )
    doc_type: str = Field(default="tag-definition", alias="docType")
