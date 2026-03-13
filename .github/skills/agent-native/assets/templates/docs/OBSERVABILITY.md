# Observability

## Goal

Give coding agents runtime visibility — errors, slow requests, trace correlation — without requiring a full observability stack.

## Default: JSONL + jq (Zero Dependencies)

All telemetry writes to `.harness/` as append-only JSONL files:

```
.harness/
  logs.jsonl        # Structured log lines
  traces.jsonl      # Span records (start, end, trace_id, parent_id)
  metrics.jsonl     # Metric data points
```

### Log Format

One JSON object per line. Required fields:

```json
{"ts":"2026-02-28T14:05:32.123Z","level":"ERROR","msg":"Connection timeout","service":"api","trace_id":"abc123","duration_ms":5012}
```

| Field | Required | Description |
|---|---|---|
| `ts` | ✅ | ISO 8601 timestamp |
| `level` | ✅ | TRACE, DEBUG, INFO, WARN, ERROR, FATAL (see level policy below) |
| `msg` | ✅ | Human-readable message |
| `service` | ✅ | Service/component name |
| `trace_id` | | Correlation ID across events |
| `span_id` | | Span identifier |
| `parent_id` | | Parent span for trace trees |
| `duration_ms` | | Request/operation duration |
| `status` | | ok, error |
| `error` | | Error message/stack (when level=ERROR) |
| `*` | | Any additional fields |

### Level Policy

Use the right level for HTTP responses and application events:

| Condition | Level | Example |
|---|---|---|
| Success (2xx) | `INFO` | `{"level":"INFO","msg":"GET /tasks 200","status":"ok"}` |
| Client error (4xx) | `WARN` | `{"level":"WARN","msg":"GET /tasks/999 404","status":"error","error":"not found"}` |
| Server error (5xx) | `ERROR` | `{"level":"ERROR","msg":"POST /tasks 500","status":"error","error":"db connection refused"}` |
| Unhandled exception | `ERROR` | `{"level":"ERROR","msg":"unhandled exception","error":"TypeError: ..."}` |
| Slow request (>threshold) | `WARN` | `{"level":"WARN","msg":"slow request","duration_ms":3200}` |

**Why this matters:** Agents use `jq 'select(.level == "ERROR")'` to find problems. If 404s are logged as INFO, agents miss application failures. If 404s are logged as ERROR, agents drown in noise from expected "not found" responses. WARN is the compromise — visible in targeted queries (`level == "WARN" or level == "ERROR"`) without polluting the error channel.

> **Rule of thumb:** If the *caller* made a mistake → WARN. If *your code* broke → ERROR.

### Trace Format

```json
{"trace_id":"abc123","span_id":"span1","parent_id":null,"name":"GET /api/users","service":"api","start":"2026-02-28T14:05:32.000Z","end":"2026-02-28T14:05:32.245Z","duration_ms":245,"status":"ok"}
```

### Metric Format (optional)

Metrics are **optional** for dev-time use. Traces already capture `duration_ms` per request, which is sufficient for performance analysis. Use metrics only if you need counters or gauges (e.g., queue depth, cache hit rate) that don't map to individual requests.

```json
{"ts":"2026-02-28T14:05:32.000Z","name":"http.duration","service":"api","value":245,"unit":"ms"}
```

## Querying (jq)

Common queries for agents:

```bash
# Recent errors
jq 'select(.level == "ERROR")' .harness/logs.jsonl

# Errors AND warnings (catches 4xx + 5xx)
jq 'select(.level == "ERROR" or .level == "WARN")' .harness/logs.jsonl

# Errors in the last 5 minutes (agent computes cutoff timestamp)
jq --arg since "2026-02-28T14:00:00Z" 'select(.level == "ERROR" and .ts >= $since)' .harness/logs.jsonl

# Slow requests (>500ms)
jq 'select(.duration_ms > 500)' .harness/traces.jsonl

# All events for a specific trace
jq --arg tid "abc123" 'select(.trace_id == $tid)' .harness/logs.jsonl .harness/traces.jsonl

# Error count by service
jq -s 'map(select(.level == "ERROR")) | group_by(.service) | map({service: .[0].service, count: length})' .harness/logs.jsonl

# Unique error messages
jq -s 'map(select(.level == "ERROR")) | map(.msg) | unique' .harness/logs.jsonl
```

### Pre-Built Query Library

Copy `.harness/queries/` into your repo for common agent queries:

```bash
# .harness/queries/errors.jq
select(.level == "ERROR")

# .harness/queries/slow.jq — pass --argjson threshold 500
select(.duration_ms > $threshold)

# .harness/queries/trace.jq — pass --arg tid <trace_id>
select(.trace_id == $tid)
```

Usage: `jq -f .harness/queries/errors.jq .harness/logs.jsonl`

## Logging in Your App

### Node.js (zero deps)

```typescript
import { appendFileSync, mkdirSync } from 'fs';
import { randomUUID } from 'crypto';

mkdirSync('.harness', { recursive: true });

function hlog(entry: Record<string, unknown>) {
  const line = JSON.stringify({ ts: new Date().toISOString(), ...entry });
  appendFileSync('.harness/logs.jsonl', line + '\n');
}

function htrace(entry: Record<string, unknown>) {
  const line = JSON.stringify(entry);
  appendFileSync('.harness/traces.jsonl', line + '\n');
}

// --- Logging (writes to .harness/logs.jsonl) ---
hlog({ level: 'INFO', msg: 'GET /tasks 200', service: 'api', duration_ms: 12 });
hlog({ level: 'WARN', msg: 'GET /tasks/999 404', service: 'api', status: 'error', error: 'not found' });
hlog({ level: 'ERROR', msg: 'POST /tasks 500', service: 'api', status: 'error', error: err.message });

// --- Tracing (writes to .harness/traces.jsonl) ---
// Call htrace() in middleware after each request completes:
const traceId = randomUUID();
const start = new Date();
// ... handle request ...
const end = new Date();
htrace({
  trace_id: traceId, span_id: randomUUID(), parent_id: null,
  name: `${req.method} ${req.path}`, service: 'api',
  start: start.toISOString(), end: end.toISOString(),
  duration_ms: end.getTime() - start.getTime(),
  status: res.statusCode < 400 ? 'ok' : 'error'
});
```

### Python (zero deps)

```python
import json, datetime, pathlib, uuid

pathlib.Path(".harness").mkdir(exist_ok=True)

def hlog(**kwargs):
    entry = {"ts": datetime.datetime.utcnow().isoformat() + "Z", **kwargs}
    pathlib.Path(".harness/logs.jsonl").open("a").write(json.dumps(entry) + "\n")

def htrace(**kwargs):
    pathlib.Path(".harness/traces.jsonl").open("a").write(json.dumps(kwargs) + "\n")

# --- Logging ---
hlog(level="INFO", msg="GET /tasks 200", service="api", duration_ms=8)
hlog(level="WARN", msg="GET /tasks/999 404", service="api", status="error", error="not found")
hlog(level="ERROR", msg="POST /tasks 500", service="api", status="error", error="db timeout")

# --- Tracing (call in middleware after request completes) ---
htrace(
    trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), parent_id=None,
    name="GET /tasks", service="api",
    start=start_time.isoformat() + "Z", end=end_time.isoformat() + "Z",
    duration_ms=round((end_time - start_time).total_seconds() * 1000),
    status="ok"  # or "error" for 4xx/5xx
)
```

### Go

```go
package harness

import (
    "encoding/json"
    "os"
    "time"
)

func HLog(fields map[string]any) {
    fields["ts"] = time.Now().UTC().Format(time.RFC3339Nano)
    line, _ := json.Marshal(fields)
    f, _ := os.OpenFile(".harness/logs.jsonl", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    defer f.Close()
    f.Write(append(line, '\n'))
}

func HTrace(fields map[string]any) {
    line, _ := json.Marshal(fields)
    f, _ := os.OpenFile(".harness/traces.jsonl", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    defer f.Close()
    f.Write(append(line, '\n'))
}

// --- Logging ---
// harness.HLog(map[string]any{"level": "WARN", "msg": "GET /notes/999 404", "service": "api", "error": "not found"})

// --- Tracing (call in middleware after request completes) ---
// harness.HTrace(map[string]any{
//     "trace_id": traceID, "span_id": spanID, "parent_id": nil,
//     "name": "GET /notes", "service": "api",
//     "start": start.Format(time.RFC3339Nano), "end": end.Format(time.RFC3339Nano),
//     "duration_ms": end.Sub(start).Milliseconds(), "status": "ok",
// })
```

### C#

```csharp
using System.Text.Json;

public static class Harness
{
    private static readonly string LogPath = ".harness/logs.jsonl";
    private static readonly string TracePath = ".harness/traces.jsonl";

    static Harness() => Directory.CreateDirectory(".harness");

    // --- Logging (writes to .harness/logs.jsonl) ---
    public static void Log(string level, string msg, string service, Dictionary<string, object>? extra = null)
    {
        var entry = new Dictionary<string, object>
        {
            ["ts"] = DateTime.UtcNow.ToString("O"),
            ["level"] = level,
            ["msg"] = msg,
            ["service"] = service
        };
        if (extra != null) foreach (var kv in extra) entry[kv.Key] = kv.Value;
        File.AppendAllText(LogPath, JsonSerializer.Serialize(entry) + "\n");
    }

    // --- Tracing (writes to .harness/traces.jsonl) ---
    public static void Trace(string traceId, string name, string service,
        DateTime start, DateTime end, string status, Dictionary<string, object>? extra = null)
    {
        var entry = new Dictionary<string, object>
        {
            ["trace_id"] = traceId,
            ["span_id"] = Guid.NewGuid().ToString(),
            ["parent_id"] = null!,
            ["name"] = name,
            ["service"] = service,
            ["start"] = start.ToString("O"),
            ["end"] = end.ToString("O"),
            ["duration_ms"] = (end - start).TotalMilliseconds,
            ["status"] = status
        };
        if (extra != null) foreach (var kv in extra) entry[kv.Key] = kv.Value;
        File.AppendAllText(TracePath, JsonSerializer.Serialize(entry) + "\n");
    }
}

// --- In middleware, after the request completes: ---
// var traceId = Guid.NewGuid().ToString();
// var start = DateTime.UtcNow;
// await next(context);
// var end = DateTime.UtcNow;
// var status = context.Response.StatusCode < 400 ? "ok" : "error";
// Harness.Log(level, $"{method} {path} {statusCode}", "api", new() { ["trace_id"] = traceId, ["duration_ms"] = (end - start).TotalMilliseconds });
// Harness.Trace(traceId, $"{method} {path}", "api", start, end, status);
```

### Any Language

Append JSON lines to `.harness/logs.jsonl` (logs) and `.harness/traces.jsonl` (traces). That's it.

## Verify Script Integration

`make verify` should include an observability check:

```bash
# In scripts/harness/smoke.sh or verify script:
ERRORS=$(jq -s 'map(select(.level == "ERROR")) | length' .harness/logs.jsonl 2>/dev/null || echo 0)
if [ "$ERRORS" -gt 0 ]; then
  echo "⚠️  $ERRORS errors found in .harness/logs.jsonl"
  jq 'select(.level == "ERROR")' .harness/logs.jsonl | tail -5
fi
```

## Graduation: devtel (When You Outgrow JSONL)

When you need:
- Cross-signal joins (logs ↔ traces by trace_id)
- Aggregations (p95 latency, error rates)
- 100K+ events per session
- Auto-instrumentation (HTTP, DB, etc. without manual logging)

Upgrade to [devtel](https://github.com/bertclaws/devtel):

```bash
npm install devtel
npx devtel init

# Replace manual hlog() calls with:
# import "devtel/init";
# (auto-instruments everything via OpenTelemetry)

# Query with SQL instead of jq:
npx devtel logs --level error --last 5m
npx devtel traces --slow 500ms
npx devtel query "SELECT * FROM spans JOIN logs USING (trace_id)"
```

## Rules

- Keep field names stable — agents and scripts depend on them.
- Emit structured JSON, never unstructured text logs.
- Include trace_id on anything that crosses a boundary.
- `.harness/` is gitignored. Ephemeral by default.
- Redact secrets and PII.
