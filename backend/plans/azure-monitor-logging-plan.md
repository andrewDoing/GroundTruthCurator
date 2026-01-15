# Azure Monitor logging + Application Insights — minimal, working plan

## Overview

Goal: add structured application logging and Azure Application Insights telemetry with the smallest working surface area. We’ll wire OpenTelemetry for traces and logs, export to Azure Monitor when `APPLICATIONINSIGHTS_CONNECTION_STRING` is present, and stay no-op otherwise. Keep current console logs for local dev while enriching log records with trace context for correlation.

We’ll add a tiny `telemetry` module, a couple of env-backed settings, initialize telemetry in `create_app()`, and instrument FastAPI and outbound HTTP calls. No legacy fallbacks; no over-engineering.

## Scope and simplicity

- Do now: request/response tracing, dependency (HTTP/Azure SDK) tracing, log correlation, and Azure export behind one env var.
- Defer: custom metrics, sampling/tail-based sampling tuning, custom spans/attributes beyond request basics.

## Files to change

- `app/core/config.py`
  - Add settings: `AZ_MONITOR_ENABLED: bool = True`, `AZ_MONITOR_CONNECTION_STRING: str | None = None`, `SERVICE_NAME: str = "gtc-backend"`.
  - Also read from standard `APPLICATIONINSIGHTS_CONNECTION_STRING` as a fallback when `AZ_MONITOR_CONNECTION_STRING` is unset.
- `app/core/logging.py`
  - Keep existing setup. Add optional log enrichment (trace_id/span_id) via a `logging.Filter` or `LogRecordFactory` when telemetry is active.
- `app/core/telemetry.py` (new)
  - Encapsulate OpenTelemetry wiring and Azure Monitor exporter configuration.
- `app/main.py`
  - Call `setup_logging(settings.LOG_LEVEL)` first; then `init_telemetry(app, settings)` after app creation.
- `pyproject.toml`
  - Add dependencies (runtime only, not dev):
    - `azure-monitor-opentelemetry`
    - `opentelemetry-instrumentation-fastapi`
    - `opentelemetry-instrumentation-asgi`
    - `opentelemetry-instrumentation-httpx`
    - `opentelemetry-instrumentation-logging`
    - `opentelemetry-instrumentation-azure-core`
- `environments/.dev.env`
  - Add commented examples for `APPLICATIONINSIGHTS_CONNECTION_STRING` and `GTC_SERVICE_NAME`.
- `README.md` and `CODEBASE.md`
  - Brief note on enabling telemetry via env var, and basic observability behavior.

## Minimal functions to add (names + purpose)

- `app/core/telemetry.py:init_telemetry(app: FastAPI, settings: Settings) -> None`
  - If connection string is present and `AZ_MONITOR_ENABLED` is true, configure OpenTelemetry resource (service.name, service.version), set tracer and meter providers, wire Azure Monitor exporters, and instrument FastAPI, httpx, and Azure SDKs. No-op otherwise.
- `app/core/telemetry.py:_build_resource(settings: Settings) -> Resource`
  - Build an OTEL `Resource` including `service.name=settings.SERVICE_NAME` and version from package metadata when available.
- `app/core/telemetry.py:enable_log_correlation() -> None`
  - Install OpenTelemetry logging integration so Python `logging` records carry `trace_id`/`span_id` and severity mapping; keep existing formatter.
- `app/core/logging.py:attach_trace_log_filter() -> None`
  - Optional: add a `logging.Filter` that injects `trace_id`/`span_id` into records when present to avoid formatter KeyErrors and ensure consistent fields.

## Behavior toggles

- Enable export when either `GTC_AZ_MONITOR_CONNECTION_STRING` or `APPLICATIONINSIGHTS_CONNECTION_STRING` is set and `GTC_AZ_MONITOR_ENABLED` is true (default true).
- Otherwise, keep local console logging only (no errors, no warnings).

## Test plan (names + short behaviors)

Unit
- `test_otel_disabled_by_default_no_conn_string`
  - With no conn string, init is no-op.
- `test_otel_enables_when_connection_string_present`
  - Sets env var; wiring functions are called.
- `test_logs_include_trace_ids_when_active`
  - Caplog shows trace_id/span_id fields on a request span.
- `test_service_name_in_resource_attributes`
  - Resource contains service.name from settings.

Integration (local, no Azure calls)
- `test_healthz_request_generates_trace_context`
  - TestClient GET /healthz logs include trace id.
- `test_httpx_dependency_creates_child_span`
  - Mock simple httpx call; span parent-child relationship exists.
- `test_no_exporter_error_without_connection_string`
  - No exceptions thrown; no exporter created.

## Step-by-step implementation (simple first)

1) Dependencies
   - Add the packages listed above to `pyproject.toml`; sync with `uv`.
2) Settings
   - In `config.py`, add fields and fallback read of `APPLICATIONINSIGHTS_CONNECTION_STRING` into `AZ_MONITOR_CONNECTION_STRING` when unset.
3) Telemetry module
   - Create `app/core/telemetry.py` with `init_telemetry`, `_build_resource`, and `enable_log_correlation`.
   - Use `azure.monitor.opentelemetry.configure_azure_monitor` for exporters, passing the connection string via env or parameter.
   - Instrumentation: `FastAPIInstrumentor().instrument_app(app)`, `HTTPXClientInstrumentor().instrument()`, `AzureInstrumentor().instrument()` (from `opentelemetry.instrumentation.azure.core`).
4) Logging enrichment
   - In `logging.py`, add `attach_trace_log_filter` and call it from `init_telemetry` after setting up OTel logging integration to avoid KeyErrors and ensure consistent fields.
5) App wiring
   - In `main.py`, after `create_app()` constructs the app instance and calls `setup_logging`, call `init_telemetry(app, settings)`.
6) Docs
   - Add a short section to `README.md` and `CODEBASE.md` describing how to enable telemetry and which env var to set in Azure (Container Apps/App Service uses `APPLICATIONINSIGHTS_CONNECTION_STRING`).
7) Env examples
   - Update `environments/.dev.env` with commented sample for local testing.

## Edge cases and guardrails

- Package absent in dev: wrap imports so the app still runs without telemetry deps (fail-soft, log once at DEBUG).
- Formatter compatibility: ensure log records always have `trace_id` and `span_id` attributes (empty string when absent) if formatter references them.
- Exporter errors: Azure exporter initialization should not crash the app; swallow with a one-time warning and continue with console logs only.
- Performance: default sampler (parent-based + always-on) is acceptable; consider rate limiting later if volume is high.
- PII: do not log request bodies or auth headers; rely on existing log levels and FastAPI instrumentation defaults.

## Configuration matrix (quick)

- Local dev
  - No env var: console logs only; OTel disabled.
  - With `APPLICATIONINSIGHTS_CONNECTION_STRING`: console logs + export to your AI resource.
- Azure (Container Apps/App Service)
  - Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in app settings; telemetry exports automatically.

## Acceptance criteria

- When connection string is set, requests to `/healthz` produce trace + correlated logs, visible in Application Insights (traces/logs tables) or via Live Metrics.
- When unset, the app behaves exactly as today with no errors or warnings related to telemetry.
- Unit tests pass and CI remains green.

