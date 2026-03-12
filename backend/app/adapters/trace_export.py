"""Backward-compatibility shim — the canonical location is now
``app.plugins.adapters.trace_export``.
"""

from app.plugins.adapters.trace_export import TraceExportAdapter

__all__ = ["TraceExportAdapter"]
