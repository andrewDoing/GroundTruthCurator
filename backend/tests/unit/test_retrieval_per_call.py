"""Tests for RagCompatPack per-tool-call retrieval state (Phase 6)."""

from __future__ import annotations


from app.domain.models import AgenticGroundTruthEntry
from app.plugins.packs.rag_compat import RagCompatPack


def _make_item(**overrides) -> AgenticGroundTruthEntry:
    """Create a minimal item with default fields."""
    base = {
        "id": "test-item",
        "datasetName": "ds",
        "history": [
            {"role": "user", "msg": "hi"},
            {"role": "assistant", "msg": "hello"},
        ],
    }
    base.update(overrides)
    return AgenticGroundTruthEntry.model_validate(base)


def _make_item_with_refs(**overrides) -> AgenticGroundTruthEntry:
    """Create an item with top-level refs (legacy pattern)."""
    return _make_item(
        refs=[
            {"url": "https://a.com", "title": "A", "content": "chunk-a"},
            {"url": "https://b.com", "title": "B", "content": "chunk-b"},
        ],
        **overrides,
    )


def _make_item_with_tool_calls(**overrides) -> AgenticGroundTruthEntry:
    """Create an item with tool calls and top-level refs."""
    return _make_item(
        refs=[
            {"url": "https://a.com", "title": "A", "content": "chunk-a", "messageIndex": 1},
            {"url": "https://b.com", "title": "B", "content": "chunk-b"},
        ],
        toolCalls=[
            {"id": "tc-1", "name": "search", "callType": "tool", "stepNumber": 1},
            {"id": "tc-2", "name": "lookup", "callType": "tool", "stepNumber": 2},
        ],
        **overrides,
    )


class TestPerCallRetrievalState:
    """Per-tool-call retrieval management on RagCompatPack."""

    def test_get_retrievals_empty_item(self):
        pack = RagCompatPack()
        item = _make_item()
        assert pack.get_retrievals(item) == {}

    def test_set_and_get_retrieval_candidates(self):
        pack = RagCompatPack()
        item = _make_item()
        candidates = [
            {"url": "https://a.com", "title": "A", "chunk": "text-a"},
        ]
        pack.set_retrieval_candidates(item, "tc-1", candidates)
        assert pack.get_retrieval_candidates(item, "tc-1") == candidates

    def test_get_retrieval_candidates_missing_tool_call(self):
        pack = RagCompatPack()
        item = _make_item()
        assert pack.get_retrieval_candidates(item, "nonexistent") == []

    def test_set_retrievals_replaces_all(self):
        pack = RagCompatPack()
        item = _make_item()
        pack.set_retrieval_candidates(item, "tc-1", [{"url": "https://a.com"}])
        pack.set_retrievals(
            item,
            {
                "tc-2": {"candidates": [{"url": "https://b.com"}]},
            },
        )
        assert pack.get_retrieval_candidates(item, "tc-1") == []
        assert len(pack.get_retrieval_candidates(item, "tc-2")) == 1

    def test_has_per_call_state_false_when_empty(self):
        pack = RagCompatPack()
        item = _make_item()
        assert pack.has_per_call_state(item) is False

    def test_has_per_call_state_true_after_set(self):
        pack = RagCompatPack()
        item = _make_item()
        pack.set_retrieval_candidates(item, "tc-1", [{"url": "https://a.com"}])
        assert pack.has_per_call_state(item) is True

    def test_get_all_candidates_flat_from_per_call(self):
        pack = RagCompatPack()
        item = _make_item()
        pack.set_retrieval_candidates(
            item,
            "tc-1",
            [
                {"url": "https://a.com", "title": "A"},
            ],
        )
        pack.set_retrieval_candidates(
            item,
            "tc-2",
            [
                {"url": "https://b.com", "title": "B"},
            ],
        )
        flat = pack.get_all_candidates_flat(item)
        assert len(flat) == 2
        urls = {c["url"] for c in flat}
        assert urls == {"https://a.com", "https://b.com"}

    def test_get_all_candidates_flat_falls_back_to_top_level_refs(self):
        pack = RagCompatPack()
        item = _make_item_with_refs()
        flat = pack.get_all_candidates_flat(item)
        assert len(flat) == 2
        assert flat[0]["url"] == "https://a.com"
        assert flat[0]["chunk"] == "chunk-a"

    def test_get_all_candidates_flat_includes_tool_call_id(self):
        pack = RagCompatPack()
        item = _make_item()
        pack.set_retrieval_candidates(
            item,
            "tc-1",
            [
                {"url": "https://a.com"},
            ],
        )
        flat = pack.get_all_candidates_flat(item)
        assert flat[0]["toolCallId"] == "tc-1"


class TestMigrateRefsToPerCall:
    """Tests for migrate_refs_to_per_call helper."""

    def test_migrate_no_refs_returns_false(self):
        pack = RagCompatPack()
        item = _make_item()
        assert pack.migrate_refs_to_per_call(item) is False

    def test_migrate_already_migrated_returns_false(self):
        pack = RagCompatPack()
        item = _make_item()
        pack.set_retrieval_candidates(item, "tc-1", [{"url": "https://a.com"}])
        # Even with refs present, per-call state exists → skip migration
        assert pack.migrate_refs_to_per_call(item) is False

    def test_migrate_top_level_refs_to_unassociated(self):
        pack = RagCompatPack()
        item = _make_item_with_refs()
        assert pack.migrate_refs_to_per_call(item) is True
        # All refs go to _unassociated since no tool calls
        cands = pack.get_retrieval_candidates(item, "_unassociated")
        assert len(cands) == 2
        assert cands[0]["url"] == "https://a.com"

    def test_migrate_refs_matched_to_tool_calls_by_step(self):
        pack = RagCompatPack()
        item = _make_item_with_tool_calls()
        assert pack.migrate_refs_to_per_call(item) is True

        # Ref with messageIndex=1 matches tc-1 (stepNumber=1)
        tc1_cands = pack.get_retrieval_candidates(item, "tc-1")
        assert len(tc1_cands) == 1
        assert tc1_cands[0]["url"] == "https://a.com"

        # Ref without messageIndex goes to _unassociated
        unassociated = pack.get_retrieval_candidates(item, "_unassociated")
        assert len(unassociated) == 1
        assert unassociated[0]["url"] == "https://b.com"

    def test_migrate_idempotent(self):
        pack = RagCompatPack()
        item = _make_item_with_refs()
        assert pack.migrate_refs_to_per_call(item) is True
        assert pack.migrate_refs_to_per_call(item) is False
