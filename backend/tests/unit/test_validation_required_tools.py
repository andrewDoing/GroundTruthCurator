"""Unit tests for backend required-tool enforcement in approval validation.

These tests were deferred from Phase 4 (frontend-only approval strictness)
to Phase 5 where the backend side is implemented. They validate that
collect_approval_validation_errors() enforces ≥1 required tool when tool
calls are present, and that plugin-pack waivers can bypass this check.
"""

from __future__ import annotations

from app.domain.models import (
    AgenticGroundTruthEntry,
)
from app.plugins.base import PluginPackRegistry
from app.plugins.packs.rag_compat import RagCompatPack
from app.services.validation_service import collect_approval_validation_errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_TOOLS_ERROR = (
    "expectedTools.required must include at least one tool "
    "before approval when toolCalls are present"
)


def _make_item(**overrides) -> AgenticGroundTruthEntry:
    defaults = {
        "id": "req-tool-1",
        "datasetName": "demo",
        "history": [
            {"role": "user", "msg": "Find the answer."},
            {"role": "assistant", "msg": "I found it."},
        ],
    }
    defaults.update(overrides)
    return AgenticGroundTruthEntry.model_validate(defaults)


# ---------------------------------------------------------------------------
# Core required-tool enforcement
# ---------------------------------------------------------------------------


def test_required_tool_error_when_tool_calls_exist_but_no_required():
    item = _make_item(toolCalls=[{"name": "search"}])
    errors = collect_approval_validation_errors(item)
    assert REQUIRED_TOOLS_ERROR in errors


def test_no_required_tool_error_when_required_tools_defined():
    item = _make_item(
        toolCalls=[{"name": "search"}],
        expectedTools={"required": [{"name": "search"}]},
    )
    errors = collect_approval_validation_errors(item)
    assert REQUIRED_TOOLS_ERROR not in errors


def test_no_required_tool_error_when_no_tool_calls():
    item = _make_item()
    errors = collect_approval_validation_errors(item)
    assert REQUIRED_TOOLS_ERROR not in errors


def test_missing_required_tools_detected():
    item = _make_item(
        toolCalls=[{"name": "search"}],
        expectedTools={"required": [{"name": "browser"}]},
    )
    errors = collect_approval_validation_errors(item)
    assert any("browser" in e for e in errors)


def test_multiple_missing_required_tools_sorted():
    item = _make_item(
        toolCalls=[{"name": "search"}],
        expectedTools={"required": [{"name": "z-tool"}, {"name": "a-tool"}]},
    )
    errors = collect_approval_validation_errors(item)
    missing_error = [e for e in errors if "do not exist" in e]
    assert len(missing_error) == 1
    assert "a-tool, z-tool" in missing_error[0]


# ---------------------------------------------------------------------------
# Plugin-pack waiver for required-tools
# ---------------------------------------------------------------------------


def test_rag_pack_waives_required_tools_for_retrieval_items():
    """RagCompatPack waives the required-tools check for items with refs."""
    registry = PluginPackRegistry()
    registry.register(RagCompatPack())

    item = _make_item(
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
    assert REQUIRED_TOOLS_ERROR in core_errors

    filtered = registry.filter_core_errors(item, core_errors)
    assert REQUIRED_TOOLS_ERROR not in filtered


def test_rag_pack_does_not_waive_required_tools_without_refs():
    """Without refs, the required-tools error stands."""
    registry = PluginPackRegistry()
    registry.register(RagCompatPack())

    item = _make_item(
        toolCalls=[{"name": "search"}],
        plugins={
            "rag-compat": {
                "kind": "rag-compat",
                "version": "1.0",
                "data": {"references": []},
            }
        },
    )
    core_errors = collect_approval_validation_errors(item)
    filtered = registry.filter_core_errors(item, core_errors)
    assert REQUIRED_TOOLS_ERROR in filtered


def test_required_tools_pass_when_properly_classified():
    """Items with classified tools have no required-tools error at all."""
    item = _make_item(
        toolCalls=[{"name": "search"}, {"name": "browser"}],
        expectedTools={
            "required": [{"name": "search"}],
            "optional": [{"name": "browser"}],
        },
    )
    errors = collect_approval_validation_errors(item)
    assert not errors
