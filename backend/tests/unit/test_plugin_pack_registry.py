"""Unit tests for PluginPack ABC and PluginPackRegistry.

Tests cover:
- Successful pack registration
- Duplicate-name rejection
- Empty-name rejection
- validate_all() calls each pack's validate_registration()
- validate_all() wraps errors with pack name context
- collect_approval_errors() aggregates across all packs
- get() and names() accessors
"""

from __future__ import annotations

import pytest

from app.domain.models import AgenticGroundTruthEntry
from app.plugins.base import PluginPack, PluginPackRegistry


# ---------------------------------------------------------------------------
# Test double packs
# ---------------------------------------------------------------------------


class NoOpPack(PluginPack):
    @property
    def name(self) -> str:
        return "no-op"


class AlwaysErrorPack(PluginPack):
    """A pack whose validate_registration always fails."""

    @property
    def name(self) -> str:
        return "always-error"

    def validate_registration(self) -> None:
        raise ValueError("intentional startup failure for testing")


class ApprovalErrorPack(PluginPack):
    """A pack that always appends an approval error."""

    @property
    def name(self) -> str:
        return "approval-error"

    def collect_approval_errors(self, item: AgenticGroundTruthEntry) -> list[str]:
        return [f"approval-error-pack: item {item.id} failed"]


class ConditionalApprovalPack(PluginPack):
    """A pack that errors on items with a specific dataset name."""

    @property
    def name(self) -> str:
        return "conditional"

    def collect_approval_errors(self, item: AgenticGroundTruthEntry) -> list[str]:
        if item.datasetName == "forbidden":
            return ["conditional: forbidden dataset cannot be approved"]
        return []


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


def test_register_single_pack_succeeds():
    registry = PluginPackRegistry()
    registry.register(NoOpPack())
    assert len(registry) == 1


def test_register_multiple_packs_succeeds():
    registry = PluginPackRegistry()
    registry.register(NoOpPack())
    registry.register(ApprovalErrorPack())
    assert len(registry) == 2


def test_register_duplicate_name_raises():
    registry = PluginPackRegistry()
    registry.register(NoOpPack())
    with pytest.raises(ValueError, match="Duplicate plugin pack name 'no-op'"):
        registry.register(NoOpPack())


def test_register_empty_name_raises():
    class EmptyNamePack(PluginPack):
        @property
        def name(self) -> str:
            return ""

    registry = PluginPackRegistry()
    with pytest.raises(ValueError, match="non-empty string"):
        registry.register(EmptyNamePack())


def test_register_whitespace_name_raises():
    class WhitespacePack(PluginPack):
        @property
        def name(self) -> str:
            return "   "

    registry = PluginPackRegistry()
    with pytest.raises(ValueError, match="non-empty string"):
        registry.register(WhitespacePack())


# ---------------------------------------------------------------------------
# validate_all tests
# ---------------------------------------------------------------------------


def test_validate_all_passes_for_valid_packs():
    registry = PluginPackRegistry()
    registry.register(NoOpPack())
    registry.validate_all()  # should not raise


def test_validate_all_fails_with_pack_name_in_message():
    registry = PluginPackRegistry()
    registry.register(AlwaysErrorPack())
    with pytest.raises(ValueError, match="Plugin pack 'always-error' failed startup validation"):
        registry.validate_all()


def test_validate_all_includes_original_error_message():
    registry = PluginPackRegistry()
    registry.register(AlwaysErrorPack())
    with pytest.raises(ValueError, match="intentional startup failure for testing"):
        registry.validate_all()


def test_validate_all_empty_registry_passes():
    registry = PluginPackRegistry()
    registry.validate_all()  # no packs — should not raise


# ---------------------------------------------------------------------------
# collect_approval_errors tests
# ---------------------------------------------------------------------------


def _make_item(item_id: str = "t-001", dataset: str = "demo") -> AgenticGroundTruthEntry:
    return AgenticGroundTruthEntry(
        id=item_id,
        datasetName=dataset,
        history=[
            {"role": "user", "msg": "hello"},
            {"role": "assistant", "msg": "world"},
        ],
    )


def test_collect_approval_errors_empty_registry():
    registry = PluginPackRegistry()
    item = _make_item()
    assert registry.collect_approval_errors(item) == []


def test_collect_approval_errors_no_op_pack_returns_empty():
    registry = PluginPackRegistry()
    registry.register(NoOpPack())
    item = _make_item()
    assert registry.collect_approval_errors(item) == []


def test_collect_approval_errors_error_pack_returns_errors():
    registry = PluginPackRegistry()
    registry.register(ApprovalErrorPack())
    item = _make_item(item_id="x-1")
    errors = registry.collect_approval_errors(item)
    assert len(errors) == 1
    assert "x-1" in errors[0]


def test_collect_approval_errors_aggregates_across_packs():
    registry = PluginPackRegistry()
    registry.register(ApprovalErrorPack())
    registry.register(ConditionalApprovalPack())

    # Item where ConditionalApprovalPack also fires
    item = _make_item(dataset="forbidden")
    errors = registry.collect_approval_errors(item)
    assert len(errors) == 2  # one from each pack


def test_collect_approval_errors_conditional_pack_silent_for_allowed_dataset():
    registry = PluginPackRegistry()
    registry.register(ConditionalApprovalPack())
    item = _make_item(dataset="allowed")
    assert registry.collect_approval_errors(item) == []


# ---------------------------------------------------------------------------
# Accessor tests
# ---------------------------------------------------------------------------


def test_get_registered_pack_by_name():
    registry = PluginPackRegistry()
    pack = NoOpPack()
    registry.register(pack)
    assert registry.get("no-op") is pack


def test_get_unregistered_pack_returns_none():
    registry = PluginPackRegistry()
    assert registry.get("missing") is None


def test_names_returns_sorted_list():
    registry = PluginPackRegistry()
    registry.register(ConditionalApprovalPack())
    registry.register(ApprovalErrorPack())
    registry.register(NoOpPack())
    assert registry.names() == ["approval-error", "conditional", "no-op"]
