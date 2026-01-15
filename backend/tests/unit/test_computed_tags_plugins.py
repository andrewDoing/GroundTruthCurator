"""Unit tests for the computed tags plugin system (registry and discovery)."""

from __future__ import annotations

import pytest

from app.domain.models import GroundTruthItem
from app.plugins.base import ComputedTagPlugin, TagPluginRegistry
from app.plugins.registry import (
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def reset_registry_state():
    """Reset the global registry before and after each test."""
    reset_default_registry()
    yield
    reset_default_registry()


class TestTagPluginRegistry:
    """Tests for the TagPluginRegistry class."""

    def test_empty_registry_returns_empty_tags(self):
        """An empty registry should return no tags."""
        registry = TagPluginRegistry()
        item = GroundTruthItem(id="test", datasetName="test", synthQuestion="Q")
        assert registry.compute_all(item) == []
        assert registry.get_all_keys() == set()

    def test_duplicate_tag_key_raises_error(self):
        """Registering a plugin with duplicate tag_key should raise ValueError."""

        class Plugin1(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dup:key"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return self.tag_key

        class Plugin2(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dup:key"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return self.tag_key

        registry = TagPluginRegistry()
        registry.register(Plugin1())

        with pytest.raises(ValueError, match="Duplicate tag key 'dup:key'"):
            registry.register(Plugin2())

    def test_default_registry_is_singleton(self):
        """get_default_registry should return same instance on repeated calls."""
        reg1 = get_default_registry()
        reg2 = get_default_registry()
        assert reg1 is reg2

    def test_reset_clears_singleton(self):
        """reset_default_registry should clear the singleton."""
        reg1 = get_default_registry()
        reset_default_registry()
        reg2 = get_default_registry()
        assert reg1 is not reg2


class TestDynamicTagPrefixes:
    """Tests for dynamic tag prefix detection and filtering."""

    def test_get_dynamic_prefixes_with_dynamic_plugin(self):
        """Registry should extract prefixes from dynamic plugins."""

        class DynamicPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dataset:_dynamic"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return f"dataset:{doc.datasetName}" if doc.datasetName else None

        registry = TagPluginRegistry()
        registry.register(DynamicPlugin())

        assert registry.get_dynamic_prefixes() == {"dataset:"}

    def test_get_dynamic_prefixes_excludes_static_plugins(self):
        """Static plugins should not contribute to dynamic prefixes."""

        class StaticPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "turns:multiturn"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return self.tag_key

        class DynamicPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dataset:_dynamic"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return f"dataset:{doc.datasetName}" if doc.datasetName else None

        registry = TagPluginRegistry()
        registry.register(StaticPlugin())
        registry.register(DynamicPlugin())

        assert registry.get_dynamic_prefixes() == {"dataset:"}
        assert registry.get_static_keys() == {"turns:multiturn"}

    def test_is_computed_tag_static_match(self):
        """is_computed_tag should return True for static tag keys."""

        class StaticPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "turns:multiturn"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return self.tag_key

        registry = TagPluginRegistry()
        registry.register(StaticPlugin())

        assert registry.is_computed_tag("turns:multiturn") is True
        assert registry.is_computed_tag("turns:singleturn") is False

    def test_is_computed_tag_dynamic_prefix_match(self):
        """is_computed_tag should match any tag with a dynamic prefix."""

        class DynamicPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dataset:_dynamic"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return f"dataset:{doc.datasetName}" if doc.datasetName else None

        registry = TagPluginRegistry()
        registry.register(DynamicPlugin())

        # Any dataset:* tag should be recognized as computed
        assert registry.is_computed_tag("dataset:oldDataset") is True
        assert registry.is_computed_tag("dataset:newDataset") is True
        assert registry.is_computed_tag("dataset:anything") is True
        # But other prefixes should not match
        assert registry.is_computed_tag("source:manual") is False

    def test_filter_manual_tags_removes_static_computed_tags(self):
        """filter_manual_tags should remove static computed tag keys."""

        class StaticPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "turns:multiturn"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return self.tag_key

        registry = TagPluginRegistry()
        registry.register(StaticPlugin())

        manual_tags = ["source:manual", "turns:multiturn", "priority:high"]
        filtered = registry.filter_manual_tags(manual_tags)

        assert filtered == ["source:manual", "priority:high"]

    def test_filter_manual_tags_removes_all_dynamic_values(self):
        """filter_manual_tags should remove ANY tag matching a dynamic prefix.

        This is the key bug fix - dataset:oldDataset should be stripped even
        when the current computed value is dataset:newDataset.
        """

        class DynamicPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dataset:_dynamic"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return f"dataset:{doc.datasetName}" if doc.datasetName else None

        registry = TagPluginRegistry()
        registry.register(DynamicPlugin())

        # Scenario: User manually added dataset:oldDataset, but item is now in newDataset
        manual_tags = ["source:manual", "dataset:oldDataset", "priority:high"]
        computed_tags = ["dataset:newDataset"]

        filtered = registry.filter_manual_tags(manual_tags, computed_tags)

        # dataset:oldDataset should be removed because dataset: is a dynamic prefix
        assert filtered == ["source:manual", "priority:high"]


class TestGroundTruthItemTagMerge:
    """Tests for computed and manual tag merging."""

    def test_computed_and_manual_tags_merge(self):
        """Verify computed and manual tags merge correctly and are sorted."""
        item = GroundTruthItem(
            id="merge-test",
            datasetName="test-dataset",
            synthQuestion="Test question",
            manualTags=["source:manual", "priority:high"],
            computedTags=["turns:singleturn"],
        )

        assert "source:manual" in item.tags
        assert "priority:high" in item.tags
        assert "turns:singleturn" in item.tags
        assert item.tags == sorted(item.tags)
