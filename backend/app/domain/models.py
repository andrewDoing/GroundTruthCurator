from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Optional, Literal
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
            raise ValueError(f"tools cannot appear in more than one category: {', '.join(overlap)}")
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
            raise ValueError(f"relevance must be one of {sorted(allowed)}, got '{value}'")
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

    @computed_field
    @property
    def tags(self) -> list[str]:
        merged = set(self.manual_tags or []) | set(self.computed_tags or [])
        return sorted(merged)

    def set_plugin(self, slot: str, data: dict[str, Any], *, version: str = "1.0") -> None:
        self.plugins[slot] = PluginPayload(kind=slot, version=version, data=data)

    def get_plugin_data(self, slot: str) -> dict[str, Any] | None:
        plugin = self.plugins.get(slot)
        return None if plugin is None else plugin.data

    def export_json_schema(self) -> dict[str, Any]:
        return self.model_json_schema()


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
    field: str | None = Field(
        default=None, description="Field that caused the error (if applicable)"
    )
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
