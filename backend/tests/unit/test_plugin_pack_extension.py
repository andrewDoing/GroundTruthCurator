"""Unit tests for expanded PluginPack extension surfaces.

Tests cover:
- get_stats_contribution no-op default and registry aggregation
- get_explorer_fields no-op default and registry aggregation with pack_name
- get_import_transforms and get_export_transforms aggregation
- collect_stats merges base_stats with pack contributions
"""

from __future__ import annotations

from typing import Any

from app.domain.models import AgenticGroundTruthEntry
from app.plugins.base import (
    ExplorerFieldDefinition,
    ExportTransform,
    ImportTransform,
    PluginPack,
    PluginPackRegistry,
)


# ---------------------------------------------------------------------------
# Test double packs
# ---------------------------------------------------------------------------


class StatsPack(PluginPack):
    @property
    def name(self) -> str:
        return "stats-pack"

    def get_stats_contribution(self, base_stats: dict[str, Any]) -> dict[str, Any]:
        return {
            "stats-pack:customCount": 42,
            "stats-pack:ratio": base_stats.get("total", 0) / 100,
        }


class ExplorerPack(PluginPack):
    @property
    def name(self) -> str:
        return "explorer-pack"

    def get_explorer_fields(self) -> list[ExplorerFieldDefinition]:
        return [
            ExplorerFieldDefinition(
                key="explorer-pack:score",
                label="Score",
                field_type="number",
                sortable=True,
                filterable=True,
            ),
            ExplorerFieldDefinition(
                key="explorer-pack:category",
                label="Category",
                field_type="string",
                filterable=True,
            ),
        ]


class TransformPack(PluginPack):
    @property
    def name(self) -> str:
        return "transform-pack"

    def get_import_transforms(self) -> list[ImportTransform]:
        return [
            ImportTransform(
                name="transform-pack:normalize",
                description="Normalize field casing",
            )
        ]

    def get_export_transforms(self) -> list[ExportTransform]:
        return [
            ExportTransform(
                name="transform-pack:flatten",
                description="Flatten nested fields",
            )
        ]


class NoOpExtensionPack(PluginPack):
    @property
    def name(self) -> str:
        return "no-op-ext"


# ---------------------------------------------------------------------------
# Default no-op behavior
# ---------------------------------------------------------------------------


def test_default_stats_contribution_is_empty():
    pack = NoOpExtensionPack()
    assert pack.get_stats_contribution({"total": 100}) == {}


def test_default_explorer_fields_is_empty():
    pack = NoOpExtensionPack()
    assert pack.get_explorer_fields() == []


def test_default_import_transforms_is_empty():
    pack = NoOpExtensionPack()
    assert pack.get_import_transforms() == []


def test_default_export_transforms_is_empty():
    pack = NoOpExtensionPack()
    assert pack.get_export_transforms() == []


# ---------------------------------------------------------------------------
# Stats aggregation
# ---------------------------------------------------------------------------


def test_collect_stats_returns_base_when_no_packs():
    registry = PluginPackRegistry()
    base = {"total": 100, "approved": 50}
    result = registry.collect_stats(base)
    assert result == base


def test_collect_stats_merges_pack_contributions():
    registry = PluginPackRegistry()
    registry.register(StatsPack())
    base = {"total": 100, "approved": 50}
    result = registry.collect_stats(base)
    assert result["total"] == 100
    assert result["approved"] == 50
    assert result["stats-pack:customCount"] == 42
    assert result["stats-pack:ratio"] == 1.0


def test_collect_stats_pack_key_overwrites_base_on_collision():
    registry = PluginPackRegistry()

    class OverwritePack(PluginPack):
        @property
        def name(self) -> str:
            return "overwrite"

        def get_stats_contribution(self, base_stats: dict[str, Any]) -> dict[str, Any]:
            return {"total": 999}

    registry.register(OverwritePack())
    result = registry.collect_stats({"total": 100})
    assert result["total"] == 999


# ---------------------------------------------------------------------------
# Explorer fields aggregation
# ---------------------------------------------------------------------------


def test_collect_explorer_fields_empty_registry():
    registry = PluginPackRegistry()
    assert registry.collect_explorer_fields() == []


def test_collect_explorer_fields_populates_pack_name():
    registry = PluginPackRegistry()
    registry.register(ExplorerPack())
    fields = registry.collect_explorer_fields()
    assert len(fields) == 2
    assert all(f.pack_name == "explorer-pack" for f in fields)
    assert fields[0].key == "explorer-pack:score"
    assert fields[1].key == "explorer-pack:category"


def test_collect_explorer_fields_from_multiple_packs():
    registry = PluginPackRegistry()
    registry.register(ExplorerPack())
    registry.register(NoOpExtensionPack())
    fields = registry.collect_explorer_fields()
    assert len(fields) == 2  # only ExplorerPack contributes


# ---------------------------------------------------------------------------
# Import/export transform aggregation
# ---------------------------------------------------------------------------


def test_collect_import_transforms_populates_pack_name():
    registry = PluginPackRegistry()
    registry.register(TransformPack())
    transforms = registry.collect_import_transforms()
    assert len(transforms) == 1
    assert transforms[0].pack_name == "transform-pack"
    assert transforms[0].name == "transform-pack:normalize"


def test_collect_export_transforms_populates_pack_name():
    registry = PluginPackRegistry()
    registry.register(TransformPack())
    transforms = registry.collect_export_transforms()
    assert len(transforms) == 1
    assert transforms[0].pack_name == "transform-pack"
    assert transforms[0].name == "transform-pack:flatten"


def test_collect_transforms_empty_when_no_contributing_packs():
    registry = PluginPackRegistry()
    registry.register(NoOpExtensionPack())
    assert registry.collect_import_transforms() == []
    assert registry.collect_export_transforms() == []
