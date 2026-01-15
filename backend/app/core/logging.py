import logging
import sys
from contextvars import ContextVar

# Context var storing current user identity (email/oid/header). Empty string if unknown.
current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")

try:
    # Importing here to avoid hard dependency; used only when available
    from opentelemetry import trace as otel_trace  # type: ignore
except Exception:  # pragma: no cover - optional dep
    otel_trace = None  # type: ignore


def setup_logging(level: str = "INFO") -> None:
    # Suppress logs from the entire azure namespace (includes azure.core, azure.storage, etc.)
    logging.getLogger("azure").setLevel(logging.WARNING)

    # Additionally suppress detailed HTTP pipeline logs
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

    # Basic structured-ish logging setup suitable for dev
    root = logging.getLogger()
    if root.handlers:
        return  # already configured
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s user=%(user_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Ensure every LogRecord has a user_id attribute even if filter not run (e.g., 3rd party logger earlier)
    _install_log_record_factory()


class _TraceContextFilter(logging.Filter):
    """Injects trace_id, span_id and user_id into LogRecord if available.

    Always sets the attributes to strings to keep formatters safe.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - logging API
        trace_id = ""
        span_id = ""
        user_id = ""
        try:
            # Fetch user id from contextvar (safe default already provided)
            user_id = current_user_id.get()
        except Exception:  # pragma: no cover - extremely unlikely
            user_id = ""
        try:
            if otel_trace is not None:
                span = otel_trace.get_current_span()
                ctx = span.get_span_context() if span else None
                if ctx and getattr(ctx, "trace_id", None):
                    # Format as 32-char hex per W3C TraceContext
                    trace_id = f"{ctx.trace_id:032x}"
                    span_id = f"{ctx.span_id:016x}"
        except Exception:
            # Never break logging
            trace_id = ""
            span_id = ""
        # Attach attributes even if empty
        setattr(record, "trace_id", trace_id)
        setattr(record, "span_id", span_id)
        # user_id attribute consumed by formatter
        setattr(record, "user_id", user_id)
        return True


def attach_trace_log_filter() -> None:
    """Attach the trace context filter to the root handler(s).

    Safe to call multiple times.
    """
    root = logging.getLogger()
    filt = _TraceContextFilter()
    for h in root.handlers:
        # Avoid dup filters
        if not any(isinstance(f, _TraceContextFilter) for f in getattr(h, "filters", [])):
            h.addFilter(filt)


# --- User identity helpers ---


def set_current_user(user_id: str | None) -> None:
    """Set the current user identity for logging.

    Use empty string when None provided so formatter output is stable (user=).
    """
    try:
        current_user_id.set(user_id or "")
    except Exception:  # pragma: no cover - defensive
        pass


def clear_current_user() -> None:
    """Clear user identity after a request finishes."""
    try:
        current_user_id.set("")
    except Exception:  # pragma: no cover - defensive
        pass


_original_factory = logging.getLogRecordFactory()


def _install_log_record_factory() -> None:
    try:
        factory = logging.getLogRecordFactory()
        if getattr(factory, "__name__", "") == "_user_inject_factory":  # already installed
            return

        def _user_inject_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
            record = _original_factory(*args, **kwargs)  # type: ignore[misc]
            # Always (re)inject user_id from context to keep it authoritative.
            # But do NOT trigger KeyError if logging call supplied extra={"user_id": ...}.
            # Python logging raises when extra attempts to overwrite an existing attribute.
            # We sidestep by assigning after record creation unconditionally.
            try:
                record.user_id = current_user_id.get()  # type: ignore[attr-defined]
            except Exception:
                try:
                    record.user_id = getattr(record, "user_id", "")  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover - extremely defensive
                    pass
            return record

        _user_inject_factory.__name__ = "_user_inject_factory"  # for idempotence check
        logging.setLogRecordFactory(_user_inject_factory)
    except Exception:  # pragma: no cover
        pass


def user_logging_middleware(app):  # type: ignore[no-untyped-def]
    """Install a lightweight middleware that populates user context for logging.

    This middleware should run after auth middleware so that request.state.principal
    (Easy Auth) or headers (dev mode) are available. It does not enforce auth; it only
    propagates identity into log lines.
    """

    @app.middleware("http")
    async def _user_log(ctx, call_next):  # type: ignore[no-redef]
        from fastapi import Request
        from app.core.auth import get_current_principal, settings as _settings  # lazy import

        request: Request = ctx
        user_id = ""
        try:
            if _settings.EZAUTH_ENABLED:
                principal = get_current_principal(request)
                if principal:
                    user_id = (
                        principal.email
                        or principal.oid
                        or principal.name
                        or request.headers.get("X-User-Id")
                        or ""
                    )
            else:
                # Dev mode: honor X-User-Id header else anonymous
                user_id = request.headers.get("X-User-Id") or "anonymous"
        except Exception:  # pragma: no cover
            user_id = ""
        set_current_user(user_id)
        try:
            response = await call_next(request)
        finally:
            clear_current_user()
        return response

    return app
