#!/usr/bin/env bash
set -euo pipefail

# FORMAT — Auto-format source code.
#
# Auto-detects the project type and runs the appropriate formatter.
# Customize or set HARNESS_FORMAT_CMD.

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_FORMAT_CMD:-}" ]; then
  eval "$HARNESS_FORMAT_CMD"
  exit 0
fi

if [ -f "$root_dir/Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
  cargo fmt
  exit 0
fi

if [ -f "$root_dir/package.json" ] && command -v npx >/dev/null 2>&1; then
  if npx prettier --version >/dev/null 2>&1; then
    npx prettier --write .
    exit 0
  elif npx biome --version >/dev/null 2>&1; then
    npx biome format --write .
    exit 0
  fi
fi

if [ -f "$root_dir/go.mod" ] && command -v gofmt >/dev/null 2>&1; then
  gofmt -w .
  exit 0
fi

if [ -f "$root_dir/pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1 && uv run ruff --version >/dev/null 2>&1; then
    uv run ruff format .
    exit 0
  elif command -v ruff >/dev/null 2>&1; then
    ruff format .
    exit 0
  elif command -v black >/dev/null 2>&1; then
    black .
    exit 0
  fi
fi

if ls "$root_dir"/*.csproj >/dev/null 2>&1 || ls "$root_dir"/*.sln >/dev/null 2>&1; then
  dotnet format
  exit 0
fi

echo "ERROR: No formatter detected."
echo "Set HARNESS_FORMAT_CMD or customize scripts/harness/format.sh"
exit 1
