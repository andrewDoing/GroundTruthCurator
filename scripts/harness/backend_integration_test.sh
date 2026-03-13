#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_BACKEND_INTEGRATION_TEST_CMD:-}" ]; then
  eval "$HARNESS_BACKEND_INTEGRATION_TEST_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend integration tests.' >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo 'ERROR: curl is required for backend integration tests.' >&2; exit 1; }

cosmos_ready_url="${HARNESS_COSMOS_READY_URL:-${GTC_COSMOS_ENDPOINT:-http://localhost:8081}}"

echo "==> Waiting for Cosmos emulator at ${cosmos_ready_url}"
for _ in $(seq 1 60); do
  if curl -sS --max-time 2 "$cosmos_ready_url" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -sS --max-time 2 "$cosmos_ready_url" >/dev/null 2>&1; then
  echo "ERROR: Cosmos emulator did not become ready at ${cosmos_ready_url}." >&2
  exit 1
fi

echo '==> Backend integration tests'
(
  cd "$root_dir/backend"
  GTC_LLM_ENABLED=False uv run pytest -q tests/integration -v --junitxml=pytest-int-results.xml
)
