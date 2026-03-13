#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

PORT="${HARNESS_SMOKE_PORT:-8008}"
HEALTH_URL="${HARNESS_SMOKE_HEALTH_URL:-http://127.0.0.1:${PORT}/healthz}"
OPENAPI_URL="${HARNESS_SMOKE_URL:-http://127.0.0.1:${PORT}/v1/openapi.json}"
SERVER_LOG="$root_dir/.harness/smoke-server.log"

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend smoke tests.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend smoke tests.' >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo 'ERROR: curl is required for smoke tests.' >&2; exit 1; }

mkdir -p "$root_dir/.harness"
: > "$root_dir/.harness/logs.jsonl"
: > "$root_dir/.harness/traces.jsonl"
: > "$SERVER_LOG"

SERVER_PID=''
cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo '==> Starting backend smoke server'
(
  cd "$root_dir/backend"
  env \
    GTC_AZ_MONITOR_ENABLED=false \
    GTC_HARNESS_JSONL_ENABLED=true \
    uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
) >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

echo "==> Waiting for $HEALTH_URL"
for _ in $(seq 1 20); do
  if curl -fsS "$HEALTH_URL" >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl -fsS "$HEALTH_URL" >/dev/null; then
  echo 'ERROR: backend health probe failed.' >&2
  tail -50 "$SERVER_LOG" >&2 || true
  exit 1
fi

echo "==> Probing $OPENAPI_URL"
curl -fsS "$OPENAPI_URL" >/dev/null

echo '==> Building frontend bundle'
(
  cd "$root_dir/frontend"
  npm run build
)

if [ ! -s "$root_dir/.harness/logs.jsonl" ]; then
  echo 'ERROR: smoke run did not emit .harness/logs.jsonl entries.' >&2
  exit 1
fi

if [ ! -s "$root_dir/.harness/traces.jsonl" ]; then
  echo 'ERROR: smoke run did not emit .harness/traces.jsonl entries.' >&2
  exit 1
fi

echo 'Smoke test passed ✅'
