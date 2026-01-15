"""Computed tag plugin for identifying NO_ANSWER ground truth items.

This module provides a plugin that tags documents where the ground truth
answer is "NO_ANSWER" (whitespace-insensitive).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.base import ComputedTagPlugin

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem


class NoAnswerPlugin(ComputedTagPlugin):
    """Tags documents where the ground truth answer is "NO_ANSWER".

    This plugin identifies cases where there is explicitly no answer
    available for the question, useful for filtering or analysis.

    Example:
        For a document with groundTruthAnswer="NO_ANSWER", this plugin
        will generate the tag "answer:no_answer".
    """

    @property
    def tag_key(self) -> str:
        return "answer:no_answer"

    def compute(self, doc: GroundTruthItem) -> str | None:
        if doc.answer and doc.answer.strip().casefold() == "no_answer":
            return self.tag_key
        return None
