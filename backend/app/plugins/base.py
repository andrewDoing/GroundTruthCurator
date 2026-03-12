"""Base classes for the plugin system.

This module defines:
- ComputedTagPlugin: abstract base for computed-tag plugins
- TagPluginRegistry: registry for computed-tag plugins
- PluginPack: abstract base for broader plugin packs (validators, explorer contributions)
- PluginPackRegistry: startup-validated registry for plugin packs
- ExplorerFieldDefinition / ImportTransform / ExportTransform: supporting types
  for the PluginPack extension surfaces added in Phase 1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app.domain.models import AgenticGroundTruthEntry, GroundTruthItem


# ---------------------------------------------------------------------------
# Supporting types for plugin-pack extension surfaces
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExplorerFieldDefinition:
    """Describes a plugin-contributed column or filter in the explorer view.

    Attributes:
        key: Stable identifier for the field (e.g. "rag-compat:refCount").
        label: Human-readable column header.
        field_type: One of "string", "number", "boolean", "date".
        sortable: Whether the explorer should allow sorting on this field.
        filterable: Whether the explorer should allow filtering on this field.
        pack_name: Owning plugin pack name (auto-populated by registry).
    """

    key: str
    label: str
    field_type: str = "string"
    sortable: bool = False
    filterable: bool = False
    pack_name: str = ""


@dataclass(frozen=True)
class ImportTransform:
    """A named transformation applied to a record during import.

    Attributes:
        name: Unique identifier for this transform (e.g. "rag-compat:legacy-refs").
        description: Human-readable explanation of what the transform does.
        transform: Callable that receives a raw dict and returns a transformed dict.
        pack_name: Owning plugin pack name (auto-populated by registry).
    """

    name: str
    description: str = ""
    transform: Callable[[dict[str, Any]], dict[str, Any]] = field(
        default_factory=lambda: (lambda d: d)
    )
    pack_name: str = ""


@dataclass(frozen=True)
class ExportTransform:
    """A named transformation applied to a record during export.

    Attributes:
        name: Unique identifier for this transform (e.g. "rag-compat:flatten-refs").
        description: Human-readable explanation of what the transform does.
        transform: Callable that receives a record dict and returns a transformed dict.
        pack_name: Owning plugin pack name (auto-populated by registry).
    """

    name: str
    description: str = ""
    transform: Callable[[dict[str, Any]], dict[str, Any]] = field(
        default_factory=lambda: (lambda d: d)
    )
    pack_name: str = ""


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


# ---------------------------------------------------------------------------
# Plugin-pack contract (broader than computed tags)
# ---------------------------------------------------------------------------


class PluginPack(ABC):
    """Abstract base class for plugin packs.

    A plugin pack is a named unit of domain behavior that can contribute:
    - Startup validation (via validate_registration)
    - Approval-time error hooks (via collect_approval_errors)

    The generic core hosts plugin packs without being aware of domain details.
    Computed-tag plugins continue to work unchanged through TagPluginRegistry.

    Example (minimal no-op pack)::

        class MyDomainPack(PluginPack):
            @property
            def name(self) -> str:
                return "my-domain"

            def validate_registration(self) -> None:
                # assert required config exists; raise ValueError on failure
                pass

    Example (approval-contributing pack)::

        class StrictRefPack(PluginPack):
            @property
            def name(self) -> str:
                return "strict-ref"

            def collect_approval_errors(
                self, item: AgenticGroundTruthEntry
            ) -> list[str]:
                errors: list[str] = []
                if not item.refs:
                    errors.append("strict-ref: at least one reference is required")
                return errors
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this plugin pack (e.g., 'rag-compat').

        Used for duplicate-registration detection and telemetry.
        Must be a non-empty string stable across restarts.
        """

    def validate_registration(self) -> None:
        """Validate this pack's own registration contract at startup.

        Called once during application startup by PluginPackRegistry.validate_all().
        Raise ValueError with an actionable message if the pack is misconfigured.
        The default implementation is a no-op.

        Raises:
            ValueError: If the pack is not correctly configured.
        """

    def collect_approval_errors(self, item: AgenticGroundTruthEntry) -> list[str]:
        """Return pack-specific approval validation errors for an item.

        Called after the generic core approval checks. Return an empty list
        when the item is acceptable from this pack's perspective.

        Args:
            item: The item being evaluated for approval.

        Returns:
            A list of human-readable error messages, or an empty list on success.
        """
        return []

    # ------------------------------------------------------------------
    # Extension surfaces (Phase 1 contract — default no-ops)
    # ------------------------------------------------------------------

    def get_stats_contribution(self, base_stats: dict[str, Any]) -> dict[str, Any]:
        """Return plugin-specific stats to merge into the stats response.

        Called by the stats endpoint to let each pack contribute domain-
        specific aggregations alongside the generic core counts.

        Args:
            base_stats: The core stats dict already computed by the host.

        Returns:
            A dict of additional stats entries.  Keys must be namespaced
            with the pack name (e.g. ``"rag-compat:refCount"``).
        """
        return {}

    def get_explorer_fields(self) -> list[ExplorerFieldDefinition]:
        """Return field definitions for plugin-contributed explorer columns/filters.

        The host merges these into its own explorer column set so that
        plugin-specific data can be browsed without hardcoding column
        definitions in the core explorer.

        Returns:
            A list of field definitions.
        """
        return []

    def get_import_transforms(self) -> list[ImportTransform]:
        """Return transforms applied during record import.

        Each transform receives the raw dict read from the import source
        and must return a (possibly mutated) dict.  Transforms execute in
        list order.

        Returns:
            A list of import transforms contributed by this pack.
        """
        return []

    def get_export_transforms(self) -> list[ExportTransform]:
        """Return transforms applied during record export.

        Each transform receives the normalised record dict and must return
        a (possibly mutated) dict suitable for the target export format.
        Transforms execute in list order.

        Returns:
            A list of export transforms contributed by this pack.
        """
        return []


class PluginPackRegistry:
    """Registry for plugin packs with startup validation.

    Maintains a named collection of PluginPack instances. Startup validation
    calls each pack's validate_registration() method so misconfigured packs
    fail fast with actionable errors rather than silently degrading behavior.

    Example::

        registry = PluginPackRegistry()
        registry.register(RagCompatPack())
        registry.validate_all()  # called once during app startup
    """

    def __init__(self) -> None:
        self._packs: dict[str, PluginPack] = {}

    def register(self, pack: PluginPack) -> None:
        """Register a plugin pack.

        Args:
            pack: The plugin pack instance to register.

        Raises:
            ValueError: If a pack with the same name is already registered,
                or if pack.name is empty.
        """
        pack_name = pack.name
        if not pack_name or not pack_name.strip():
            raise ValueError("Plugin pack name must be a non-empty string")
        if pack_name in self._packs:
            raise ValueError(
                f"Duplicate plugin pack name '{pack_name}': "
                "a pack with this name is already registered"
            )
        self._packs[pack_name] = pack

    def validate_all(self) -> None:
        """Run startup validation for all registered packs.

        Calls validate_registration() on every registered pack. If any pack
        raises, this method re-raises a ValueError with the pack name included
        so the startup error is actionable.

        Raises:
            ValueError: If any pack's validate_registration() fails.
        """
        for name, pack in self._packs.items():
            try:
                pack.validate_registration()
            except ValueError as exc:
                raise ValueError(
                    f"Plugin pack '{name}' failed startup validation: {exc}"
                ) from exc

    def collect_approval_errors(self, item: AgenticGroundTruthEntry) -> list[str]:
        """Gather approval errors from all registered packs.

        Args:
            item: The item being evaluated for approval.

        Returns:
            Combined list of approval error messages from all packs.
        """
        errors: list[str] = []
        for pack in self._packs.values():
            errors.extend(pack.collect_approval_errors(item))
        return errors

    def get(self, name: str) -> PluginPack | None:
        """Return the pack with the given name, or None if not registered."""
        return self._packs.get(name)

    def names(self) -> list[str]:
        """Return sorted list of registered pack names."""
        return sorted(self._packs.keys())

    # ------------------------------------------------------------------
    # Aggregation helpers for extension surfaces (Phase 1)
    # ------------------------------------------------------------------

    def collect_stats(self, base_stats: dict[str, Any]) -> dict[str, Any]:
        """Aggregate stats contributions from all registered packs.

        Args:
            base_stats: Core stats dict already computed by the host.

        Returns:
            A merged dict containing base stats plus pack contributions.
            Pack-contributed keys overwrite base keys on collision.
        """
        merged: dict[str, Any] = dict(base_stats)
        for pack in self._packs.values():
            merged.update(pack.get_stats_contribution(base_stats))
        return merged

    def collect_explorer_fields(self) -> list[ExplorerFieldDefinition]:
        """Collect explorer field definitions from all registered packs.

        Returns:
            Combined list of field definitions with ``pack_name`` populated.
        """
        fields: list[ExplorerFieldDefinition] = []
        for pack in self._packs.values():
            for f in pack.get_explorer_fields():
                populated = ExplorerFieldDefinition(
                    key=f.key,
                    label=f.label,
                    field_type=f.field_type,
                    sortable=f.sortable,
                    filterable=f.filterable,
                    pack_name=pack.name,
                )
                fields.append(populated)
        return fields

    def collect_import_transforms(self) -> list[ImportTransform]:
        """Collect import transforms from all registered packs (ordered by pack name).

        Returns:
            Combined list of import transforms with ``pack_name`` populated.
        """
        transforms: list[ImportTransform] = []
        for pack in self._packs.values():
            for t in pack.get_import_transforms():
                populated = ImportTransform(
                    name=t.name,
                    description=t.description,
                    transform=t.transform,
                    pack_name=pack.name,
                )
                transforms.append(populated)
        return transforms

    def collect_export_transforms(self) -> list[ExportTransform]:
        """Collect export transforms from all registered packs (ordered by pack name).

        Returns:
            Combined list of export transforms with ``pack_name`` populated.
        """
        transforms: list[ExportTransform] = []
        for pack in self._packs.values():
            for t in pack.get_export_transforms():
                populated = ExportTransform(
                    name=t.name,
                    description=t.description,
                    transform=t.transform,
                    pack_name=pack.name,
                )
                transforms.append(populated)
        return transforms

    def __len__(self) -> int:
        """Return the number of registered packs."""
        return len(self._packs)
