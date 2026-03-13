#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_TYPECHECK_CMD:-}" ]; then
  eval "$HARNESS_TYPECHECK_CMD"
  exit 0
fi

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend type checking.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend type checking.' >&2; exit 1; }

ty_output_format="${HARNESS_TY_OUTPUT_FORMAT:-concise}"

echo '==> Backend typecheck'
(
  cd "$root_dir/backend"
  uv run ty check app/ --output-format "$ty_output_format" --exclude app/adapters/inference/inference.py --force-exclude
)

echo '==> Frontend typecheck'
(
  cd "$root_dir/frontend"
  npm run typecheck
)
