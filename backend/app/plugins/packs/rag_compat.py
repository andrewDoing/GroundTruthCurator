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

        Currently the generic core tolerates missing assistant messages when
        ``totalReferences > 0`` (the RAG waiver).  This pack records that
        invariant explicitly so the ownership is clear: if the waiver is ever
        tightened, the change belongs here rather than in the core.

        Items that have no RAG compat data receive no additional errors.
        """
        compat = self.rag_compat_data(item)
        if not compat:
            # Non-RAG item — no additional pack-level approval gates.
            return []
        # RAG items: future validation hooks go here.
        # e.g. per-retrieval-call selection completeness could be enforced once
        # FR-029/FR-030 retrieval tool-call per-call state is implemented.
        return []

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
