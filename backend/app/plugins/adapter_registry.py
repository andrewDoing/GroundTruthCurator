"""Default registry configuration for trace adapter plugins.

This module provides functions to create and manage the global
default trace adapter registry.  Plugins are automatically discovered
from modules in the ``adapters`` sub-package.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import threading
from pathlib import Path

from app.plugins.base import TraceAdapterPlugin, TraceAdapterRegistry


def _discover_adapters() -> list[type[TraceAdapterPlugin]]:
    """Discover all TraceAdapterPlugin subclasses in the adapters package.

    Scans all modules in the ``plugins/adapters/`` directory and finds
    concrete classes that inherit from TraceAdapterPlugin.

    Returns:
        A list of adapter plugin classes (not instances).
    """
    adapters: list[type[TraceAdapterPlugin]] = []
    package_dir = Path(__file__).parent / "adapters"

    if not package_dir.is_dir():
        return adapters

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name == "__init__":
            continue

        module = importlib.import_module(f"app.plugins.adapters.{module_info.name}")

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, TraceAdapterPlugin)
                and obj is not TraceAdapterPlugin
                and not inspect.isabstract(obj)
            ):
                adapters.append(obj)

    return adapters


def create_default_adapter_registry() -> TraceAdapterRegistry:
    """Create a TraceAdapterRegistry with all discovered adapter plugins.

    Returns:
        A registry pre-populated with all discovered adapters.
    """
    registry = TraceAdapterRegistry()
    for adapter_cls in _discover_adapters():
        registry.register(adapter_cls)
    return registry


# Global default registry instance
_default_adapter_registry: TraceAdapterRegistry | None = None
_adapter_registry_lock = threading.Lock()


def get_default_adapter_registry() -> TraceAdapterRegistry:
    """Get the global default trace adapter registry.

    Creates the registry on first access (lazy initialization).
    Thread-safe using double-checked locking pattern.

    Returns:
        The global TraceAdapterRegistry instance.
    """
    global _default_adapter_registry
    if _default_adapter_registry is None:
        with _adapter_registry_lock:
            if _default_adapter_registry is None:
                _default_adapter_registry = create_default_adapter_registry()
    assert _default_adapter_registry is not None
    return _default_adapter_registry


def reset_default_adapter_registry() -> None:
    """Reset the global default adapter registry.

    Primarily used for testing to ensure a clean state.
    """
    global _default_adapter_registry
    _default_adapter_registry = None
