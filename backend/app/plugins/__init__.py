"""Plugins Package.

This package contains plugin systems for the Ground Truth Curator.

Subpackages:
    - computed_tags: Plugin implementations (auto-discovered)
"""

from app.plugins.base import ComputedTagPlugin, TagPluginRegistry
from app.plugins.registry import (
    create_default_registry,
    get_default_registry,
    reset_default_registry,
)

__all__ = [
    # Base classes
    "ComputedTagPlugin",
    "TagPluginRegistry",
    # Registry functions
    "create_default_registry",
    "get_default_registry",
    "reset_default_registry",
]
