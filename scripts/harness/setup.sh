#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_SETUP_CMD:-}" ]; then
  eval "$HARNESS_SETUP_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend setup.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend setup.' >&2; exit 1; }

mkdir -p "$root_dir/.harness"

echo '==> Syncing backend dependencies'
(
  cd "$root_dir/backend"
  uv sync --frozen
)

echo '==> Installing frontend dependencies'
(
  cd "$root_dir/frontend"
  if [ -f package-lock.json ]; then
    npm ci --no-audit --no-fund
  else
    npm install
  fi
)
