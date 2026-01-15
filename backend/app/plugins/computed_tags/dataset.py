"""Computed tag plugin for dataset identification.

This module provides a plugin that tags documents with their dataset name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.base import ComputedTagPlugin

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem


class DatasetPlugin(ComputedTagPlugin):
    """Tags documents with their dataset name (dataset:datasetName).

    This is a dynamic tag plugin - the tag value depends on the document's
    datasetName field.

    Example:
        For a document with datasetName="support-tickets", this plugin
        will generate the tag "dataset:support-tickets".
    """

    @property
    def tag_key(self) -> str:
        return "dataset:_dynamic"

    def compute(self, doc: GroundTruthItem) -> str | None:
        return f"dataset:{doc.datasetName}" if doc.datasetName else None
