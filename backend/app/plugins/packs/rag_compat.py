"""RAG compatibility pack.

This pack owns the remaining RAG-specific compatibility surface on the generic
agentic host. The only plugin-owned payload retained here is normalized
``references`` data. Legacy RAG fields are translated into generic history or
flattened into references during import, and new writes only persist
``plugins[\"rag-compat\"].data.references``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.plugins.base import ExplorerFieldDefinition, ExportTransform, ImportTransform, PluginPack

if TYPE_CHECKING:
    from app.domain.models import AgenticGroundTruthEntry, Reference

logger = logging.getLogger(__name__)

_RAG_COMPAT_KIND: str = "rag-compat"
_PLUGIN_REFERENCES_KEY = "references"
_LEGACY_REFS_KEY = "refs"
_LEGACY_KEYS_TO_DROP = (
    _LEGACY_REFS_KEY,
    "retrievals",
    "historyAnnotations",
    "totalReferences",
    "synthQuestion",
    "editedQuestion",
    "answer",
)


def _coerce_reference_list(raw_refs: Any) -> list[Any]:
    if not isinstance(raw_refs, list):
        return []

    from app.domain.models import Reference

    return [
        ref if isinstance(ref, Reference) else Reference.model_validate(ref) for ref in raw_refs
    ]


def _extract_history_refs(history: Any) -> list[Any]:
    if not isinstance(history, list):
        return []

    refs: list[Any] = []
    for turn in history:
        if hasattr(turn, "refs"):
            refs.extend(_coerce_reference_list(getattr(turn, "refs", None)))
            continue
        if isinstance(turn, dict):
            refs.extend(_coerce_reference_list(turn.get(_LEGACY_REFS_KEY)))
    return refs


def _extract_retrieval_refs(payload: dict[str, Any], compat: dict[str, Any]) -> list[Any]:
    retrievals = compat.get("retrievals")
    if not isinstance(retrievals, dict):
        return []

    from app.domain.models import Reference

    tool_calls = payload.get("toolCalls") or payload.get("tool_calls") or []
    step_by_tool_call_id: dict[str, int | None] = {}
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if hasattr(tool_call, "id"):
                tool_call_id = getattr(tool_call, "id", "")
                step_number = getattr(tool_call, "step_number", None)
            elif isinstance(tool_call, dict):
                tool_call_id = str(tool_call.get("id") or "")
                step_number = tool_call.get("stepNumber", tool_call.get("step_number"))
            else:
                continue
            if tool_call_id:
                step_by_tool_call_id[tool_call_id] = (
                    step_number if isinstance(step_number, int) else None
                )

    flattened: list[Reference] = []
    for tool_call_id, bucket in retrievals.items():
        if not isinstance(bucket, dict):
            continue
        candidates = bucket.get("candidates")
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            candidate_tool_call_id = candidate.get("toolCallId") or tool_call_id or None
            flattened.append(
                Reference(
                    url=str(candidate.get("url") or ""),
                    title=candidate.get("title"),
                    content=candidate.get("chunk"),
                    messageIndex=step_by_tool_call_id.get(str(candidate_tool_call_id))
                    if candidate_tool_call_id
                    else None,
                )
            )
    return flattened


def rag_compat_data_from_payload(
    payload: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND
) -> dict[str, Any]:
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        return {}
    plugin = plugins.get(plugin_name)
    if hasattr(plugin, "data"):
        plugin_data = getattr(plugin, "data", None)
        return dict(plugin_data) if isinstance(plugin_data, dict) else {}
    if isinstance(plugin, dict):
        plugin_data = plugin.get("data")
        return dict(plugin_data) if isinstance(plugin_data, dict) else {}
    return {}


def compat_refs_from_payload(
    payload: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND
) -> list[Any]:
    compat = rag_compat_data_from_payload(payload, plugin_name=plugin_name)

    compat_refs = _coerce_reference_list(
        compat.get(_PLUGIN_REFERENCES_KEY, compat.get(_LEGACY_REFS_KEY))
    )
    if compat_refs:
        return compat_refs

    retrieval_refs = _extract_retrieval_refs(payload, compat)
    if retrieval_refs:
        return retrieval_refs

    return _extract_history_refs(payload.get("history"))


def normalize_legacy_payload_for_core_model(
    value: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND
) -> dict[str, Any]:
    data = dict(value)
    data.pop("tags", None)

    raw_history = data.get("history")
    normalized_history: list[dict[str, Any]] | None = None
    history_refs: list[Any] = []
    if isinstance(raw_history, list):
        normalized_history = []
        for raw_entry in raw_history:
            if hasattr(raw_entry, "model_dump"):
                entry_dict = raw_entry.model_dump(by_alias=True, exclude_none=True)
            elif isinstance(raw_entry, dict):
                entry_dict = dict(raw_entry)
            else:
                continue

            history_refs.extend(_coerce_reference_list(entry_dict.pop(_LEGACY_REFS_KEY, None)))
            message = entry_dict.get("msg")
            if message is None and isinstance(entry_dict.get("content"), str):
                message = entry_dict.get("content")
            normalized_history.append(
                {
                    "role": str(entry_dict.get("role") or ""),
                    "msg": str(message or ""),
                }
            )
        data["history"] = normalized_history

    synth_question = data.pop("synthQuestion", None)
    edited_question = data.pop("editedQuestion", None)
    answer = data.pop("answer", None)
    if normalized_history is None and any(
        isinstance(v, str) and v.strip() for v in (edited_question, synth_question, answer)
    ):
        generated_history: list[dict[str, Any]] = []
        question_text = (
            edited_question
            if isinstance(edited_question, str) and edited_question.strip()
            else synth_question
        )
        if isinstance(question_text, str) and question_text.strip():
            generated_history.append({"role": "user", "msg": question_text.strip()})
        if isinstance(answer, str) and answer.strip():
            generated_history.append({"role": "assistant", "msg": answer.strip()})
        data["history"] = generated_history

    plugins_payload = dict(data.get("plugins") or {})
    existing_plugin = plugins_payload.get(plugin_name)
    if hasattr(existing_plugin, "model_dump"):
        plugin_dict = existing_plugin.model_dump(by_alias=True)
    elif isinstance(existing_plugin, dict):
        plugin_dict = dict(existing_plugin)
    else:
        plugin_dict = {"kind": plugin_name, "version": "1.0", "data": {}}

    plugin_data_raw = plugin_dict.get("data")
    plugin_data = dict(plugin_data_raw) if isinstance(plugin_data_raw, dict) else {}
    references = _coerce_reference_list(
        plugin_data.get(_PLUGIN_REFERENCES_KEY, plugin_data.get(_LEGACY_REFS_KEY))
    )
    if not references:
        top_level_refs = data.pop(_LEGACY_REFS_KEY, None)
        references = _coerce_reference_list(top_level_refs)
    if not references:
        references = _extract_retrieval_refs(
            {"plugins": plugins_payload, "toolCalls": data.get("toolCalls")}, plugin_data
        )
    if not references:
        references = history_refs

    for legacy_key in _LEGACY_KEYS_TO_DROP:
        plugin_data.pop(legacy_key, None)

    if references:
        plugin_data[_PLUGIN_REFERENCES_KEY] = [
            ref.model_dump(by_alias=True, exclude_none=True) if hasattr(ref, "model_dump") else ref
            for ref in references
        ]

    if plugin_data:
        plugin_dict["kind"] = plugin_dict.get("kind") or plugin_name
        plugin_dict["version"] = plugin_dict.get("version") or "1.0"
        plugin_dict["data"] = plugin_data
        plugins_payload[plugin_name] = plugin_dict
        data["plugins"] = plugins_payload
    elif plugin_name in plugins_payload:
        plugins_payload.pop(plugin_name, None)
        data["plugins"] = plugins_payload

    return data


def apply_export_projection(
    doc: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND
) -> dict[str, Any]:
    projected = dict(doc)
    refs = compat_refs_from_payload(projected, plugin_name=plugin_name)
    if refs:
        projected[_PLUGIN_REFERENCES_KEY] = [
            ref.model_dump(by_alias=True, exclude_none=True) for ref in refs
        ]
        projected["totalReferences"] = len(refs)
    else:
        projected.pop(_PLUGIN_REFERENCES_KEY, None)
        projected["totalReferences"] = 0
    return projected


class RagCompatPack(PluginPack):
    @property
    def name(self) -> str:
        return _RAG_COMPAT_KIND

    def validate_registration(self) -> None:
        from app.domain.models import AgenticGroundTruthEntry

        expected = AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN
        if expected != _RAG_COMPAT_KIND:
            raise ValueError(
                f"RagCompatPack kind '{_RAG_COMPAT_KIND}' does not match "
                f"AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN '{expected}'. "
                "Update _RAG_COMPAT_KIND in rag_compat.py to keep them in sync."
            )
        logger.debug("rag_compat_pack.validate_registration.ok | kind=%s", _RAG_COMPAT_KIND)

    def collect_approval_errors(self, item: AgenticGroundTruthEntry) -> list[str]:
        return []

    def collect_approval_waivers(
        self, item: AgenticGroundTruthEntry, core_errors: list[str]
    ) -> list[str]:
        if self.reference_count(item) == 0:
            return []

        waivers: list[str] = []
        assistant_error = "history must include at least one assistant message"
        if assistant_error in core_errors:
            waivers.append(assistant_error)

        required_tools_error = (
            "expectedTools.required must include at least one tool "
            "before approval when toolCalls are present"
        )
        if required_tools_error in core_errors:
            waivers.append(required_tools_error)

        return waivers

    def rag_compat_data(self, item: AgenticGroundTruthEntry) -> dict[str, Any]:
        return item.get_plugin_data(_RAG_COMPAT_KIND) or {}

    def refs_from_item(self, item: AgenticGroundTruthEntry) -> list[Any]:
        return compat_refs_from_payload(
            {
                "plugins": item.plugins,
                "toolCalls": item.tool_calls,
                "history": item.history,
            }
        )

    def reference_count(self, item: AgenticGroundTruthEntry) -> int:
        refs = self.refs_from_item(item)
        if refs:
            return len(refs)
        compat = self.rag_compat_data(item)
        explicit_total = compat.get("totalReferences")
        return explicit_total if isinstance(explicit_total, int) and explicit_total > 0 else 0

    def replace_references(
        self, item: AgenticGroundTruthEntry, refs: list[Reference]
    ) -> AgenticGroundTruthEntry:
        compat = dict(self.rag_compat_data(item))
        for legacy_key in _LEGACY_KEYS_TO_DROP:
            compat.pop(legacy_key, None)
        if refs:
            compat[_PLUGIN_REFERENCES_KEY] = [
                ref.model_dump(by_alias=True, exclude_none=True) for ref in refs
            ]
        else:
            compat.pop(_PLUGIN_REFERENCES_KEY, None)
        item.set_plugin(_RAG_COMPAT_KIND, compat)
        return item

    def attach_reference(
        self, item: AgenticGroundTruthEntry, ref: Reference
    ) -> AgenticGroundTruthEntry:
        current = list(self.refs_from_item(item))
        current.append(ref)
        return self.replace_references(item, current)

    def detach_reference(
        self, item: AgenticGroundTruthEntry, ref_url: str
    ) -> AgenticGroundTruthEntry:
        remaining = [r for r in self.refs_from_item(item) if getattr(r, "url", None) != ref_url]
        return self.replace_references(item, remaining)

    def get_explorer_fields(self) -> list[ExplorerFieldDefinition]:
        return [
            ExplorerFieldDefinition(
                key="rag-compat:totalReferences",
                label="References",
                field_type="number",
                sortable=True,
                filterable=True,
            )
        ]

    def get_import_transforms(self) -> list[ImportTransform]:
        return [
            ImportTransform(
                name="rag-compat:normalize-legacy-payload",
                description="Normalize legacy RAG fields into generic history and rag-compat references",
                transform=normalize_legacy_payload_for_core_model,
            )
        ]

    def get_export_transforms(self) -> list[ExportTransform]:
        return [
            ExportTransform(
                name="rag-compat:project-references",
                description="Project rag-compat references into export payloads",
                transform=apply_export_projection,
            )
        ]
