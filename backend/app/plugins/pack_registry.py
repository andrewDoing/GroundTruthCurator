"""Global default plugin-pack registry.

Provides a lazy-initialized singleton PluginPackRegistry that holds all
built-in plugin packs.  The registry is validated at startup by the Container;
if any pack's validate_registration() raises, the app will not start.

Usage::

    from app.plugins.pack_registry import get_default_pack_registry

    # During startup:
    get_default_pack_registry().validate_all()

    # During approval:
    errors = get_default_pack_registry().collect_approval_errors(item)
"""

from __future__ import annotations

import logging
import threading

from app.plugins.base import PluginPackRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singleton — thread-safe double-checked locking pattern
# (mirrors registry.py which owns the TagPluginRegistry singleton)
# ---------------------------------------------------------------------------

_default_pack_registry: PluginPackRegistry | None = None
_pack_registry_lock = threading.Lock()


def create_default_pack_registry() -> PluginPackRegistry:
    """Create a PluginPackRegistry pre-populated with all built-in packs.

    Returns:
        A registry containing the RagCompatPack.
    """
    from app.plugins.packs.rag_compat import RagCompatPack

    registry = PluginPackRegistry()
    registry.register(RagCompatPack())
    logger.debug(
        "plugin_pack_registry.created | packs=%s", registry.names()
    )
    return registry


def get_default_pack_registry() -> PluginPackRegistry:
    """Return the global default plugin-pack registry.

    Creates the registry on first access (lazy initialization).
    Thread-safe using double-checked locking.

    Returns:
        The global PluginPackRegistry instance.
    """
    global _default_pack_registry
    if _default_pack_registry is None:
        with _pack_registry_lock:
            if _default_pack_registry is None:
                _default_pack_registry = create_default_pack_registry()
    assert _default_pack_registry is not None
    return _default_pack_registry


def reset_default_pack_registry() -> None:
    """Reset the global default pack registry.

    Primarily used in tests to ensure a clean state between test cases.
    """
    global _default_pack_registry
    _default_pack_registry = None


def get_required_pack(name: str, registry: PluginPackRegistry | None = None):
    active_registry = registry or get_default_pack_registry()
    pack = active_registry.get(name)
    if pack is None:
        raise LookupError(f"Required plugin pack '{name}' is not registered")
    return pack


def get_rag_compat_pack(registry: PluginPackRegistry | None = None):
    from app.plugins.packs.rag_compat import RagCompatPack

    pack = get_required_pack("rag-compat", registry)
    if not isinstance(pack, RagCompatPack):
        raise TypeError("Registered 'rag-compat' pack is not a RagCompatPack instance")
    return pack
