#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_API_CHECK_CMD:-}" ]; then
  eval "$HARNESS_API_CHECK_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for API checks.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for API checks.' >&2; exit 1; }

echo '==> Exporting OpenAPI spec'
(
  cd "$root_dir/backend"
  uv run python scripts/export_openapi.py
)

echo '==> Checking committed OpenAPI spec'
git -C "$root_dir" --no-pager diff --exit-code -- frontend/src/api/openapi.json || {
  echo 'ERROR: OpenAPI spec is out of date. Run: cd backend && uv run python scripts/export_openapi.py' >&2
  exit 1
}

echo '==> Checking generated frontend API types'
(
  cd "$root_dir/frontend"
  npm run api:types:check
)
