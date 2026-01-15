"""Unit tests for the retrieval behavior computed tag plugins."""

from __future__ import annotations

import pytest

from app.domain.models import GroundTruthItem, Reference, HistoryItem
from app.domain.enums import HistoryItemRole
from app.plugins.computed_tags.retrieval_behavior import (
    RetrievalBehaviorNoRefsPlugin,
    RetrievalBehaviorSinglePlugin,
    RetrievalBehaviorTwoRefsPlugin,
    RetrievalBehaviorRichPlugin,
)


class TestRetrievalBehaviorPlugins:
    """Tests for retrieval behavior classification plugins."""

    @pytest.mark.parametrize(
        "num_refs,expected_tag",
        [
            (0, "retrieval_behavior:no_refs"),
            (1, "retrieval_behavior:single"),
            (2, "retrieval_behavior:two_refs"),
            (3, "retrieval_behavior:rich"),
            (5, "retrieval_behavior:rich"),
            (10, "retrieval_behavior:rich"),
        ],
    )
    def test_mutually_exclusive_classification(self, num_refs, expected_tag):
        """Each document gets exactly one retrieval behavior tag."""
        item = GroundTruthItem(
            id=f"test-{num_refs}-refs",
            datasetName="test-dataset",
            synthQuestion="Question",
            refs=[Reference(url=f"https://example.com/doc{i}") for i in range(num_refs)],
        )

        plugins = [
            RetrievalBehaviorNoRefsPlugin(),
            RetrievalBehaviorSinglePlugin(),
            RetrievalBehaviorTwoRefsPlugin(),
            RetrievalBehaviorRichPlugin(),
        ]

        results = [p.compute(item) for p in plugins]
        non_none = [r for r in results if r is not None]

        assert len(non_none) == 1, f"Expected exactly 1 match for {num_refs} refs"
        assert non_none[0] == expected_tag

    def test_refs_in_history_are_counted(self):
        """References in history turns are included in the count."""
        item = GroundTruthItem(
            id="test-history-refs",
            datasetName="test-dataset",
            synthQuestion="Follow up question",
            history=[
                HistoryItem(role=HistoryItemRole.user, msg="First question"),
                HistoryItem(
                    role=HistoryItemRole.assistant,
                    msg="First answer",
                    refs=[
                        Reference(url="https://example.com/doc1"),
                        Reference(url="https://example.com/doc2"),
                    ],
                ),
                HistoryItem(role=HistoryItemRole.user, msg="Second question"),
                HistoryItem(
                    role=HistoryItemRole.assistant,
                    msg="Second answer",
                    refs=[Reference(url="https://example.com/doc3")],
                ),
            ],
        )
        # 3 refs total in history -> rich
        assert RetrievalBehaviorRichPlugin().compute(item) == "retrieval_behavior:rich"
