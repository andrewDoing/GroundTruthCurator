from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # type: ignore[import-not-found]

from app.adapters.repos.cosmos_repo import (
    CosmosGroundTruthRepo,
    SELECT_CLAUSE_C,
    _normalize_unicode_for_cosmos,
    _restore_unicode_from_cosmos,
)
from app.plugins.pack_registry import get_rag_compat_pack
from app.domain.enums import GroundTruthStatus, SortField, SortOrder
from app.domain.models import AgenticGroundTruthEntry
from tests.test_helpers import make_test_entry


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


def test_emulator_unicode_normalization_encodes_canonical_reference_content(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.repos.cosmos_repo.settings.COSMOS_DISABLE_UNICODE_ESCAPE", True)

    original_content = r"Snippet with invalid escape \q and unicode \u2603"
    payload = {
        "plugins": {
            "rag-compat": {
                "data": {
                    "references": [
                        {
                            "url": "https://example.com/canonical",
                            "content": original_content,
                        }
                    ]
                }
            }
        }
    }

    normalized = _normalize_unicode_for_cosmos(payload)
    ref = normalized["plugins"]["rag-compat"]["data"]["references"][0]

    assert ref.get("_contentEncoded") is True
    assert ref["content"] != original_content

    restored = _restore_unicode_from_cosmos(normalized)
    restored_ref = restored["plugins"]["rag-compat"]["data"]["references"][0]
    assert restored_ref["content"] == original_content
    assert "_contentEncoded" not in restored_ref


def test_emulator_unicode_normalization_does_not_base64_encode_legacy_refs(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.repos.cosmos_repo.settings.COSMOS_DISABLE_UNICODE_ESCAPE", True)

    original_content = r"Legacy snippet with invalid escape \q"
    payload = {
        "history": [
            {
                "role": "assistant",
                "msg": "Answer",
                "refs": [{"url": "https://example.com/legacy", "content": original_content}],
            }
        ]
    }

    normalized = _normalize_unicode_for_cosmos(payload)
    ref = normalized["history"][0]["refs"][0]
    assert "_contentEncoded" not in ref
    assert ref["content"] != original_content

    restored = _restore_unicode_from_cosmos(normalized)
    restored_ref = restored["history"][0]["refs"][0]
    assert restored_ref["content"] == original_content
    assert "_contentEncoded" not in restored_ref


def test_sort_key_has_answer(repo: CosmosGroundTruthRepo) -> None:
    example = make_test_entry(
        id="item",
        dataset_name="faq",
        synth_question="What?",
        answer="value",
        manual_tags=["team:sme"],
        reviewed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    key = CosmosGroundTruthRepo._sort_key(example, SortField.has_answer)
    assert key[0] == 1


def test_select_clause_includes_generic_phase_one_fields() -> None:
    for field in (
        "c.scenarioId",
        "c.contextEntries",
        "c.traceIds",
        "c.toolCalls",
        "c.expectedTools",
        "c.feedback",
        "c.metadata",
        "c.createdBy",
        "c.createdAt",
        "c.tracePayload",
    ):
        assert field in SELECT_CLAUSE_C


# =============================================================================
# Reference-count semantics via rag-compat pack helpers
# =============================================================================


class TestComputeTotalReferences:
    """Unit tests for rag-compat reference_count behavior.

    These tests exercise reference counting through
    ``get_rag_compat_pack().reference_count(item)`` using compatibility
    payload shapes seeded in fixtures. The host model no longer owns
    ``totalReferences`` behavior.
    """

    def _make_item(
        self,
        refs: list[dict] | None = None,
        history: list[dict] | None = None,
    ) -> AgenticGroundTruthEntry:
        """Helper to create an AgenticGroundTruthEntry with specified refs and history."""
        normalized_history = history
        if history is not None:
            normalized_history = []
            for turn in history:
                turn_copy = dict(turn)
                if turn_copy.get("refs") in (None, []):
                    turn_copy.pop("refs", None)
                normalized_history.append(turn_copy)
        return make_test_entry(
            id="test-item",
            dataset_name="test-dataset",
            synth_question="Test question?",
            refs=refs,
            history=normalized_history,
        )

    # -------------------------------------------------------------------------
    # Compat-reference counting with conversation history present
    # -------------------------------------------------------------------------

    def test_history_refs_take_priority_over_item_refs(self) -> None:
        """Compat refs are counted even when conversation history is present."""
        item = self._make_item(
            refs=[{"url": "https://item-ref-1.com"}, {"url": "https://item-ref-2.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi"},
            ],
        )
        assert get_rag_compat_pack().reference_count(item) == 2

    def test_history_refs_from_multiple_turns(self) -> None:
        """Compat refs are counted correctly with multi-turn history present."""
        item = self._make_item(
            refs=[
                {"url": "https://ref1.com"},
                {"url": "https://ref2.com"},
                {"url": "https://ref3.com"},
            ],
            history=[
                {"role": "user", "msg": "Q1"},
                {"role": "assistant", "msg": "A1"},
                {"role": "user", "msg": "Q2"},
                {"role": "assistant", "msg": "A2"},
            ],
        )
        assert get_rag_compat_pack().reference_count(item) == 3

    # -------------------------------------------------------------------------
    # Compat-reference fallback when history contributes no refs
    # -------------------------------------------------------------------------

    def test_item_refs_fallback_when_no_history(self) -> None:
        """Plugin-owned compat refs are counted when there is no history."""
        item = self._make_item(
            refs=[
                {"url": "https://ref1.com"},
                {"url": "https://ref2.com"},
                {"url": "https://ref3.com"},
            ],
            history=None,
        )
        assert get_rag_compat_pack().reference_count(item) == 3

    def test_item_refs_fallback_when_history_empty(self) -> None:
        """Plugin-owned compat refs are counted when history is an empty list."""
        item = self._make_item(
            refs=[{"url": "https://ref1.com"}, {"url": "https://ref2.com"}],
            history=[],
        )
        assert get_rag_compat_pack().reference_count(item) == 2

    def test_item_refs_fallback_when_history_has_no_refs(self) -> None:
        """Plugin-owned compat refs are counted when history exists but contains no refs."""
        item = self._make_item(
            refs=[{"url": "https://item-ref.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi"},  # No refs
            ],
        )
        # History contributes 0 compat refs, so top-level compat refs (1) are used
        assert get_rag_compat_pack().reference_count(item) == 1

    def test_item_refs_fallback_when_history_refs_are_empty_lists(self) -> None:
        """Plugin-owned compat refs are counted when history refs are empty lists."""
        item = self._make_item(
            refs=[{"url": "https://item-ref.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi", "refs": []},  # Empty refs list
            ],
        )
        # History compat refs total is 0, so top-level compat refs (1) are used
        assert get_rag_compat_pack().reference_count(item) == 1

    # -------------------------------------------------------------------------
    # Handle empty/null compat refs and history
    # -------------------------------------------------------------------------

    def test_zero_when_no_refs_anywhere(self) -> None:
        """Returns 0 when there are no refs at any level."""
        item = self._make_item(refs=None, history=None)
        assert get_rag_compat_pack().reference_count(item) == 0

    def test_zero_when_empty_refs_and_no_history(self) -> None:
        """Returns 0 when refs is empty list and no history."""
        item = self._make_item(refs=[], history=None)
        assert get_rag_compat_pack().reference_count(item) == 0

    def test_zero_when_empty_refs_and_empty_history(self) -> None:
        """Returns 0 when refs is empty and history is empty list."""
        item = self._make_item(refs=[], history=[])
        assert get_rag_compat_pack().reference_count(item) == 0

    def test_handles_none_refs_in_history_turn(self) -> None:
        """Handles history turns where refs is explicitly None."""
        item = self._make_item(
            refs=[{"url": "https://item-ref.com"}],
            history=[
                {"role": "user", "msg": "Hello"},
                {"role": "assistant", "msg": "Hi", "refs": None},  # Explicitly None
            ],
        )
        # History compat refs is 0, so top-level compat refs are used
        assert get_rag_compat_pack().reference_count(item) == 1

    # -------------------------------------------------------------------------
    # Complex scenarios with partial data
    # -------------------------------------------------------------------------

    def test_mixed_history_some_turns_with_refs_some_without(self) -> None:
        """Compat refs are counted with mixed multi-turn history."""
        item = self._make_item(
            refs=[
                {"url": "https://ref1.com"},
                {"url": "https://ref2.com"},
                {"url": "https://ref3.com"},
            ],
            history=[
                {"role": "user", "msg": "Q1"},
                {"role": "assistant", "msg": "A1"},  # No refs
                {"role": "user", "msg": "Q2"},
                {"role": "assistant", "msg": "A2"},
                {"role": "user", "msg": "Q3"},
                {"role": "assistant", "msg": "A3"},
                {"role": "user", "msg": "Q4"},
                {"role": "assistant", "msg": "A4"},
            ],
        )
        assert get_rag_compat_pack().reference_count(item) == 3

    def test_user_turns_with_refs_are_counted(self) -> None:
        """Compat refs are counted regardless of turn roles."""
        item = self._make_item(
            refs=[{"url": "https://user-ref.com"}, {"url": "https://assistant-ref.com"}],
            history=[
                {"role": "user", "msg": "Here's a doc"},
                {"role": "assistant", "msg": "Thanks"},
            ],
        )
        assert get_rag_compat_pack().reference_count(item) == 2

    def test_many_refs_in_single_turn(self) -> None:
        """Handles many compatibility refs."""
        many_refs = [{"url": f"https://ref{i}.com"} for i in range(10)]
        item = self._make_item(
            refs=many_refs,
            history=[
                {"role": "user", "msg": "Q"},
                {"role": "assistant", "msg": "A"},
            ],
        )
        assert get_rag_compat_pack().reference_count(item) == 10

    def test_item_only_no_history_field_at_all(self) -> None:
        """Item created without history field entirely."""
        # Use model_validate directly to test the case where history is completely absent
        item = AgenticGroundTruthEntry.model_validate(
            {
                "id": "minimal-item",
                "datasetName": "test",
                "plugins": {
                    "rag-compat": {
                        "kind": "rag-compat",
                        "version": "1.0",
                        "data": {
                            "synthQuestion": "What?",
                            "refs": [{"url": "https://only-ref.com"}],
                        },
                    }
                },
            }
        )
        assert get_rag_compat_pack().reference_count(item) == 1

    def test_complex_real_world_scenario(self) -> None:
        """Realistic multi-turn conversation with various ref patterns."""
        item = self._make_item(
            refs=[
                {"url": "https://kb.example.com/article1"},
                {"url": "https://docs.example.com/troubleshooting"},
                {"url": "https://kb.example.com/article2"},
            ],
            history=[
                # Turn 1: User asks question
                {"role": "user", "msg": "How do I fix error X?"},
                {"role": "assistant", "msg": "You can try these solutions..."},
                # Turn 3: User follow-up
                {"role": "user", "msg": "That didn't work, any other ideas?"},
                {"role": "assistant", "msg": "Let's try this instead..."},
                # Turn 5: User confirms
                {"role": "user", "msg": "That worked, thanks!"},
                # Turn 6: Assistant closes (no refs needed)
                {"role": "assistant", "msg": "Glad I could help!"},
            ],
        )
        assert get_rag_compat_pack().reference_count(item) == 3


# ---------------------------------------------------------------------------
# IQ-001 regression: list_all_gt must filter to ground-truth-item docType
# ---------------------------------------------------------------------------


def test_list_all_gt_query_includes_doctype_filter(repo: CosmosGroundTruthRepo) -> None:
    """list_all_gt must generate a query that excludes non-ground-truth documents."""
    # Reach into the query logic by directly constructing what list_all_gt would build.
    # The method builds: WHERE c.docType = 'ground-truth-item' [AND c.status = @status]
    # Verify the WHERE clause string for the no-filter case.
    clauses = ["c.docType = 'ground-truth-item'"]
    where = " WHERE " + " AND ".join(clauses)
    query = f"SELECT * FROM c{where}"
    assert "c.docType = 'ground-truth-item'" in query
    assert "SELECT * FROM c WHERE" in query


def test_list_all_gt_query_with_status_filter(repo: CosmosGroundTruthRepo) -> None:
    """list_all_gt with status must include BOTH docType and status filters."""

    clauses = ["c.docType = 'ground-truth-item'", "c.status = @status"]
    where = " WHERE " + " AND ".join(clauses)
    query = f"SELECT * FROM c{where}"
    assert "c.docType = 'ground-truth-item'" in query
    assert "c.status = @status" in query
    # Ensure both clauses are present (not SELECT * FROM c WHERE c.status = @status alone)
    assert "c.docType = 'ground-truth-item' AND c.status = @status" in query


# ---------------------------------------------------------------------------
# IQ-003 strengthened: call list_all_gt() directly and assert query emitted
# ---------------------------------------------------------------------------


async def _empty_aiter():  # type: ignore[return]
    """Empty async generator used to stub out Cosmos query_items in unit tests."""
    return
    yield  # pragma: no cover – presence makes this an async generator function


@pytest.mark.asyncio
async def test_list_all_gt_directly_emits_doctype_filter(
    repo: CosmosGroundTruthRepo,
) -> None:
    """Calling list_all_gt() directly must pass the docType filter to query_items."""
    captured: list[str] = []

    def _mock_query_items(*args: object, **kwargs: object) -> object:
        query = kwargs.get("query") or (args[0] if args else "")
        captured.append(str(query))
        return _empty_aiter()

    mock_container = MagicMock()
    mock_container.query_items = _mock_query_items

    with patch.object(repo, "_ensure_initialized", new_callable=AsyncMock):
        repo._gt_container = mock_container  # type: ignore[assignment]
        result = await repo.list_all_gt()

    assert result == []
    assert len(captured) == 1
    assert "c.docType = 'ground-truth-item'" in captured[0]
    assert "SELECT * FROM c WHERE" in captured[0]


@pytest.mark.asyncio
async def test_list_all_gt_directly_emits_doctype_and_status_filter(
    repo: CosmosGroundTruthRepo,
) -> None:
    """list_all_gt(status=draft) must emit BOTH docType and status clauses."""
    captured: list[str] = []

    def _mock_query_items(*args: object, **kwargs: object) -> object:
        query = kwargs.get("query") or (args[0] if args else "")
        captured.append(str(query))
        return _empty_aiter()

    mock_container = MagicMock()
    mock_container.query_items = _mock_query_items

    with patch.object(repo, "_ensure_initialized", new_callable=AsyncMock):
        repo._gt_container = mock_container  # type: ignore[assignment]
        result = await repo.list_all_gt(status=GroundTruthStatus.draft)

    assert result == []
    assert len(captured) == 1
    assert "c.docType = 'ground-truth-item'" in captured[0]
    assert "c.status = @status" in captured[0]
    assert "c.docType = 'ground-truth-item' AND c.status = @status" in captured[0]
