"""Unit tests for the question length computed tag plugins."""

from __future__ import annotations

import pytest

from app.domain.models import GroundTruthItem
from app.plugins.computed_tags.question_length import (
    QuestionLengthLongPlugin,
    QuestionLengthMediumPlugin,
    QuestionLengthShortPlugin,
)


class TestQuestionLengthPlugins:
    """Tests for question length classification plugins."""

    @pytest.mark.parametrize(
        "word_count,expected_short,expected_medium,expected_long",
        [
            (0, "question_length:short", None, None),  # Empty
            (10, "question_length:short", None, None),  # Boundary: max short
            (11, None, "question_length:medium", None),  # Boundary: min medium
            (30, None, "question_length:medium", None),  # Boundary: max medium
            (31, None, None, "question_length:long"),  # Boundary: min long
            (50, None, None, "question_length:long"),  # Well into long
        ],
    )
    def test_mutually_exclusive_classification(
        self, word_count, expected_short, expected_medium, expected_long
    ):
        """Each document gets exactly one length tag."""
        question = " ".join([f"word{i}" for i in range(word_count)])
        item = GroundTruthItem(
            id="test-id",
            datasetName="test-dataset",
            synthQuestion=question,
        )

        short_plugin = QuestionLengthShortPlugin()
        medium_plugin = QuestionLengthMediumPlugin()
        long_plugin = QuestionLengthLongPlugin()

        assert short_plugin.compute(item) == expected_short
        assert medium_plugin.compute(item) == expected_medium
        assert long_plugin.compute(item) == expected_long

        # Exactly one should match
        results = [
            short_plugin.compute(item),
            medium_plugin.compute(item),
            long_plugin.compute(item),
        ]
        assert sum(1 for r in results if r is not None) == 1

    def test_edited_question_takes_precedence(self):
        """editedQuestion is used over synthQuestion when present."""
        item = GroundTruthItem(
            id="test-id",
            datasetName="test-dataset",
            synthQuestion="short",  # 1 word
            editedQuestion=" ".join([f"word{i}" for i in range(35)]),  # 35 words -> long
        )

        assert QuestionLengthLongPlugin().compute(item) == "question_length:long"
        assert QuestionLengthShortPlugin().compute(item) is None
