#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_FORMAT_CMD:-}" ]; then
  eval "$HARNESS_FORMAT_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend formatting.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend formatting.' >&2; exit 1; }

echo '==> Formatting backend'
(
  cd "$root_dir/backend"
  uv run black app tests scripts
)

echo '==> Formatting frontend'
(
  cd "$root_dir/frontend"
  npm run lint
)
