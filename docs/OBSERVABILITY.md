# Observability

## Purpose

Ground Truth Curator uses append-only JSONL files in `.harness/` as the local, agent-facing observability contract. The backend emits one structured log record and one structured trace record for each HTTP request when harness JSONL is enabled.

## Files And Ownership

```text
.harness/
  logs.jsonl    # request log lines
  traces.jsonl  # request span records
```

- JSONL emission is implemented in `backend/app/core/harness_observability.py`.
- Middleware installation happens in `backend/app/main.py` when `GTC_HARNESS_JSONL_ENABLED=true`.
- `.harness/` is ephemeral local state and should not be committed.

## Current Contract

### `logs.jsonl`

One JSON object per completed HTTP request.

Example:

```json
{"ts":"2026-03-13T12:00:00+00:00","level":"INFO","msg":"GET /healthz 200","service":"gtc-api","trace_id":"3b7c...","span_id":"f83f1b02a9f54fbe","duration_ms":8,"status":"ok","method":"GET","path":"/healthz","http_status":200,"error":null}
```

### `traces.jsonl`

One JSON object per completed HTTP request span.

Example:

```json
{"trace_id":"3b7c...","span_id":"f83f1b02a9f54fbe","parent_id":null,"name":"GET /healthz","service":"gtc-api","start":"2026-03-13T12:00:00+00:00","end":"2026-03-13T12:00:00+00:00","duration_ms":8,"status":"ok","method":"GET","path":"/healthz","http_status":200}
```

## Required Event Fields

### Required fields in `.harness/logs.jsonl`

| Field | Required | Notes |
|---|---|---|
| `ts` | yes | ISO 8601 completion timestamp |
| `level` | yes | `INFO`, `WARN`, or `ERROR` in the current implementation |
| `msg` | yes | `<METHOD> <PATH> <STATUS>` |
| `service` | yes | `settings.SERVICE_NAME` |
| `trace_id` | yes | Correlates log and trace records |
| `span_id` | yes | Per-request span id |
| `duration_ms` | yes | Rounded request duration |
| `status` | yes | `ok` for `<400`, otherwise `error` |
| `method` | yes | HTTP verb |
| `path` | yes | Request path |
| `http_status` | yes | Numeric HTTP status |
| `error` | yes | `null` on success, `"client error"` for 4xx, `"server error"` for 5xx, or exception class name for unhandled exceptions |

### Required fields in `.harness/traces.jsonl`

| Field | Required | Notes |
|---|---|---|
| `trace_id` | yes | Request correlation id |
| `span_id` | yes | Per-request span id |
| `parent_id` | yes | Currently always `null` |
| `name` | yes | `<METHOD> <PATH>` |
| `service` | yes | `settings.SERVICE_NAME` |
| `start` | yes | ISO 8601 start timestamp |
| `end` | yes | ISO 8601 completion timestamp |
| `duration_ms` | yes | Rounded request duration |
| `status` | yes | `ok` or `error` |
| `method` | yes | HTTP verb |
| `path` | yes | Request path |
| `http_status` | yes | Numeric HTTP status |

## Level Policy

Ground Truth Curator's current HTTP logging policy comes directly from `backend/app/core/harness_observability.py`:

| Condition | Level | Status | `error` field |
|---|---|---|---|
| HTTP `<400` | `INFO` | `ok` | `null` |
| HTTP `400-499` | `WARN` | `error` | `"client error"` |
| HTTP `>=500` | `ERROR` | `error` | `"server error"` |
| Unhandled exception | `ERROR` | `error` | exception class name |

Notes:

- The current code treats all `<400` responses as `INFO`, so successful redirects stay out of the warning channel.
- There is no separate slow-request warning emitter today. Slow requests are reviewed from `traces.jsonl` with `jq`.
- Deployed environments may also emit Azure Monitor / OpenTelemetry telemetry, but `.harness/*.jsonl` is the local harness contract agents should inspect first.

## Environment Toggles

### Core harness switches

- `GTC_HARNESS_JSONL_ENABLED=true`
  - Installs the JSONL middleware and writes `.harness/logs.jsonl` and `.harness/traces.jsonl`.
- `GTC_AZ_MONITOR_ENABLED=false`
  - Used by the smoke flow to keep local verification self-contained and avoid Azure Monitor dependencies.

### Backend behavior switches commonly used with the harness

- `GTC_REPO_BACKEND=memory`
  - Keeps local smoke and demo runs independent of Cosmos.
- `GTC_DEMO_MODE=true`
  - Enables demo data in memory-backed backend flows.
- `GTC_DEMO_USER_ID=demo-user`
  - Stable demo identity used by the backend.
- `GTC_ENV_FILE=...`
  - Layers explicit backend environment files when needed.

### Frontend and local-dev switches

- `VITE_DEMO_MODE=true`
  - Makes `useGroundTruth()` choose the demo provider in supported builds.
- `VITE_DEV_USER_ID=demo-user`
  - Injects a dev `X-User-Id` through the frontend client.
- `HARNESS_BACKEND_URL=http://localhost:8000`
  - Vite proxy target for `/v1`.
- `HARNESS_BACKEND_PORT`, `HARNESS_FRONTEND_PORT`
  - Ports used by harness dev-up scripts.
- `VITE_SELF_SERVE_LIMIT`, `VITE_REQUIRE_REFERENCE_VISIT`, `VITE_REQUIRE_KEY_PARAGRAPH`
  - Runtime workflow toggles consumed from `/v1/config` with environment fallback.

### Smoke-script overrides

- `HARNESS_SMOKE_PORT`
- `HARNESS_SMOKE_HEALTH_URL`
- `HARNESS_SMOKE_URL`

These allow the smoke probe to target non-default local ports or URLs without changing the script.

## Smoke And Verify Commands

### Smoke

Run:

```bash
make -f Makefile.harness smoke
```

What it proves today:

1. Starts the backend with:

   ```bash
   GTC_AZ_MONITOR_ENABLED=false \
   GTC_HARNESS_JSONL_ENABLED=true \
   uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
   ```

2. Probes:
   - `GET /healthz`
   - `GET /v1/openapi.json`
3. Builds the frontend with `cd frontend && npm run build`
4. Fails if either `.harness/logs.jsonl` or `.harness/traces.jsonl` is missing or empty

### Check, CI, verify

```bash
make -f Makefile.harness check
make -f Makefile.harness ci
make -f Makefile.harness verify
make -f Makefile.harness observe
```

- `check` runs repo lint and typecheck wrappers.
- `ci` runs `smoke`, `check`, `api-check`, and `test`.
- `verify` runs `ci` and then prints recent runtime errors and slow requests with `jq`.
- `observe` gives a quick count of errors, slow traces, and line counts without a full test run.

## jq Review Examples

Use these from the repository root after a smoke, dev, or verify run.

```bash
# current verify target: recent runtime errors
jq 'select(.level == "ERROR")' .harness/logs.jsonl | tail -5

# include 4xx warnings as well
jq 'select(.level == "WARN" or .level == "ERROR")' .harness/logs.jsonl | tail -20

# current verify target: slow requests over 1s
jq 'select(.duration_ms > 1000)' .harness/traces.jsonl | tail -5

# current observe target: count runtime errors
jq -s 'map(select(.level == "ERROR")) | length' .harness/logs.jsonl

# current observe target: count traces slower than 500 ms
jq -s 'map(select(.duration_ms > 500)) | length' .harness/traces.jsonl

# inspect a single request across both files
jq --arg tid "<trace_id>" 'select(.trace_id == $tid)' .harness/logs.jsonl .harness/traces.jsonl
```

## Review Expectations For Agents

- After backend or frontend changes, prefer `make -f Makefile.harness verify`.
- If `verify` is too heavy for the current task, run `make -f Makefile.harness smoke` and inspect `.harness/*.jsonl` directly.
- Treat `WARN` records as user-visible workflow failures or contract mismatches worth reviewing, not just infrastructure noise.
- Treat slow traces as performance regressions even when logs contain no `ERROR` records.
