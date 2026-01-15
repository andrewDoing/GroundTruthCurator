"""Unit tests for the turns computed tag plugins."""

from __future__ import annotations

import pytest

from app.domain.models import GroundTruthItem, HistoryItem
from app.domain.enums import HistoryItemRole
from app.plugins.computed_tags.turns import MultiTurnPlugin, SingleTurnPlugin


class TestTurnsPlugins:
    """Tests for SingleTurnPlugin and MultiTurnPlugin mutual exclusivity."""

    @pytest.mark.parametrize(
        "history_len,expected_single,expected_multi",
        [
            (0, "turns:singleturn", None),  # No history
            (1, "turns:singleturn", None),  # 1 turn
            (2, "turns:singleturn", None),  # 2 turns (boundary)
            (3, None, "turns:multiturn"),  # 3 turns (boundary)
            (5, None, "turns:multiturn"),  # 5 turns
        ],
    )
    def test_mutually_exclusive_classification(self, history_len, expected_single, expected_multi):
        """Each document gets exactly one of singleturn or multiturn."""
        history = (
            [
                HistoryItem(
                    role=HistoryItemRole.user if i % 2 == 0 else HistoryItemRole.assistant,
                    msg=f"Turn {i}",
                )
                for i in range(history_len)
            ]
            if history_len > 0
            else None
        )

        item = GroundTruthItem(
            id="test-id",
            datasetName="test-dataset",
            synthQuestion="Question",
            history=history,
        )

        single_plugin = SingleTurnPlugin()
        multi_plugin = MultiTurnPlugin()

        assert single_plugin.compute(item) == expected_single
        assert multi_plugin.compute(item) == expected_multi

        # Exactly one should match
        results = [single_plugin.compute(item), multi_plugin.compute(item)]
        assert sum(1 for r in results if r is not None) == 1
