#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_TEST_CMD:-}" ]; then
  eval "$HARNESS_TEST_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend tests.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend tests.' >&2; exit 1; }

echo '==> Backend unit tests'
(
  cd "$root_dir/backend"
  GTC_LLM_ENABLED=False uv run pytest tests/unit/ -v
)

echo '==> Frontend unit tests'
(
  cd "$root_dir/frontend"
  npm run test:run -- --pool=threads --poolOptions.threads.singleThread
)
