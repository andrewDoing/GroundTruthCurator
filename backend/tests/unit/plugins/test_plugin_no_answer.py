"""Unit tests for the NoAnswerPlugin computed tag plugin."""

from __future__ import annotations

from app.plugins.computed_tags.no_answer import NoAnswerPlugin
from tests.test_helpers import make_test_entry


class TestNoAnswerPlugin:
    """Tests for the NoAnswerPlugin."""

    def test_no_answer_exact_match(self):
        """Should return tag when answer is exactly NO_ANSWER."""
        plugin = NoAnswerPlugin()
        item = make_test_entry(
            id="test", dataset_name="test", synth_question="Q", answer="NO_ANSWER"
        )
        assert plugin.compute(item) == "answer:no_answer"

    def test_no_answer_with_whitespace(self):
        """Should return tag when answer is NO_ANSWER with surrounding whitespace."""
        plugin = NoAnswerPlugin()
        item = make_test_entry(
            id="test", dataset_name="test", synth_question="Q", answer="  NO_ANSWER  "
        )
        assert plugin.compute(item) == "answer:no_answer"

    def test_no_answer_with_newlines(self):
        """Should return tag when answer is NO_ANSWER with newlines."""
        plugin = NoAnswerPlugin()
        item = make_test_entry(
            id="test", dataset_name="test", synth_question="Q", answer="\nNO_ANSWER\n"
        )
        assert plugin.compute(item) == "answer:no_answer"

    def test_regular_answer_returns_none(self):
        """Should return None for regular answers."""
        plugin = NoAnswerPlugin()
        item = make_test_entry(
            id="test", dataset_name="test", synth_question="Q", answer="A valid answer"
        )
        assert plugin.compute(item) is None

    def test_none_answer_returns_none(self):
        """Should return None when answer is None."""
        plugin = NoAnswerPlugin()
        item = make_test_entry(id="test", dataset_name="test", synth_question="Q", answer=None)
        assert plugin.compute(item) is None

    def test_empty_answer_returns_none(self):
        """Should return None when answer is empty string."""
        plugin = NoAnswerPlugin()
        item = make_test_entry(id="test", dataset_name="test", synth_question="Q", answer="")
        assert plugin.compute(item) is None
