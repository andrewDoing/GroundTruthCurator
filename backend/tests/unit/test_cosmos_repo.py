from __future__ import annotations

from datetime import datetime, timezone

import pytest  # type: ignore[import-not-found]

from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo
from app.domain.enums import GroundTruthStatus, SortField, SortOrder
from app.domain.models import GroundTruthItem


@pytest.fixture()
def repo() -> CosmosGroundTruthRepo:
    return CosmosGroundTruthRepo(
        endpoint="https://example.com",
        key="dummy",
        db_name="test-db",
        gt_container_name="ground-truth",
        assignments_container_name="assignments",
        connection_verify=False,
        test_mode=True,
    )


def test_build_query_filter_no_filters(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(None, None, None, None)
    assert where == " WHERE c.docType = 'ground-truth-item'"
    assert params == []


def test_build_query_filter_with_status(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(GroundTruthStatus.draft, None, None, None)
    assert "c.status = @status" in where
    assert {"name": "@status", "value": GroundTruthStatus.draft.value} in params


def test_build_query_filter_with_dataset(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(None, "faq", None, None)
    assert "c.datasetName = @dataset" in where
    assert {"name": "@dataset", "value": "faq"} in params


def test_build_query_filter_with_tags_and_logic(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(None, None, ["sme", "validation"], None)
    # Tags search across manualTags and computedTags
    assert "ARRAY_CONTAINS(c.manualTags, @tag0)" in where
    assert "ARRAY_CONTAINS(c.computedTags, @tag0)" in where
    assert "ARRAY_CONTAINS(c.manualTags, @tag1)" in where
    assert "ARRAY_CONTAINS(c.computedTags, @tag1)" in where
    assert {"name": "@tag0", "value": "sme"} in params
    assert {"name": "@tag1", "value": "validation"} in params


def test_build_query_filter_all_filters_combined(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(
        GroundTruthStatus.approved,
        "kb",
        ["tag-a", "tag-b"],
        None,
    )
    assert "c.status = @status" in where
    assert "c.datasetName = @dataset" in where
    # 4 ARRAY_CONTAINS: 2 for each tag (manualTags, computedTags)
    assert where.count("ARRAY_CONTAINS") == 4
    assert {"name": "@status", "value": GroundTruthStatus.approved.value} in params
    assert {"name": "@dataset", "value": "kb"} in params


def test_build_query_filter_ignore_tags_when_disabled(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(None, None, ["sme"], None, include_tags=False)
    assert "ARRAY_CONTAINS" not in where
    assert params == []


def test_build_query_filter_with_exclude_tags(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(None, None, None, ["archived", "spam"])
    # Exclude tags use NOT logic
    assert "NOT (ARRAY_CONTAINS(c.manualTags, @excludeTag0)" in where
    assert "NOT (ARRAY_CONTAINS(c.manualTags, @excludeTag1)" in where
    assert {"name": "@excludeTag0", "value": "archived"} in params
    assert {"name": "@excludeTag1", "value": "spam"} in params


def test_build_query_filter_with_include_and_exclude_tags(repo: CosmosGroundTruthRepo) -> None:
    where, params = repo._build_query_filter(None, None, ["important"], ["spam"])
    # Should have both include and exclude clauses
    assert "ARRAY_CONTAINS(c.manualTags, @tag0)" in where
    assert "NOT (ARRAY_CONTAINS(c.manualTags, @excludeTag0)" in where
    assert {"name": "@tag0", "value": "important"} in params
    assert {"name": "@excludeTag0", "value": "spam"} in params


def test_resolve_sort_defaults(repo: CosmosGroundTruthRepo) -> None:
    field, direction = repo._resolve_sort(None, None)
    assert field is SortField.reviewed_at
    assert direction is SortOrder.desc


def test_resolve_sort_with_overrides(repo: CosmosGroundTruthRepo) -> None:
    field, direction = repo._resolve_sort(SortField.updated_at, SortOrder.asc)
    assert field is SortField.updated_at
    assert direction is SortOrder.asc


def test_sort_key_has_answer(repo: CosmosGroundTruthRepo) -> None:
    example = GroundTruthItem.model_validate(
        {
            "id": "item",
            "datasetName": "faq",
            "synthQuestion": "What?",
            "answer": "value",
            "manualTags": ["team:sme"],
            "reviewedAt": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
    )
    key = CosmosGroundTruthRepo._sort_key(example, SortField.has_answer)
    assert key[0] == 1


# =============================================================================
# Tests for _compute_total_references
# =============================================================================


class TestComputeTotalReferences:
    """Unit tests for CosmosGroundTruthRepo._compute_total_references.

    The method calculates total references with the following logic:
    - If history has refs, count only history refs (history takes priority)
    - If history has no refs, count item-level refs as fallback
    """

    def _make_item(
        self,
        refs: list[dict] | None = None,
        history: list[dict] | None = None,
    ) -> GroundTruthItem:
        """Helper to create a GroundTruthItem with specified refs and history."""
        data: dict = {
            "id": "test-item",
            "datasetName": "test-dataset",
            "synthQuestion": "Test question?",
        }
        if refs is not None:
            data["refs"] = refs
        if history is not None:
            data["history"] = history
        return GroundTruthItem.model_validate(data)

    # -------------------------------------------------------------------------
    # History refs take priority over item refs
    # -------------------------------------------------------------------------

    def test_history_refs_take_priority_over_item_refs(self) -> None:
        """When history has refs, only history refs are counted (item refs ignored)."""
        item = self._make_item(
            refs=[{"url": "https://item-ref-1.com"}, {"url": "https://item-ref-2.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi", "refs": [{"url": "https://history-ref.com"}]},
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # Should count only history refs (1), not item refs (2)
        assert result == 1

    def test_history_refs_from_multiple_turns(self) -> None:
        """Refs from all history turns are summed."""
        item = self._make_item(
            refs=[{"url": "https://ignored.com"}],
            history=[
                {"role": "user", "msg": "Q1"},
                {
                    "role": "assistant",
                    "msg": "A1",
                    "refs": [{"url": "https://ref1.com"}, {"url": "https://ref2.com"}],
                },
                {"role": "user", "msg": "Q2"},
                {"role": "assistant", "msg": "A2", "refs": [{"url": "https://ref3.com"}]},
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # Should count all history refs: 2 + 1 = 3
        assert result == 3

    # -------------------------------------------------------------------------
    # Item refs used when no history refs exist
    # -------------------------------------------------------------------------

    def test_item_refs_fallback_when_no_history(self) -> None:
        """Item refs are counted when there is no history."""
        item = self._make_item(
            refs=[
                {"url": "https://ref1.com"},
                {"url": "https://ref2.com"},
                {"url": "https://ref3.com"},
            ],
            history=None,
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 3

    def test_item_refs_fallback_when_history_empty(self) -> None:
        """Item refs are counted when history is an empty list."""
        item = self._make_item(
            refs=[{"url": "https://ref1.com"}, {"url": "https://ref2.com"}],
            history=[],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 2

    def test_item_refs_fallback_when_history_has_no_refs(self) -> None:
        """Item refs are counted when history exists but contains no refs."""
        item = self._make_item(
            refs=[{"url": "https://item-ref.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi"},  # No refs
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # History has 0 refs, so item refs (1) should be used
        assert result == 1

    def test_item_refs_fallback_when_history_refs_are_empty_lists(self) -> None:
        """Item refs are counted when history refs are empty lists."""
        item = self._make_item(
            refs=[{"url": "https://item-ref.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi", "refs": []},  # Empty refs list
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # History refs total is 0, so item refs (1) should be used
        assert result == 1

    # -------------------------------------------------------------------------
    # Handle empty/null refs and history
    # -------------------------------------------------------------------------

    def test_zero_when_no_refs_anywhere(self) -> None:
        """Returns 0 when there are no refs at any level."""
        item = self._make_item(refs=None, history=None)
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 0

    def test_zero_when_empty_refs_and_no_history(self) -> None:
        """Returns 0 when refs is empty list and no history."""
        item = self._make_item(refs=[], history=None)
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 0

    def test_zero_when_empty_refs_and_empty_history(self) -> None:
        """Returns 0 when refs is empty and history is empty list."""
        item = self._make_item(refs=[], history=[])
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 0

    def test_handles_none_refs_in_history_turn(self) -> None:
        """Handles history turns where refs is explicitly None."""
        item = self._make_item(
            refs=[{"url": "https://item-ref.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi", "refs": None},  # Explicitly None
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # History refs is 0, fallback to item refs
        assert result == 1

    # -------------------------------------------------------------------------
    # Complex scenarios with partial data
    # -------------------------------------------------------------------------

    def test_mixed_history_some_turns_with_refs_some_without(self) -> None:
        """History with mix of turns with and without refs."""
        item = self._make_item(
            refs=[{"url": "https://ignored.com"}],
            history=[
                {"role": "user", "msg": "Q1"},
                {"role": "assistant", "msg": "A1"},  # No refs
                {"role": "user", "msg": "Q2"},
                {"role": "assistant", "msg": "A2", "refs": [{"url": "https://ref1.com"}]},
                {"role": "user", "msg": "Q3"},
                {"role": "assistant", "msg": "A3", "refs": None},  # Explicitly None
                {"role": "user", "msg": "Q4"},
                {
                    "role": "assistant",
                    "msg": "A4",
                    "refs": [{"url": "https://ref2.com"}, {"url": "https://ref3.com"}],
                },
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # History refs: 0 + 1 + 0 + 2 = 3
        assert result == 3

    def test_user_turns_with_refs_are_counted(self) -> None:
        """Refs on user turns are also counted (not just assistant turns)."""
        item = self._make_item(
            refs=[{"url": "https://ignored.com"}],
            history=[
                {"role": "user", "msg": "Here's a doc", "refs": [{"url": "https://user-ref.com"}]},
                {
                    "role": "assistant",
                    "msg": "Thanks",
                    "refs": [{"url": "https://assistant-ref.com"}],
                },
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # Both user and assistant refs are counted: 1 + 1 = 2
        assert result == 2

    def test_many_refs_in_single_turn(self) -> None:
        """Handles turns with many references."""
        many_refs = [{"url": f"https://ref{i}.com"} for i in range(10)]
        item = self._make_item(
            history=[
                {"role": "user", "msg": "Q"},
                {"role": "assistant", "msg": "A", "refs": many_refs},
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 10

    def test_item_only_no_history_field_at_all(self) -> None:
        """Item created without history field entirely."""
        data = {
            "id": "minimal-item",
            "datasetName": "test",
            "synthQuestion": "What?",
            "refs": [{"url": "https://only-ref.com"}],
        }
        item = GroundTruthItem.model_validate(data)
        result = CosmosGroundTruthRepo._compute_total_references(item)
        assert result == 1

    def test_complex_real_world_scenario(self) -> None:
        """Realistic multi-turn conversation with various ref patterns."""
        item = self._make_item(
            # Item-level refs (should be ignored if history has any refs)
            refs=[{"url": "https://old-ref.com"}],
            history=[
                # Turn 1: User asks question
                {"role": "user", "msg": "How do I fix error X?"},
                # Turn 2: Assistant responds with 2 refs
                {
                    "role": "assistant",
                    "msg": "You can try these solutions...",
                    "refs": [
                        {"url": "https://kb.example.com/article1"},
                        {"url": "https://docs.example.com/troubleshooting"},
                    ],
                },
                # Turn 3: User follow-up
                {"role": "user", "msg": "That didn't work, any other ideas?"},
                # Turn 4: Assistant with 1 more ref
                {
                    "role": "assistant",
                    "msg": "Let's try this instead...",
                    "refs": [{"url": "https://kb.example.com/article2"}],
                },
                # Turn 5: User confirms
                {"role": "user", "msg": "That worked, thanks!"},
                # Turn 6: Assistant closes (no refs needed)
                {"role": "assistant", "msg": "Glad I could help!"},
            ],
        )
        result = CosmosGroundTruthRepo._compute_total_references(item)
        # History refs: 2 + 1 = 3 (item-level ref is ignored)
        assert result == 3
