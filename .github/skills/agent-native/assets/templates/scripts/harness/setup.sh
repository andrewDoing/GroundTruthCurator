#!/usr/bin/env bash
set -euo pipefail

# SETUP — Install project dependencies.
#
# Auto-detects the project type and installs deps.
# Customize or set HARNESS_SETUP_CMD.

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_SETUP_CMD:-}" ]; then
  eval "$HARNESS_SETUP_CMD"
  exit 0
fi

if [ -f "$root_dir/Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
  cargo fetch
  exit 0
fi

if [ -f "$root_dir/package.json" ] && command -v npm >/dev/null 2>&1; then
  npm install
  exit 0
fi

if [ -f "$root_dir/go.mod" ] && command -v go >/dev/null 2>&1; then
  go mod download
  exit 0
fi

if [ -f "$root_dir/pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv sync
    exit 0
  elif command -v pip >/dev/null 2>&1; then
    pip install -e .
    exit 0
  fi
fi

if ls "$root_dir"/*.csproj >/dev/null 2>&1 || ls "$root_dir"/*.sln >/dev/null 2>&1; then
  dotnet restore
  exit 0
fi

echo "ERROR: No project type detected."
echo "Set HARNESS_SETUP_CMD or customize scripts/harness/setup.sh"
exit 1
