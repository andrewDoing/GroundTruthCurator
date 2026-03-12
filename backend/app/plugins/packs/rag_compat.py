"""RAG compatibility pack.

This pack owns retrieval-specific behavior on the generic agentic host:
- Validates its own plugin-kind constant at startup so mismatches are detected
  before any data is processed.
- Projects per-item RAG state from ``plugins["rag-compat"].data`` via the
  compat-accessor helpers already present on AgenticGroundTruthEntry.
- Provides the canonical ``rag_compat_data``, ``refs_from_item``,
  ``attach_reference``, and ``detach_reference`` helpers so reference
  manipulation stays in one owned location rather than being inlined across
  multiple services.
- Contributes approval validation hooks that enforce RAG-specific invariants on
  top of the generic core checks.

Retrieval search remains available through the standard ``/v1/search`` endpoint
(backed by SearchService), which handles the generic query path independently.
Reference selection and attachment are owned by this pack.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.plugins.base import ExplorerFieldDefinition, ExportTransform, PluginPack

if TYPE_CHECKING:
    from app.domain.models import AgenticGroundTruthEntry, Reference

logger = logging.getLogger(__name__)

# The plugin-kind key stored inside AgenticGroundTruthEntry.plugins.
# This MUST match AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN.
# validate_registration() enforces this at startup.
_RAG_COMPAT_KIND: str = "rag-compat"

_LEGACY_PLUGIN_FIELDS: tuple[str, ...] = (
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
)

_LEGACY_PLUGIN_FIELD_ALIASES: dict[str, str] = {
    "synth_question": "synthQuestion",
    "edited_question": "editedQuestion",
    "context_used_for_generation": "contextUsedForGeneration",
    "context_source": "contextSource",
    "model_used_for_generation": "modelUsedForGeneration",
    "semantic_cluster_number": "semanticClusterNumber",
    "sampling_bucket": "samplingBucket",
    "question_length": "questionLength",
    "total_references": "totalReferences",
}


def _coerce_reference_list(raw_refs: Any) -> list[Any]:
    if not isinstance(raw_refs, list):
        return []

    from app.domain.models import Reference

    return [ref if isinstance(ref, Reference) else Reference.model_validate(ref) for ref in raw_refs]


def _history_message(history: Any, role: str, *, reverse: bool = False) -> str | None:
    if not isinstance(history, list):
        return None
    iterator = reversed(history) if reverse else history
    for turn in iterator:
        if hasattr(turn, "role") and hasattr(turn, "msg"):
            current_role = str(getattr(turn, "role", "")).strip().lower()
            current_msg = str(getattr(turn, "msg", "")).strip()
        elif isinstance(turn, dict):
            current_role = str(turn.get("role", "")).strip().lower()
            current_msg = str(turn.get("msg") or turn.get("content") or "").strip()
        else:
            continue
        if current_role == role and current_msg:
            return current_msg
    return None


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


def normalize_legacy_payload_for_core_model(
    value: object, *, plugin_name: str = _RAG_COMPAT_KIND
) -> object:
    if not isinstance(value, dict):
        return value

    data = dict(value)
    data.pop("tags", None)
    legacy_payload: dict[str, Any] = {}

    for alias, canonical in _LEGACY_PLUGIN_FIELD_ALIASES.items():
        if alias not in data:
            continue
        alias_value = data.pop(alias)
        if canonical not in data:
            data[canonical] = alias_value

    for field_name in _LEGACY_PLUGIN_FIELDS:
        if field_name in data:
            legacy_payload[field_name] = data.pop(field_name)

    if "refs" in legacy_payload:
        legacy_payload["refs"] = _coerce_reference_list(legacy_payload["refs"])

    history_value = data.get("history")
    if isinstance(history_value, list):
        normalized_history: list[dict[str, Any]] = []
        history_annotations: list[dict[str, Any]] = []
        saw_history_annotations = False
        for raw_entry in history_value:
            if hasattr(raw_entry, "model_dump"):
                entry_dict = raw_entry.model_dump(by_alias=True, exclude_none=True)
            elif isinstance(raw_entry, dict):
                entry_dict = dict(raw_entry)
            else:
                normalized_history.append(raw_entry)
                history_annotations.append({})
                continue

            annotation: dict[str, Any] = {}
            if "refs" in entry_dict:
                annotation["refs"] = _coerce_reference_list(entry_dict.pop("refs"))
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

    if not legacy_payload:
        return data

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
    plugin_data.update(legacy_payload)
    plugin_dict["kind"] = plugin_dict.get("kind") or plugin_name
    plugin_dict["version"] = plugin_dict.get("version") or "1.0"
    plugin_dict["data"] = plugin_data
    plugins_payload[plugin_name] = plugin_dict
    data["plugins"] = plugins_payload
    return data


def compat_refs_from_payload(
    payload: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND
) -> list[Any]:
    compat = rag_compat_data_from_payload(payload, plugin_name=plugin_name)
    refs = _coerce_reference_list(compat.get("refs"))
    if refs:
        return refs

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
                step_by_tool_call_id[tool_call_id] = step_number if isinstance(step_number, int) else None

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
            candidate_tool_call_id = candidate.get("toolCallId") or (
                tool_call_id if tool_call_id != RagCompatPack._UNASSOCIATED_KEY else None
            )
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


def compat_total_references_from_payload(
    payload: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND
) -> int:
    compat = rag_compat_data_from_payload(payload, plugin_name=plugin_name)
    explicit_total = compat.get("totalReferences")
    if isinstance(explicit_total, int):
        return explicit_total

    history_count = 0
    history_annotations = compat.get("historyAnnotations")
    if isinstance(history_annotations, list):
        for annotation in history_annotations:
            if isinstance(annotation, dict) and isinstance(annotation.get("refs"), list):
                history_count += len(annotation["refs"])
    if history_count:
        return history_count
    return len(compat_refs_from_payload(payload, plugin_name=plugin_name))


def apply_export_projection(doc: dict[str, Any], *, plugin_name: str = _RAG_COMPAT_KIND) -> dict[str, Any]:
    projected = dict(doc)
    compat = rag_compat_data_from_payload(projected, plugin_name=plugin_name)
    if not compat:
        return projected

    refs = compat_refs_from_payload(projected, plugin_name=plugin_name)
    projected["refs"] = [ref.model_dump(by_alias=True, exclude_none=True) for ref in refs]
    projected["totalReferences"] = len(refs)

    if projected.get("synthQuestion") is None:
        projected["synthQuestion"] = compat.get("synthQuestion") or _history_message(
            projected.get("history"), "user"
        )
    if projected.get("editedQuestion") is None:
        projected["editedQuestion"] = compat.get("editedQuestion") or projected.get("synthQuestion")
    if projected.get("answer") is None:
        projected["answer"] = compat.get("answer") or _history_message(
            projected.get("history"), "assistant", reverse=True
        )

    return projected


class RagCompatPack(PluginPack):
    """RAG compatibility pack.

    Owns retrieval-specific behavior behind the generic plugin-pack contract.
    Registered at startup via PluginPackRegistry so misconfiguration raises
    a clear startup error instead of silently producing wrong data.

    Design notes:
    - The ``rag-compat`` plugin payload is written by
      AgenticGroundTruthEntry.translate_legacy_payload_for_core_model during
      ingest of legacy RAG-shaped documents.
    - Core approval checks (history, tool-call consistency) run before pack
      hooks. The pack adds RAG-specific approval gates that cannot be expressed
      generically.
    - The pack does NOT add new top-level fields to the host model; all RAG
      state is accessed via plugins["rag-compat"].data.
    - Reference attachment and detachment are owned by this pack; the generic
      SearchService only owns the query path.
    """

    @property
    def name(self) -> str:
        return _RAG_COMPAT_KIND

    def validate_registration(self) -> None:
        """Validate that the rag-compat kind constant matches the host model.

        Fails startup if someone renames the plugin key in
        AgenticGroundTruthEntry without updating this pack (or vice-versa).
        """
        from app.domain.models import AgenticGroundTruthEntry

        expected = AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN
        if expected != _RAG_COMPAT_KIND:
            raise ValueError(
                f"RagCompatPack kind '{_RAG_COMPAT_KIND}' does not match "
                f"AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN '{expected}'. "
                "Update _RAG_COMPAT_KIND in rag_compat.py to keep them in sync."
            )
        logger.debug(
            "rag_compat_pack.validate_registration.ok | kind=%s", _RAG_COMPAT_KIND
        )

    def collect_approval_errors(self, item: AgenticGroundTruthEntry) -> list[str]:
        """Return RAG-specific approval errors for an item.

        Items that have no RAG compat data receive no additional errors.
        """
        compat = self.rag_compat_data(item)
        if not compat:
            return []
        # RAG items: future validation hooks go here.
        # e.g. per-retrieval-call selection completeness could be enforced once
        # FR-029/FR-030 retrieval tool-call per-call state is implemented.
        return []

    def collect_approval_waivers(
        self, item: AgenticGroundTruthEntry, core_errors: list[str]
    ) -> list[str]:
        """Waive core errors that do not apply to RAG retrieval-only items.

        When an item has ``totalReferences > 0`` (indicating it is a
        retrieval-based item), the following core checks are waived:
        - "history must include at least one assistant message" — retrieval-only
          items may not produce an assistant reply.
        - "expectedTools.required must include at least one tool…" — retrieval
          items may use reference attachment instead of classified tool calls.
        """
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

    # ------------------------------------------------------------------
    # Accessor helpers — owned by this pack so callers don't embed the
    # plugin-kind string literal elsewhere.
    # ------------------------------------------------------------------

    def rag_compat_data(self, item: AgenticGroundTruthEntry) -> dict[str, Any]:
        """Return the raw rag-compat plugin data dict for an item, or {}."""
        return item.get_plugin_data(_RAG_COMPAT_KIND) or {}

    def refs_from_item(self, item: AgenticGroundTruthEntry) -> list[Any]:
        """Return the references list projected from the rag-compat payload."""
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
        serialized = [ref.model_dump(by_alias=True, exclude_none=True) for ref in refs]
        item._set_rag_compat_value("refs", serialized)
        item._set_rag_compat_value("retrievals", None)
        # Clear cached totalReferences so it will be recomputed from refs/historyAnnotations
        if "totalReferences" in item.__dict__:
            del item.__dict__["totalReferences"]
        item._set_rag_compat_value("totalReferences", None)  # Remove from plugin storage too
        return item

    def attach_reference(self, item: AgenticGroundTruthEntry, ref: Reference) -> AgenticGroundTruthEntry:
        """Attach a reference to an item via the rag-compat plugin payload.

        This is a RAG-compat concern; the generic core does not manage refs.
        The ``refs`` setter on AgenticGroundTruthEntry writes to
        ``plugins["rag-compat"].data`` automatically.

        Args:
            item: The ground-truth item to modify in-place.
            ref: The reference to attach.

        Returns:
            The same item (mutated in-place) for convenience.
        """
        current = list(self.refs_from_item(item))
        current.append(ref)
        return self.replace_references(item, current)

    def detach_reference(self, item: AgenticGroundTruthEntry, ref_url: str) -> AgenticGroundTruthEntry:
        """Detach a reference from an item by URL, using the rag-compat payload.

        This is a RAG-compat concern; the generic core does not manage refs.

        Args:
            item: The ground-truth item to modify in-place.
            ref_url: The URL of the reference to remove.

        Returns:
            The same item (mutated in-place) for convenience.
        """
        remaining = [r for r in self.refs_from_item(item) if getattr(r, "url", None) != ref_url]
        return self.replace_references(item, remaining)

    # ------------------------------------------------------------------
    # Per-tool-call retrieval state (Phase 6 — retrieval normalization)
    #
    # New items store references per retrieval tool call inside
    # ``plugins["rag-compat"].data.retrievals``.
    # Read path: per-call state first, then fall back to top-level refs.
    # Write path: always to per-call state.
    # ------------------------------------------------------------------

    _UNASSOCIATED_KEY: str = "_unassociated"

    def get_retrievals(self, item: AgenticGroundTruthEntry) -> dict[str, Any]:
        """Return the full retrievals dict or {} when absent."""
        compat = self.rag_compat_data(item)
        retrievals = compat.get("retrievals")
        return dict(retrievals) if isinstance(retrievals, dict) else {}

    def get_retrieval_candidates(
        self, item: AgenticGroundTruthEntry, tool_call_id: str
    ) -> list[dict[str, Any]]:
        """Return candidate list for one tool call, or []."""
        retrievals = self.get_retrievals(item)
        bucket = retrievals.get(tool_call_id)
        if isinstance(bucket, dict):
            cands = bucket.get("candidates")
            return list(cands) if isinstance(cands, list) else []
        return []

    def set_retrieval_candidates(
        self,
        item: AgenticGroundTruthEntry,
        tool_call_id: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        """Set candidates for a single tool call (write-through to plugin data)."""
        compat = self.rag_compat_data(item)
        retrievals = dict(compat.get("retrievals") or {})
        retrievals[tool_call_id] = {"candidates": candidates}
        item._set_rag_compat_value("retrievals", retrievals)

    def set_retrievals(
        self,
        item: AgenticGroundTruthEntry,
        retrievals: dict[str, Any],
    ) -> None:
        """Replace the entire retrievals dict."""
        item._set_rag_compat_value("retrievals", retrievals)

    def has_per_call_state(self, item: AgenticGroundTruthEntry) -> bool:
        """Return True when per-call retrieval state exists."""
        compat = self.rag_compat_data(item)
        retrievals = compat.get("retrievals")
        return isinstance(retrievals, dict) and len(retrievals) > 0

    def get_all_candidates_flat(
        self, item: AgenticGroundTruthEntry
    ) -> list[dict[str, Any]]:
        """Flatten all per-call candidates into a single list.

        Read path: returns per-call candidates when present.  Falls back
        to converting top-level refs into candidate dicts for backward compat.
        """
        if self.has_per_call_state(item):
            result: list[dict[str, Any]] = []
            for tool_call_id, bucket in self.get_retrievals(item).items():
                if not isinstance(bucket, dict):
                    continue
                cands = bucket.get("candidates")
                if isinstance(cands, list):
                    for c in cands:
                        entry = dict(c) if isinstance(c, dict) else {}
                        if "toolCallId" not in entry:
                            entry["toolCallId"] = tool_call_id
                        result.append(entry)
            return result

        # Backward compat: convert top-level refs to candidate shape
        refs = item.refs
        return [
            {
                "url": getattr(r, "url", ""),
                "title": getattr(r, "title", None),
                "chunk": getattr(r, "content", None),
                "relevance": None,
                "toolCallId": None,
            }
            for r in refs
        ]

    def get_explorer_fields(self) -> list[ExplorerFieldDefinition]:
        return [
            ExplorerFieldDefinition(
                key="rag-compat:totalReferences",
                label="References",
                field_type="number",
                sortable=True,
                filterable=True,
            ),
            ExplorerFieldDefinition(
                key="rag-compat:perCallRetrievals",
                label="Per-Call Retrievals",
                field_type="boolean",
                filterable=True,
            ),
        ]

    def get_export_transforms(self) -> list[ExportTransform]:
        return [
            ExportTransform(
                name="rag-compat:project-legacy-export-fields",
                description="Project rag-compat retrieval/reference fields into export payloads",
                transform=apply_export_projection,
            )
        ]

    def migrate_refs_to_per_call(
        self, item: AgenticGroundTruthEntry
    ) -> bool:
        """Migrate top-level refs into per-call state (idempotent).

        Associates refs with retrieval tool calls by matching
        ``messageIndex`` to tool-call step ordering when possible.
        Refs that cannot be matched go into the ``_unassociated`` bucket.

        Returns True if migration produced changes.
        """
        if self.has_per_call_state(item):
            return False

        refs = item.refs
        if not refs:
            return False

        # Build a map from step/messageIndex to tool call id
        tool_calls = item.tool_calls or []
        step_to_tc: dict[int | None, str] = {}
        for tc in tool_calls:
            if tc.step_number is not None:
                step_to_tc[tc.step_number] = tc.id

        retrievals: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for ref in refs:
            mi = getattr(ref, "messageIndex", None)
            tc_id = step_to_tc.get(mi) if mi is not None else None
            key = tc_id or self._UNASSOCIATED_KEY

            if key not in retrievals:
                retrievals[key] = {"candidates": []}
            retrievals[key]["candidates"].append({
                "url": getattr(ref, "url", ""),
                "title": getattr(ref, "title", None),
                "chunk": getattr(ref, "content", None),
                "relevance": None,
                "rawPayload": None,
                "toolCallId": key if key != self._UNASSOCIATED_KEY else None,
            })

        self.set_retrievals(item, retrievals)
        return True
