"""Computed tag plugins for conversation turn classification.

This module provides plugins that tag documents based on their
conversation history (single-turn vs multi-turn).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.base import ComputedTagPlugin

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem


class MultiTurnPlugin(ComputedTagPlugin):
    """Tags documents that have multi-turn conversation history.

    Applies the 'turns:multiturn' tag if the document has a non-empty
    history field with at least 2 turns.
    """

    @property
    def tag_key(self) -> str:
        return "turns:multiturn"

    def compute(self, doc: GroundTruthItem) -> str | None:
        history = doc.history
        if not history or not isinstance(history, list):
            return None
        return self.tag_key if len(history) > 2 else None


class SingleTurnPlugin(ComputedTagPlugin):
    """Tags documents that are single-turn (no multi-turn history).

    Applies the 'turns:singleturn' tag if the document has no history
    or has fewer than 2 turns.
    """

    @property
    def tag_key(self) -> str:
        return "turns:singleturn"

    def compute(self, doc: GroundTruthItem) -> str | None:
        history = doc.history
        if not history or not isinstance(history, list):
            return self.tag_key
        return self.tag_key if len(history) <= 2 else None
