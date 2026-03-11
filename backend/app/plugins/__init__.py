"""Plugins Package.

This package contains plugin systems for the Ground Truth Curator.

Subpackages:
    - computed_tags: Computed-tag plugin implementations (auto-discovered).
    - packs: Plugin-pack implementations (startup-validated, approval-contributing).
"""

from app.plugins.base import ComputedTagPlugin, PluginPack, PluginPackRegistry, TagPluginRegistry
from app.plugins.registry import (
    create_default_registry,
    get_default_registry,
    reset_default_registry,
)
from app.plugins.pack_registry import (
    create_default_pack_registry,
    get_default_pack_registry,
    reset_default_pack_registry,
)

__all__ = [
    # Base classes — computed-tag plugin
    "ComputedTagPlugin",
    "TagPluginRegistry",
    # Base classes — plugin pack
    "PluginPack",
    "PluginPackRegistry",
    # Tag plugin registry functions
    "create_default_registry",
    "get_default_registry",
    "reset_default_registry",
    # Plugin-pack registry functions
    "create_default_pack_registry",
    "get_default_pack_registry",
    "reset_default_pack_registry",
]
