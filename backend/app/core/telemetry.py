from __future__ import annotations

import logging
from importlib import metadata

from fastapi import FastAPI

from .config import Settings
from .logging import attach_trace_log_filter

log = logging.getLogger(__name__)


def _get_package_version(default: str = "0.0.0") -> str:
    try:
        return metadata.version("backend")
    except Exception:  # pragma: no cover - best-effort
        return default


def _build_resource(settings: Settings):
    """Build an OpenTelemetry Resource from settings.

    Deferred import keeps module import safe when OTel isn't installed.
    """
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.semconv.resource import ResourceAttributes
    except Exception as e:  # pragma: no cover - optional dep
        log.debug("OpenTelemetry SDK not available for Resource: %s", e)
        return None

    attrs = {
        ResourceAttributes.SERVICE_NAME: settings.SERVICE_NAME,
        ResourceAttributes.SERVICE_VERSION: _get_package_version("0.1.0"),
    }
    return Resource.create(attrs)


def enable_log_correlation() -> None:
    """Enable OTel logging integration so records carry trace context."""
    try:
        # opentelemetry-instrumentation-logging provides logging auto-correlation
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception as e:  # pragma: no cover - optional dep
        log.debug("OpenTelemetry logging instrumentation not available: %s", e)


def init_telemetry(app: FastAPI, settings: Settings) -> None:
    """Initialize Azure Monitor exporters and instrumentation based on settings.

    No-op if disabled or connection string missing. Never raises.
    """
    try:
        if not settings.AZ_MONITOR_ENABLED:
            return
        conn_str = (
            settings.AZ_MONITOR_CONNECTION_STRING.get_secret_value()
            if settings.AZ_MONITOR_CONNECTION_STRING
            else None
        )
        if not conn_str:
            # No export configured; keep local logging only
            return

        # Imports are inside so the app can start without these deps installed
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource

        resource = _build_resource(settings)
        if resource is None:
            # Fall back to default resource
            resource = Resource.create({})

        # Configure exporters for traces, metrics, logs using the connection string
        # configure_azure_monitor wires providers and exporters.
        configure_azure_monitor(
            connection_string=conn_str,
            resource=resource,
        )

        # Instrument FastAPI app and common outbound dependencies
        try:
            FastAPIInstrumentor().instrument_app(app)
        except Exception:
            # If already instrumented or missing, ignore
            pass
        try:
            HTTPXClientInstrumentor().instrument()
        except Exception:
            pass

        # Ensure logging records get trace/span IDs without changing format
        enable_log_correlation()
        attach_trace_log_filter()

        log.info("Azure Monitor telemetry configured for service '%s'", settings.SERVICE_NAME)
    except Exception as e:  # pragma: no cover - fail-soft
        # Never crash the app due to telemetry wiring issues
        log.warning("Telemetry initialization failed; continuing without exporters: %s", e)
