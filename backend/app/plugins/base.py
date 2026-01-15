"""Base classes for the computed tags plugin system.

This module defines the abstract base class for computed tag plugins
and the registry for managing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem


class ComputedTagPlugin(ABC):
    """Abstract base class for computed tag plugins.

    Each plugin implements logic to determine if a specific tag should be
    applied to a ground truth document based on its content.

    The compute() method returns the tag string if applicable, or None if not.
    This unified interface supports both static tags (fixed tag_key) and
    dynamic tags (computed based on document content).

    Example (static tag):
        class LongDocPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "length:long"

            def compute(self, doc: GroundTruthItem) -> str | None:
                content = doc.answer or ""
                return self.tag_key if len(content) > 10000 else None

    Example (dynamic tag):
        class DatasetPlugin(ComputedTagPlugin):
            @property
            def tag_key(self) -> str:
                return "dataset:_dynamic"

            def compute(self, doc: GroundTruthItem) -> str | None:
                return f"dataset:{doc.datasetName}" if doc.datasetName else None
    """

    @property
    @abstractmethod
    def tag_key(self) -> str:
        """The unique tag key for this computed tag (e.g., 'length:long').

        Must follow the group:value format.
        For dynamic plugins, use a placeholder like 'group:_dynamic'.
        """
        pass

    @abstractmethod
    def compute(self, doc: GroundTruthItem) -> str | None:
        """Compute the tag for this document.

        Args:
            doc: The GroundTruthItem to evaluate.
                 Contains fields like 'answer', 'synthQuestion', 'refs', 'history', etc.

        Returns:
            The tag string if applicable, None otherwise.
            For static plugins, return self.tag_key or None.
            For dynamic plugins, return the computed tag string or None.
        """
        pass


class TagPluginRegistry:
    """Registry for managing and executing computed tag plugins.

    The registry maintains a list of active plugins and provides methods to:
    - Register new plugins
    - Compute all applicable tags for a document
    - Get the set of all registered computed tag keys

    Example:
        registry = TagPluginRegistry()
        registry.register(LongDocPlugin())
        registry.register(MultiTurnPlugin())
        registry.register(DatasetPlugin())

        computed_tags = registry.compute_all(document)
        all_computed_keys = registry.get_all_keys()
    """

    def __init__(self) -> None:
        self._plugins: list[ComputedTagPlugin] = []
        self._registered_keys: set[str] = set()

    def register(self, plugin: ComputedTagPlugin) -> None:
        """Register a computed tag plugin.

        Args:
            plugin: The plugin instance to register.

        Raises:
            ValueError: If a plugin with the same tag_key is already registered.
        """
        if plugin.tag_key in self._registered_keys:
            raise ValueError(
                f"Duplicate tag key '{plugin.tag_key}': a plugin with this key is already registered"
            )
        self._registered_keys.add(plugin.tag_key)
        self._plugins.append(plugin)

    def compute_all(self, doc: GroundTruthItem) -> list[str]:
        """Compute all applicable tags for a document.

        Iterates through all registered plugins and collects tags
        from plugins whose compute() method returns a tag string.

        Args:
            doc: The GroundTruthItem to evaluate.

        Returns:
            A list of computed tag keys that apply to this document.
        """
        tags: list[str] = []
        for plugin in self._plugins:
            tag = plugin.compute(doc)
            if tag:
                tags.append(tag)
        return tags

    def get_all_keys(self) -> set[str]:
        """Get the set of all registered computed tag keys.

        Returns:
            A set of all tag keys that could be computed by registered plugins.
            Note: Dynamic plugin keys are placeholders (e.g., 'dataset:_dynamic').
        """
        return {p.tag_key for p in self._plugins}

    def get_static_keys(self) -> set[str]:
        """Get the set of static (non-dynamic) computed tag keys.

        Filters out dynamic plugin keys that use the ':_dynamic' placeholder.

        Returns:
            A set of tag keys excluding those ending with ':_dynamic'.
        """
        return {p.tag_key for p in self._plugins if not p.tag_key.endswith(":_dynamic")}

    def get_dynamic_prefixes(self) -> set[str]:
        """Get the prefixes for dynamic computed tag plugins.

        Dynamic plugins have tag_key ending with ':_dynamic'.
        This returns the prefix part (e.g., 'dataset:' from 'dataset:_dynamic').

        Returns:
            A set of prefixes that identify dynamic computed tags.
        """
        prefixes: set[str] = set()
        for plugin in self._plugins:
            if plugin.tag_key.endswith(":_dynamic"):
                # Extract prefix: "dataset:_dynamic" -> "dataset:"
                prefix = plugin.tag_key[: -len("_dynamic")]
                prefixes.add(prefix)
        return prefixes

    def is_computed_tag(self, tag: str, computed_tags: list[str] | None = None) -> bool:
        """Check if a tag is a computed tag (static or dynamic).

        A tag is considered computed if:
        1. It exactly matches a static computed tag key, OR
        2. It starts with a dynamic prefix (e.g., 'dataset:'), OR
        3. It's in the provided computed_tags list (current item's computed values)

        Args:
            tag: The tag to check.
            computed_tags: Optional list of currently computed tags for an item.

        Returns:
            True if the tag should be treated as a computed tag.
        """
        # Check static keys
        if tag in self.get_static_keys():
            return True

        # Check dynamic prefixes
        for prefix in self.get_dynamic_prefixes():
            if tag.startswith(prefix):
                return True

        # Check current computed values
        if computed_tags and tag in computed_tags:
            return True

        return False

    def filter_manual_tags(
        self, manual_tags: list[str] | None, computed_tags: list[str] | None = None
    ) -> list[str]:
        """Filter out computed tags from a list of manual tags.

        Uses pattern-based matching for dynamic tags to ensure ALL dynamic
        tag values are filtered (not just exact matches).

        Args:
            manual_tags: List of manual tags to filter.
            computed_tags: Optional list of currently computed tags for the item.

        Returns:
            Filtered list with computed tags removed.
        """
        if not manual_tags:
            return []

        return [t for t in manual_tags if not self.is_computed_tag(t, computed_tags)]

    def __len__(self) -> int:
        """Return the number of registered plugins."""
        return len(self._plugins)
