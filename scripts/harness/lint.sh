#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_LINT_CMD:-}" ]; then
  eval "$HARNESS_LINT_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend linting.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend linting.' >&2; exit 1; }

echo '==> Backend lint'
(
  cd "$root_dir/backend"
  uv run ruff check app/
)

echo '==> Frontend lint'
(
  cd "$root_dir/frontend"
  npm run lint:check
)
