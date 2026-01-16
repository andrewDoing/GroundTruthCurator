"""Default registry configuration for computed tag plugins.

This module provides functions to create and manage the global
default tag plugin registry. Plugins are automatically discovered
from modules in the computed_tags package.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import threading
from pathlib import Path

from app.plugins.base import ComputedTagPlugin, TagPluginRegistry


def _discover_plugins() -> list[type[ComputedTagPlugin]]:
    """Discover all ComputedTagPlugin subclasses in the computed_tags package.

    Scans all modules in the computed_tags package directory and finds
    concrete classes that inherit from ComputedTagPlugin.

    Returns:
        A list of plugin classes (not instances).
    """
    plugins: list[type[ComputedTagPlugin]] = []
    package_dir = Path(__file__).parent / "computed_tags"

    # Iterate through all Python modules in the package directory
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        # Skip __init__ module
        if module_info.name == "__init__":
            continue

        # Import the module
        module = importlib.import_module(f"app.plugins.computed_tags.{module_info.name}")

        # Find all classes in the module that are subclasses of ComputedTagPlugin
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, ComputedTagPlugin)
                and obj is not ComputedTagPlugin
                and not inspect.isabstract(obj)
            ):
                plugins.append(obj)

    return plugins


def create_default_registry() -> TagPluginRegistry:
    """Create a TagPluginRegistry with all discovered plugins.

    Automatically discovers and registers all ComputedTagPlugin subclasses
    found in the computed_tags package modules.

    Returns:
        A registry pre-populated with all discovered plugins.
    """
    registry = TagPluginRegistry()
    for plugin_cls in _discover_plugins():
        registry.register(plugin_cls())
    return registry


# Global default registry instance
_default_registry: TagPluginRegistry | None = None
_registry_lock = threading.Lock()


def get_default_registry() -> TagPluginRegistry:
    """Get the global default tag plugin registry.

    Creates the registry on first access (lazy initialization).
    Thread-safe using double-checked locking pattern.

    Returns:
        The global TagPluginRegistry instance.
    """
    global _default_registry
    if _default_registry is None:
        with _registry_lock:
            # Double-check after acquiring lock
            if _default_registry is None:
                _default_registry = create_default_registry()
    assert _default_registry is not None
    return _default_registry


def reset_default_registry() -> None:
    """Reset the global default registry.

    Primarily used for testing to ensure a clean state.
    """
    global _default_registry
    _default_registry = None
