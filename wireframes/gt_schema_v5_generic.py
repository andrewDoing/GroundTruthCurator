from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class HistoryEntry(BaseModel):
    role: str
    msg: str

    model_config = {"extra": "forbid"}


class ContextEntry(BaseModel):
    key: str
    value: Any

    model_config = {"extra": "forbid"}


class FeedbackEntry(BaseModel):
    source: str = ""
    values: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ToolCallRecord(BaseModel):
    id: str = ""
    name: str
    call_type: Literal["tool", "subagent"] = Field("tool", alias="callType")
    agent: str | None = None
    # which step in the agent execution was this tool called? each step is between agent respnonses to the user. multiple tools can be called in the same step.
    sequence_number: int | None = Field(None, alias="stepNumber")
    parallel_group: str | None = Field(None, alias="parallelGroup")
    parent_call_id: str | None = Field(None, alias="parentCallId")
    response: Any = None

    model_config = {"extra": "forbid", "populate_by_name": True}


class PluginPayload(BaseModel):
    kind: str
    version: str = "1.0"
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ToolExpectation(BaseModel):
    name: str
    arguments: dict[str, Any] | str | None = None

    model_config = {"extra": "forbid"}


class ExpectedTools(BaseModel):
    """Tool expectations. Every tool defaults to allowed unless listed here."""

    required: list[ToolExpectation] = Field(default_factory=list)
    optional: list[ToolExpectation] = Field(default_factory=list)
    not_needed: list[ToolExpectation] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("required", "optional", "not_needed", mode="before")
    @classmethod
    def _coerce_string_entries(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"name": item})
            else:
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def _reject_overlap(self) -> ExpectedTools:
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

# ---------------------------------------------------------------------------
# Generic GT schema
# ---------------------------------------------------------------------------


class AgenticGroundTruthEntry(BaseModel):
    # --- Core identity / storage ---
    id: str = ""
    dataset_name: str = Field("", alias="datasetName")
    bucket: str = ""
    doc_type: str = Field("ground-truth", alias="docType")
    schema_version: str = Field("agentic-core/v1", alias="schemaVersion")
    status: str = "draft"
    etag: str = Field("", alias="_etag")
    assigned_to: str = Field("", alias="assignedTo")
    assigned_at: str = Field("", alias="assignedAt")
    updated_at: str = Field("", alias="updatedAt")
    updated_by: str = Field("", alias="updatedBy")
    reviewed_at: str | None = Field(None, alias="reviewedAt")
    manual_tags: list[str] = Field(default_factory=list, alias="manualTags")
    computed_tags: list[str] = Field(default_factory=list, alias="computedTags")

    # --- Scenario content ---
    scenario_id: str = Field("", alias="scenarioId")
    history: list[HistoryEntry] = Field(default_factory=list)
    context_entries: list[ContextEntry] = Field(default_factory=list, alias="contextEntries")

    # --- Agentic execution data ---
    trace_ids: dict[str, str] | None = Field(None, alias="traceIds")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, alias="toolCalls")
    expected_tools: ExpectedTools = Field(default_factory=ExpectedTools, alias="expectedTools")

    # --- Flexible extension surfaces ---
    feedback: list[FeedbackEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    plugins: dict[str, PluginPayload] = Field(default_factory=dict)
    comment: str = ""

    # --- Provenance ---
    created_by: str | None = None
    created_at: str | None = None

    # --- Stored at the bottom for better readability ---
    trace_payload: dict[str, Any] = Field(default_factory=dict, alias="tracePayload")

    model_config = {"extra": "forbid", "populate_by_name": True}


    def set_plugin(self, slot: str, data: dict[str, Any], *, version: str = "1.0") -> None:
        """Attach opaque customer- or feature-specific data under a named plugin slot.
        """

        self.plugins[slot] = PluginPayload(kind=slot, version=version, data=data)

    def get_plugin_data(self, slot: str) -> dict[str, Any] | None:
        plugin = self.plugins.get(slot)
        return None if plugin is None else plugin.data

    def export_json_schema(self) -> dict[str, Any]:
        return self.model_json_schema()



__all__ = [
    "AgenticGroundTruthEntry",
    "ContextEntry",
    "ExpectedOutput",
    "ExpectedTools",
    "FeedbackEntry",
    "GTMetadata",
    "HistoryEntry",
    "PluginPayload",
    "ToolExpectation",
    "ToolCallRecord",
]