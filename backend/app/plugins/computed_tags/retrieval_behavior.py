"""Computed tag plugins for retrieval behavior classification.

This module provides plugins that tag documents based on the number
of references they have:
- no_refs: no references
- single: exactly one reference
- two_refs: exactly two references
- rich: three or more references
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.base import ComputedTagPlugin
from app.plugins.pack_registry import get_default_pack_registry

if TYPE_CHECKING:
    from app.domain.models import AgenticGroundTruthEntry


def _get_total_reference_count(doc: AgenticGroundTruthEntry) -> int:
    """Get the total count of references from a document.

    Uses canonical reference derivation from history/plugin payloads.

    Args:
        doc: The AgenticGroundTruthEntry to evaluate.

    Returns:
        The total number of references.
    """
    count = get_default_pack_registry().plugin_sort_value(doc, "rag-compat:totalReferences")
    return int(count) if isinstance(count, int) else 0


class RetrievalBehaviorNoRefsPlugin(ComputedTagPlugin):
    """Tags documents that have no references.

    Applies the 'retrieval_behavior:no_refs' tag if the document has zero references.
    """

    @property
    def tag_key(self) -> str:
        return "retrieval_behavior:no_refs"

    def compute(self, doc: AgenticGroundTruthEntry) -> str | None:
        return self.tag_key if _get_total_reference_count(doc) == 0 else None


class RetrievalBehaviorSinglePlugin(ComputedTagPlugin):
    """Tags documents that have exactly one reference.

    Applies the 'retrieval_behavior:single' tag if the document has exactly one reference.
    """

    @property
    def tag_key(self) -> str:
        return "retrieval_behavior:single"

    def compute(self, doc: AgenticGroundTruthEntry) -> str | None:
        return self.tag_key if _get_total_reference_count(doc) == 1 else None


class RetrievalBehaviorTwoRefsPlugin(ComputedTagPlugin):
    """Tags documents that have exactly two references.

    Applies the 'retrieval_behavior:two_refs' tag if the document has exactly two references.
    """

    @property
    def tag_key(self) -> str:
        return "retrieval_behavior:two_refs"

    def compute(self, doc: AgenticGroundTruthEntry) -> str | None:
        return self.tag_key if _get_total_reference_count(doc) == 2 else None


class RetrievalBehaviorRichPlugin(ComputedTagPlugin):
    """Tags documents that have three or more references.

    Applies the 'retrieval_behavior:rich' tag if the document has 3+ references.
    """

    @property
    def tag_key(self) -> str:
        return "retrieval_behavior:rich"

    def compute(self, doc: AgenticGroundTruthEntry) -> str | None:
        return self.tag_key if _get_total_reference_count(doc) >= 3 else None
