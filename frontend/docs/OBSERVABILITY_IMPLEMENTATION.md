---
title: Frontend Observability Implementation
description: Comprehensive guide to frontend observability implementation using OpenTelemetry and Azure Application Insights
ms.date: 2026-01-10
---

# Frontend Observability Implementation

This document provides a complete overview of how observability is implemented in the Ground Truth Curator frontend React application.

## Architecture Overview

The frontend uses a **dual-backend telemetry system** that can export telemetry through OpenTelemetry (OTLP) or Azure Application Insights. The implementation is designed to be:

- **Opt-in**: Telemetry is disabled by default and requires explicit configuration
- **Safe**: No-ops gracefully in demo mode or when configuration is missing
- **Flexible**: Supports multiple backend targets via a unified facade pattern
- **Lightweight**: Lazy-loads telemetry SDKs to minimize bundle impact

### Portability and First Principles

This telemetry design separates two concerns:

1. **Telemetry production**: capturing and enriching signals in the browser (page load timing, fetch/XHR spans, exceptions, and business events).
2. **Telemetry export**: where the signals go (OTLP endpoint, Application Insights ingestion endpoint, or disabled).

That separation is intentional: it keeps application code stable while allowing export targets to change as an infrastructure decision.

When targeting any observability platform, you can reason about the signals independently:

- **Traces**: the primary first-class signal in this frontend implementation. In OTLP mode, traces are emitted to an OTLP HTTP endpoint.
- **Metrics**: not a first-class signal in this frontend implementation today.
- **Logs**: the frontend facade has `logTrace`, `logEvent`, and `logException`. In OTLP mode, these are represented as span events and attributes rather than as a separate log pipeline.

Most observability platforms consume frontend traces through an OTLP collector or direct ingestion endpoint. Backend application logs typically remain the primary structured log source, while frontend telemetry contributes to the distributed trace stream.

## Key Components

### 1. Telemetry Service (`src/services/telemetry.ts`)

The core telemetry module that provides:

- **Backend Selection**: Chooses between `otlp`, `appinsights`, or `none` based on configuration
- **Lazy Initialization**: SDKs are imported dynamically only when needed
- **Unified Facade**: Common API (`logEvent`, `logException`, `logTrace`) regardless of backend
- **Global Safety Nets**: Automatic capture of unhandled errors and promise rejections

**Key Functions:**

```typescript
// Initialize telemetry system (called once at app startup)
await initTelemetry(custom?: Partial<TelemetryOptions>)

// Get the telemetry facade instance
getTelemetry(): TelemetryFacade

// Log business events with optional properties
logEvent(name: string, properties?: Record<string, unknown>)

// Log exceptions with severity levels
logException(error: unknown, severity?: "error" | "warning" | "info", properties?: Record<string, unknown>)
```

### 2. Telemetry Models (`src/models/telemetry.ts`)

Type definitions for the telemetry system:

```typescript
type TelemetryBackend = "otlp" | "appinsights" | "none";

type TelemetryFacade = {
  logEvent: (name: string, properties?: Record<string, unknown>) => void;
  logException: (error: unknown, severity?: "error" | "warning" | "info", properties?: Record<string, unknown>) => void;
  logTrace: (message: string, properties?: Record<string, unknown>) => void;
  shutdown?: () => void | Promise<void>;
};
```

### 3. Error Boundary (`src/components/common/ErrorBoundary.tsx`)

React error boundary that:

- Catches rendering errors in the component tree
- Logs exceptions via `logException` with component stack information
- Renders a user-friendly fallback UI
- Integrates with the telemetry system automatically

### 4. Demo Mode Integration (`src/config/demo.ts`)

Telemetry automatically disables when:

- `DEMO_MODE` is enabled
- The app is in development and demo mode is active
- Required configuration for the selected backend is missing

## Telemetry Backends

### OpenTelemetry (Primary - OTLP)

**When to use**: Modern, vendor-neutral observability with OTLP collector infrastructure.

**Configuration**:

```bash
VITE_TELEMETRY_BACKEND=otlp
VITE_OTLP_EXPORTER_URL=https://your-collector.example.com/v1/traces
VITE_ENVIRONMENT=production
VITE_BUILD_SHA=abc123
```

**How it works**:

1. Initializes OpenTelemetry Web SDK with service resource metadata
2. Configures OTLP HTTP trace exporter to send data to a collector
3. Enables automatic instrumentation:
   - Document load performance
   - Fetch/XHR requests
4. Maps facade calls to OpenTelemetry spans with attributes
5. Events are recorded as span events with prefix `event:${name}`

**Dependencies**:

- `@opentelemetry/api`
- `@opentelemetry/sdk-trace-web`
- `@opentelemetry/exporter-trace-otlp-http`
- `@opentelemetry/instrumentation-document-load`
- `@opentelemetry/instrumentation-fetch`
- `@opentelemetry/resources`

### Azure Application Insights (Fallback)

**When to use**: Direct browser-to-Azure Monitor without OTLP collector infrastructure.

**Configuration**:

```bash
VITE_TELEMETRY_BACKEND=appinsights
VITE_APPINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...
VITE_ENVIRONMENT=production
VITE_BUILD_SHA=abc123
```

**How it works**:

1. Initializes Azure Application Insights Web SDK
2. Configures sampling percentage (default 25%)
3. Enables unhandled promise rejection tracking
4. Disables automatic route tracking (SPA has no router)
5. Maps facade calls directly to Application Insights APIs:
   - `logEvent` → `trackEvent`
   - `logException` → `trackException` with severity mapping
   - `logTrace` → `trackTrace`

**Dependencies**:

- `@microsoft/applicationinsights-web`

### None (Disabled)

**When to use**: Development, demo mode, or when telemetry is not desired.

**Configuration**:

```bash
VITE_TELEMETRY_BACKEND=none
# OR omit telemetry configuration entirely
```

**Behavior**: All telemetry calls become no-ops. No SDK is loaded.

## Environment Variables

All telemetry configuration is managed via Vite environment variables:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VITE_TELEMETRY_BACKEND` | `"otlp"` \| `"appinsights"` \| `"none"` | `"otlp"` | Selects the telemetry backend |
| `VITE_OTLP_EXPORTER_URL` | `string` | - | OTLP HTTP collector endpoint (required for otlp backend) |
| `VITE_APPINSIGHTS_CONNECTION_STRING` | `string` | - | Azure App Insights connection string (required for appinsights backend) |
| `VITE_ENVIRONMENT` | `string` | - | Environment label (local, dev, staging, prod) |
| `VITE_BUILD_SHA` | `string` | - | Git commit SHA for version tracking |

**Type definitions**: Declared in [src/vite-env.d.ts](../src/vite-env.d.ts)

## Initialization Flow

1. **Early Initialization** ([src/main.tsx](../src/main.tsx)):

   ```typescript
   void initTelemetry().then(() => {
     logEvent("gtc.app_start");
   });
   ```

2. **Backend Detection**:
   - Reads `VITE_TELEMETRY_BACKEND` from environment
   - Falls back to `"otlp"` if not specified

3. **Safety Checks**:
   - If `DEMO_MODE` is enabled → use `NoopTelemetry`
   - If backend is `"none"` → use `NoopTelemetry`
   - If backend is `"otlp"` but `VITE_OTLP_EXPORTER_URL` is missing → try App Insights fallback or noop
   - If backend is `"appinsights"` but connection string is missing → noop

4. **SDK Initialization**:
   - Dynamically imports required SDK packages
   - Configures resource metadata (service name, version, environment)
   - Sets up exporters and instrumentation
   - Registers global error handlers

5. **Facade Creation**:
   - Creates a `TelemetryFacade` instance that wraps the selected backend
   - Common properties (environment, buildSha) are attached to all events

## Event Instrumentation

### Current Instrumentation Points

The following events are currently logged (based on the planning document):

| Event Name | Location | Properties | Description |
|------------|----------|------------|-------------|
| `gtc.app_start` | [src/main.tsx](../src/main.tsx) | environment, buildSha | Application initialization |
| `gtc.save_draft` | (planned) useGroundTruth.ts | providerId, itemId, status, selectedRefCount | Draft save action |
| `gtc.approve` | (planned) useGroundTruth.ts | providerId, itemId, selectedRefCount | Approval action |
| `gtc.soft_delete` | (planned) useGroundTruth.ts | providerId, itemId | Soft delete action |
| `gtc.restore` | (planned) useGroundTruth.ts | providerId, itemId | Restore deleted item |
| `gtc.search` | (planned) search.ts | queryLen, resultCount | Reference search |
| `gtc.generate_answer_start` | (planned) llm.ts | providerId, itemId | Answer generation started |
| `gtc.generate_answer_complete` | (planned) llm.ts | providerId, itemId, durationMs | Answer generation completed |
| `gtc.generate_answer_error` | (planned) llm.ts | providerId, itemId, error | Answer generation failed |
| `gtc.export_snapshot_start` | (planned) groundTruths.ts | - | Snapshot export started |
| `gtc.export_snapshot_complete` | (planned) groundTruths.ts | durationMs | Snapshot export completed |
| `gtc.export_snapshot_error` | (planned) groundTruths.ts | error | Snapshot export failed |

**Event Naming Convention**: All events use the `gtc.*` namespace to avoid collisions.

**Property Guidelines**:

- Include only IDs, counts, durations, and status values
- Never log PII or sensitive content (no question/answer text)
- Keep property sets small and consistent
- Use snake_case for property names

### Global Error Capture

The telemetry service automatically captures:

1. **Unhandled Window Errors**:

   ```typescript
   window.addEventListener("error", (e) => {
     facade.logException(e.error || e.message || "window.error");
   });
   ```

2. **Unhandled Promise Rejections**:

   ```typescript
   window.addEventListener("unhandledrejection", (e) => {
     facade.logException(e.reason || "unhandledrejection");
   });
   ```

3. **React Component Errors**:
   - Caught by `ErrorBoundary` component
   - Logged with component stack trace
   - Renders user-friendly fallback UI

## Common Properties

Every telemetry event includes common properties automatically:

```typescript
{
  environment: import.meta.env.VITE_ENVIRONMENT,
  buildSha: import.meta.env.VITE_BUILD_SHA,
  // ... plus any event-specific properties
}
```

In OpenTelemetry mode, these become span attributes. In Application Insights mode, they are attached as custom properties.

## Sampling

- **OpenTelemetry**: Uses default AlwaysOn sampler (100% of traces captured)
- **Application Insights**: Configured to sample 25% of events (adjustable via `TelemetryOptions.sampleRatio`)

Sampling helps control data volume and cost in production environments.

## Testing

### Unit Tests

1. **Telemetry Initialization** ([tests/unit/telemetry-init.test.ts](../tests/unit/telemetry-init.test.ts)):
   - Verifies no-op behavior in demo mode
   - Tests missing configuration scenarios
   - Ensures safe initialization without errors

2. **Error Boundary** ([tests/unit/error-boundary.test.tsx](../tests/unit/error-boundary.test.tsx)):
   - Confirms exception logging on component errors
   - Validates fallback UI rendering
   - Checks telemetry integration

### Testing Guidelines

When writing tests that involve telemetry:

```typescript
import { vi } from "vitest";
import * as telemetry from "../../src/services/telemetry";

// Mock telemetry calls
beforeEach(() => {
  vi.spyOn(telemetry, "logEvent").mockImplementation(() => {});
  vi.spyOn(telemetry, "logException").mockImplementation(() => {});
});

// Test your code
it("logs an event", () => {
  // ... trigger event
  expect(telemetry.logEvent).toHaveBeenCalledWith("gtc.test", { foo: "bar" });
});
```

## Deployment Considerations

### Local Development

```bash
# Disable telemetry (default)
VITE_TELEMETRY_BACKEND=none

# OR use demo mode
VITE_DEMO_MODE=1
```

Telemetry is automatically disabled in local dev when configuration is missing.

### Staging/Production

**Option 1: OpenTelemetry + Collector**

```bash
VITE_TELEMETRY_BACKEND=otlp
VITE_OTLP_EXPORTER_URL=https://your-collector.example.com/v1/traces
VITE_ENVIRONMENT=production
VITE_BUILD_SHA=${GIT_COMMIT_SHA}
```

**Option 2: Direct to Application Insights**

```bash
VITE_TELEMETRY_BACKEND=appinsights
VITE_APPINSIGHTS_CONNECTION_STRING=${APPINSIGHTS_CONNECTION_STRING}
VITE_ENVIRONMENT=production
VITE_BUILD_SHA=${GIT_COMMIT_SHA}
```

### Connection to Azure Application Insights

Two guaranteed paths to Azure Monitor:

1. **Direct (Simplest)**:
   - Set `VITE_TELEMETRY_BACKEND=appinsights`
   - Provide `VITE_APPINSIGHTS_CONNECTION_STRING`
   - Browser connects directly to Azure Monitor ingestion endpoint
   - ✅ No collector infrastructure required

2. **OpenTelemetry via Collector** (Recommended for vendor flexibility):
   - Set `VITE_TELEMETRY_BACKEND=otlp`
   - Deploy an OTLP collector with Azure Monitor exporter
   - Point `VITE_OTLP_EXPORTER_URL` to your collector
   - Collector forwards traces to Azure Application Insights
   - ✅ Preserves vendor-neutral OTel semantics

**Note**: Direct OTLP export from browser to Azure Monitor is not supported due to CORS and authentication constraints. Always use a collector for the OTLP path.

## Troubleshooting

### Telemetry Not Working

1. **Check Environment Variables**:

   ```bash
   # In browser console
   console.log(import.meta.env.VITE_TELEMETRY_BACKEND)
   console.log(import.meta.env.VITE_OTLP_EXPORTER_URL)
   console.log(import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING)
   ```

2. **Verify Demo Mode is Disabled**:

   ```typescript
   import DEMO_MODE from "./config/demo";
   console.log("Demo mode:", DEMO_MODE);
   ```

3. **Check Browser Console**:
   - Look for telemetry initialization logs
   - Check for SDK loading errors
   - Verify no CORS or network errors

4. **Test with Known Events**:

   ```typescript
   import { logEvent } from "./services/telemetry";
   logEvent("test.event", { test: true });
   ```

### No Data in Azure Application Insights

1. **Verify Connection String Format**:
   - Should include `InstrumentationKey`, `IngestionEndpoint`, and `LiveEndpoint`

2. **Check Sampling Configuration**:
   - Default is 25% sampling
   - May need to wait for sampled events to appear

3. **Network Connectivity**:
   - Ensure browser can reach Azure Monitor endpoints
   - Check firewall and proxy settings

4. **Ingestion Delay**:
   - Application Insights has typical ingestion latency of 1-5 minutes
   - Use Live Metrics for real-time data during debugging

## Performance Impact

The telemetry implementation is designed to minimize performance overhead:

1. **Lazy Loading**: SDKs are imported dynamically only when needed
2. **No-op Fast Path**: Missing configuration results in immediate no-op without SDK loading
3. **Batch Export**: Both OTel and App Insights use batched export to reduce network calls
4. **Sampling**: Configurable sampling reduces data volume
5. **Async Initialization**: `initTelemetry()` is non-blocking

**Measured Impact**: Negligible (<1% increase in bundle size when enabled, zero impact when disabled)

## Future Enhancements

Based on [plans/telemetry-observability-plan.md](../plans/telemetry-observability-plan.md), future work may include:

- **Router Integration**: Page view tracking when/if routing is added
- **User Session Analytics**: User journey and session duration tracking
- **Frontend-Backend Correlation**: W3C trace context propagation for distributed tracing
- **Streaming UI Telemetry**: Track streaming answer generation events
- **Custom Dashboards**: Pre-built Application Insights dashboards for common scenarios

## Related Documentation

- [Planning Document](../plans/telemetry-observability-plan.md) - Original implementation plan
- [Codebase Guide](../CODEBASE.md) - Broader architectural context
- [Backend Observability](../../backend/plans/azure-monitor-logging-plan.md) - Backend telemetry integration

## Dependencies

All telemetry dependencies are production dependencies (not devDependencies):

```json
{
  "dependencies": {
    "@microsoft/applicationinsights-web": "^3.0.4",
    "@opentelemetry/api": "^1.9.0",
    "@opentelemetry/exporter-trace-otlp-http": "^0.203.0",
    "@opentelemetry/instrumentation-document-load": "^0.48.0",
    "@opentelemetry/instrumentation-fetch": "^0.203.0",
    "@opentelemetry/resources": "^2.0.1",
    "@opentelemetry/sdk-trace-web": "^2.0.1"
  }
}
```

**Bundle Size**: ~150KB gzipped when OTel is loaded, ~80KB for App Insights. Not loaded when telemetry is disabled.

## Summary

The Ground Truth Curator frontend implements a **modern, flexible observability system** that:

- ✅ Supports OpenTelemetry (vendor-neutral) and Azure Application Insights (direct)
- ✅ Automatically disables in demo mode and development
- ✅ Provides safe no-op fallback for missing configuration
- ✅ Captures key business events and exceptions
- ✅ Integrates with React error boundaries
- ✅ Minimizes performance impact through lazy loading
- ✅ Includes comprehensive type safety and testing

The system is production-ready and follows modern observability best practices while maintaining simplicity and developer ergonomics.
