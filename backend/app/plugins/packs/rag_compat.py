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

from app.plugins.base import PluginPack

if TYPE_CHECKING:
    from app.domain.models import AgenticGroundTruthEntry, Reference

logger = logging.getLogger(__name__)

# The plugin-kind key stored inside AgenticGroundTruthEntry.plugins.
# This MUST match AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN.
# validate_registration() enforces this at startup.
_RAG_COMPAT_KIND: str = "rag-compat"


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
        if item.totalReferences == 0:
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
        return item.refs

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
        current = list(item.refs)
        current.append(ref)
        item.refs = current
        return item

    def detach_reference(self, item: AgenticGroundTruthEntry, ref_url: str) -> AgenticGroundTruthEntry:
        """Detach a reference from an item by URL, using the rag-compat payload.

        This is a RAG-compat concern; the generic core does not manage refs.

        Args:
            item: The ground-truth item to modify in-place.
            ref_url: The URL of the reference to remove.

        Returns:
            The same item (mutated in-place) for convenience.
        """
        item.refs = [r for r in item.refs if getattr(r, "url", None) != ref_url]
        return item

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
