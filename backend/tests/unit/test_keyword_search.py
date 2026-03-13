"""Unit tests for keyword search functionality."""

from app.domain.models import HistoryItem
from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo
from tests.test_helpers import make_test_entry


class TestKeywordMatching:
    """Test the _item_matches_keyword method."""

    def test_matches_synth_question(self):
        """Test matching keyword in synth_question field."""
        item = make_test_entry(
            id="test-1",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="What is machine learning?",
            answer=None,
            status="draft",
        )
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "machine")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "MACHINE")  # case-insensitive
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "deep")

    def test_matches_edited_question(self):
        """Test matching keyword in edited_question field."""
        item = make_test_entry(
            id="test-2",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Original question",
            edited_question="What is deep learning?",
            answer=None,
            status="draft",
        )
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "deep")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "LEARNING")
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "machine")

    def test_matches_answer(self):
        """Test matching keyword in answer field."""
        item = make_test_entry(
            id="test-3",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Question",
            answer="Neural networks are a type of machine learning model",
            status="approved",
        )
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "neural")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "NETWORKS")
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "deep")

    def test_matches_history_messages(self):
        """Test matching keyword in history turn messages."""
        item = make_test_entry(
            id="test-4",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Question",
            answer="Answer",
            history=[
                HistoryItem(role="user", msg="Tell me about transformers"),
                HistoryItem(role="assistant", msg="Transformers are a neural architecture"),
            ],
            status="approved",
        )
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "transformers")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "ARCHITECTURE")
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "convolution")

    def test_empty_keyword_matches_all(self):
        """Test that empty keyword matches all items."""
        item = make_test_entry(
            id="test-5",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Question",
            answer="Answer",
            status="draft",
        )
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, None)

    def test_no_match_returns_false(self):
        """Test that non-matching keyword returns False."""
        item = make_test_entry(
            id="test-6",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Question about cats",
            answer="Cats are animals",
            status="draft",
        )
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "dogs")
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "machine learning")

    def test_partial_match(self):
        """Test that partial word matching works (substring)."""
        item = make_test_entry(
            id="test-7",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Question about networking",
            answer="Answer",
            status="draft",
        )
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "network")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "ing")

    def test_handles_none_fields(self):
        """Test that None fields don't cause errors."""
        item = make_test_entry(
            id="test-8",
            dataset_name="test",
            bucket="00000000-0000-0000-0000-000000000001",
            synth_question="Required field",
            edited_question=None,
            answer=None,
            history=None,
            status="draft",
        )
        assert not CosmosGroundTruthRepo._item_matches_keyword(item, "test")
        assert CosmosGroundTruthRepo._item_matches_keyword(item, "")  # empty keyword matches
