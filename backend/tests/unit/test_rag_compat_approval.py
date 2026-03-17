"""Unit tests for RAG approval waiver migration.

Validates that the RAG-specific assistant-message and required-tools waivers
are owned by RagCompatPack.collect_approval_waivers() rather than being
hard-coded in the core validation_service.
"""

from __future__ import annotations


from app.domain.models import (
    AgenticGroundTruthEntry,
)
from app.plugins.packs.rag_compat import RagCompatPack
from app.services.validation_service import collect_approval_validation_errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(**overrides) -> AgenticGroundTruthEntry:
    defaults = {
        "id": "rag-test-1",
        "datasetName": "demo",
        "history": [{"role": "user", "msg": "What is X?"}],
    }
    defaults.update(overrides)
    return AgenticGroundTruthEntry.model_validate(defaults)


# ---------------------------------------------------------------------------
# Core validation (no plugin intervention) — strict after waiver removal
# ---------------------------------------------------------------------------


def test_core_requires_assistant_message_even_with_refs():
    """After waiver removal, core always generates the assistant error."""
    item = _make_item(
        history=[{"role": "user", "msg": "hello"}],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": [{"url": "https://example.com/ref"}]},
            }
        },
    )
    errors = collect_approval_validation_errors(item)
    assert "history must include at least one assistant message" in errors


def test_core_no_error_when_assistant_present():
    item = _make_item(
        history=[
            {"role": "user", "msg": "hello"},
            {"role": "assistant", "msg": "world"},
        ],
    )
    errors = collect_approval_validation_errors(item)
    assert errors == []


# ---------------------------------------------------------------------------
# RagCompatPack waiver — assistant-message
# ---------------------------------------------------------------------------


def test_rag_pack_waives_assistant_error_when_refs_present():
    pack = RagCompatPack()
    item = _make_item(
        history=[{"role": "user", "msg": "hello"}],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": [{"url": "https://example.com/ref"}]},
            }
        },
    )
    core_errors = collect_approval_validation_errors(item)
    waivers = pack.collect_approval_waivers(item, core_errors)
    assert "history must include at least one assistant message" in waivers


def test_rag_pack_no_waiver_when_refs_zero():
    pack = RagCompatPack()
    item = _make_item(
        history=[{"role": "user", "msg": "hello"}],
        plugins={
            "rag-compat": {"kind": "rag-compat", "version": "1.0", "data": {"references": []}}
        },
    )
    core_errors = collect_approval_validation_errors(item)
    waivers = pack.collect_approval_waivers(item, core_errors)
    assert waivers == []


def test_rag_pack_does_not_waive_user_message_error():
    """The pack should only waive assistant-message and required-tools errors."""
    pack = RagCompatPack()
    item = _make_item(
        history=[{"role": "assistant", "msg": "answer"}],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": [{"url": "https://example.com/ref"}]},
            }
        },
    )
    core_errors = collect_approval_validation_errors(item)
    waivers = pack.collect_approval_waivers(item, core_errors)
    # "history must include at least one user message" should NOT be waived
    assert "history must include at least one user message" not in waivers


# ---------------------------------------------------------------------------
# RagCompatPack waiver — required-tools
# ---------------------------------------------------------------------------


def test_rag_pack_waives_required_tools_error_when_refs_present():
    pack = RagCompatPack()
    item = _make_item(
        history=[
            {"role": "user", "msg": "hello"},
            {"role": "assistant", "msg": "world"},
        ],
        toolCalls=[{"name": "search"}],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": [{"url": "https://example.com/ref"}]},
            }
        },
    )
    core_errors = collect_approval_validation_errors(item)
    waivers = pack.collect_approval_waivers(item, core_errors)
    assert any("expectedTools.required" in w for w in waivers)


def test_rag_pack_no_required_tools_waiver_when_refs_zero():
    pack = RagCompatPack()
    item = _make_item(
        history=[
            {"role": "user", "msg": "hello"},
            {"role": "assistant", "msg": "world"},
        ],
        toolCalls=[{"name": "search"}],
        plugins={
            "rag-compat": {"kind": "rag-compat", "version": "1.0", "data": {"references": []}}
        },
    )
    core_errors = collect_approval_validation_errors(item)
    waivers = pack.collect_approval_waivers(item, core_errors)
    assert waivers == []


# ---------------------------------------------------------------------------
# Registry-level waiver filtering (integration with PluginPackRegistry)
# ---------------------------------------------------------------------------


def test_registry_filters_waived_errors():
    from app.plugins.base import PluginPackRegistry

    registry = PluginPackRegistry()
    registry.register(RagCompatPack())
    registry.validate_all()

    item = _make_item(
        history=[{"role": "user", "msg": "hello"}],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": [{"url": "https://example.com/ref"}]},
            }
        },
    )
    core_errors = collect_approval_validation_errors(item)
    assert "history must include at least one assistant message" in core_errors

    filtered = registry.filter_core_errors(item, core_errors)
    assert "history must include at least one assistant message" not in filtered


def test_registry_preserves_non_waived_errors():
    from app.plugins.base import PluginPackRegistry

    registry = PluginPackRegistry()
    registry.register(RagCompatPack())

    # Item with no history, no question, no answer → "no conversation message" error
    item = _make_item(
        history=[],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": [{"url": "https://example.com/ref"}]},
            }
        },
    )
    core_errors = collect_approval_validation_errors(item)
    filtered = registry.filter_core_errors(item, core_errors)
    # "history must contain at least one conversation message" is NOT waived
    assert any("at least one conversation message" in e for e in filtered)
