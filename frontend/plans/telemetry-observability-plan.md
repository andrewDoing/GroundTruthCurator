# Frontend Telemetry Plan: OpenTelemetry-first with Azure App Insights fallback (no code edits yet)

This document outlines a simple, incremental plan to add client-side telemetry to the React + Vite + TypeScript SPA, using OpenTelemetry (OTel) as the primary instrumentation model from the start and Azure Application Insights as a practical fallback/bridge. This is a plan only—no code changes in this step.

## Overview

We will instrument the app with: (1) safe, early initialization; (2) basic page/error collection; (3) a tiny logger wrapper for a few high-value custom events; and (4) OpenTelemetry as the first-class SDK for traces/log-like events, with the option to export to Azure Monitor or any OTLP-compatible backend. Telemetry is disabled in demo mode or when config is missing. Keep event schemas small and consistent.

## What we’ll implement now (only needed functionality)

- Initialization via a single module that no-ops in DEMO_MODE or without config
- Error capture: global unhandled errors and a React ErrorBoundary
- Minimal custom events at key business actions:
  - gtc.app_start
  - gtc.save_draft, gtc.approve
  - gtc.soft_delete, gtc.restore
  - gtc.search
  - gtc.generate_answer_start|complete|error
  - gtc.export_snapshot_start|complete|error
- Basic trace/diagnostic breadcrumbs with sampling
- A feature flag to select telemetry backend (otlp|appinsights|none) with default to OTel (otlp)

Do not add routing, correlation, or complex dashboards yet.

## Files to add/modify

Add (new):
- src/services/telemetry.ts – OTel-first init + logger facade (with backend switch)
- src/hooks/useTelemetry.ts – Hook-friendly accessors around the facade
- src/components/common/ErrorBoundary.tsx – Logs exceptions via telemetry and renders fallback
- src/models/telemetry.ts – Small types for common props and event properties

Modify (existing):
- src/main.tsx – Initialize telemetry early; wrap <App /> in ErrorBoundary
- src/hooks/useGroundTruth.ts – Log save/approve/delete/restore events
- src/services/search.ts – Log search query length and result count
- src/services/llm.ts – Log generation start/complete/error
- src/services/groundTruths.ts – Log export start/complete/error
- src/vite-env.d.ts – Add env typings for telemetry vars
- package.json – Add telemetry deps (see Dependencies)
- README.md – Document env vars + on/off behavior

## Dependencies (initial)

- OpenTelemetry (primary):
  - @opentelemetry/api
  - @opentelemetry/sdk-trace-web
  - @opentelemetry/instrumentation-document-load
  - @opentelemetry/instrumentation-fetch
  - @opentelemetry/exporter-trace-otlp-http (browser OTLP exporter)
- Azure App Insights (fallback/bridge):
  - @microsoft/applicationinsights-web (+ optional @microsoft/applicationinsights-react-js)

Note: For Azure Monitor, OTel typically exports via an OTLP collector or Data Collection Endpoint (DCE). The App Insights Web SDK remains the simplest direct-to-Monitor browser path; we retain it as a toggleable fallback.

## Environment variables

- VITE_TELEMETRY_BACKEND: "otlp" | "appinsights" | "none" (default: otlp)
- VITE_OTLP_EXPORTER_URL: OTLP HTTP endpoint (collector or DCE)
- VITE_APPINSIGHTS_CONNECTION_STRING: Azure Application Insights connection string (fallback)
- VITE_ENVIRONMENT: environment label (e.g., local, dev, staging, prod)
- VITE_BUILD_SHA: short git SHA (optional)

Telemetry should remain OFF when DEMO_MODE is true or when required env for the selected backend is missing.

## Connectivity to Azure Application Insights (guarantee)

We will support two guaranteed ways to land data in Azure Application Insights:

1) Direct browser SDK (simplest, recommended for pure client telemetry)
- Set VITE_TELEMETRY_BACKEND=appinsights and provide VITE_APPINSIGHTS_CONNECTION_STRING
- The facade maps events/exceptions/traces to App Insights track APIs
- Works fully in-browser without a collector; best for immediate connectivity

2) OpenTelemetry via an OTLP Collector that forwards to Azure Monitor (OTel-first)
- Set VITE_TELEMETRY_BACKEND=otlp and VITE_OTLP_EXPORTER_URL to your collector endpoint
- The collector uses the Azure Monitor exporter (or Data Collection Rule/Endpoint) to forward to Application Insights
- This preserves OTel semantics and enables vendor-neutral routing

Note: Direct browser OTLP export to Azure Monitor/DCE generally isn’t feasible due to auth and CORS constraints; a collector (server-side) is the supported bridge for OTel→Azure Monitor from the browser. Therefore, to guarantee App Insights connectivity in OTel mode, point the browser to your collector.

Fail-safe behavior: If backend=otlp is selected but missing exporter URL, or the app runs in DEMO_MODE, the facade will no-op or (optionally) fall back to App Insights when configured, avoiding runtime errors and ensuring you can still connect to App Insights when desired.

## Functions (names and purpose)

In src/services/telemetry.ts
- initTelemetry(opts): Initialize OTel (primary) or App Insights (fallback) once; no-op in demo or missing config. Sets sampling and common properties.
- getTelemetry(): Return the underlying client facade (OTel tracer/logger or App Insights) or a noop (never throw).
- logEvent(name, properties?): Record an event as an OTel span event (OTel path) or AI custom event (fallback), with small, stable properties.
- logException(error, severityLevel?, properties?): Capture exceptions via OTel exception event or AI trackException.
- logTrace(message, properties?): Lightweight diagnostic breadcrumb (OTel event or AI trace) under sampling.
- logDependency(name, durationMs, success, properties?): Future dependency span or AI dependency; safe no-op for now.

In src/hooks/useTelemetry.ts
- useTelemetry(): Hook-friendly wrapper returning { logEvent, logException, logTrace } that maps to the facade.

In src/components/common/ErrorBoundary.tsx
- ErrorBoundary: Catches render errors, calls logException, and renders a minimal fallback.

## Where we’ll call telemetry

- App startup (src/main.tsx): initTelemetry + logEvent("gtc.app_start")
- Save Draft (src/hooks/useGroundTruth.ts): logEvent("gtc.save_draft", {...})
- Approve (src/hooks/useGroundTruth.ts): logEvent("gtc.approve", {...})
- Soft Delete / Restore (src/hooks/useGroundTruth.ts): logEvent("gtc.soft_delete"|"gtc.restore", {...})
- Search (src/services/search.ts): logEvent("gtc.search", { queryLen, resultCount })
- Answer Generation (src/services/llm.ts): logEvent("gtc.generate_answer_start|complete|error", {...})
- Export Snapshot (src/services/groundTruths.ts): logEvent("gtc.export_snapshot_start|complete|error", {...})

Common properties to attach when available: { environment, buildSha, providerId, itemId, status, selectedRefCount, durationMs?, error? }. In OTel mode, these are span attributes; in AI mode, event properties.

## OpenTelemetry (primary) details

When VITE_TELEMETRY_BACKEND=otlp:
- Initialize OTel Web SDK with Resource { service.name: "gtc-frontend", service.version: VITE_BUILD_SHA? }
- Enable instrumentations: document load, fetch (minimal set to start)
- Configure OTLP exporter to VITE_OTLP_EXPORTER_URL (collector or Azure Monitor DCE)
- Use a single tracer (e.g., "gtc-frontend") and record events as span events named `event:<name>` with attributes = properties
- Keep event schemas identical to fallback to enable backend switching without call-site changes

## Azure Application Insights (fallback) details

When VITE_TELEMETRY_BACKEND=appinsights:
- Initialize App Insights Web SDK with connection string and set common properties
- Disable router auto-collection (no router) and enable exception tracking
- Map the same facade calls: event -> trackEvent, exception -> trackException, trace -> trackTrace

## Tests (names and brief coverage)

Unit (Vitest):
- telemetry-inits-when-config-present: Initializes client and sets common properties
- telemetry-noop-when-missing-or-demo: Safe no-op without errors
- telemetry-logEvent-passes-properties: Forwards event name + props correctly
- telemetry-logException-captures-error: Sends exception with message/stack
- error-boundary-logs-render-errors: ErrorBoundary logs and renders fallback
- event-schema-has-expected-keys: Representative event props match shape

Integration-light (mocks):
- save-draft-logs-on-success: useGroundTruth triggers telemetry on save
- approve-logs-when-gated-success: Approve path emits telemetry event
- search-logs-query-and-results: Search logs query length + count
- generate-logs-start-and-complete: Generation start/complete events observed
- export-logs-start-and-complete: Snapshot export events emitted

E2E (optional follow-up):
- telemetry-does-not-break-flows: App runs with telemetry enabled without regressions

## Step-by-step implementation checklist

1) Add dependencies: OTel packages (primary) and AI web SDK (fallback)
2) Create src/services/telemetry.ts with OTel-first init + noop-safe facade and backend switch
3) Add src/hooks/useTelemetry.ts for convenience
4) Add src/components/common/ErrorBoundary.tsx; wrap <App /> in src/main.tsx
5) Touch key call sites (save/approve/delete/restore/search/generate/export) to log events
6) Add env typings in src/vite-env.d.ts and document in README.md
7) Sampling: enable ~25% initially to control volume (OTel sampler and/or AI sampling)
8) Ensure telemetry is disabled in DEMO_MODE or missing config for selected backend
9) Write unit tests with SDK mocks; spot-check integration-light tests

## Out of scope (for now)

- Router-based page view tracking
- User/session analytics beyond defaults
- Complex correlation between frontend and backend traces
- Streaming UI updates for generation tied to traces
- PII or content-level logging (we only log IDs/counts/lengths)

## Acceptance criteria

- App starts with telemetry initialized when configured; no errors if not
- Core events emit with consistent, small property sets
- Errors are captured via ErrorBoundary and global handlers
- DEMO_MODE and missing config result in safe no-ops
- Unit tests cover initialization and representative event emission

## Notes

- Keep event names under the `gtc.*` namespace and properties minimal
- Prefer IDs/counts/lengths over raw content to avoid PII
- The facade approach allows flipping to OTel later without widespread changes
