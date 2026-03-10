#!/usr/bin/env bash
set -euo pipefail

# LINT — Run static analysis / linting.
#
# This catches style violations, unused imports, and common bugs.
# Must exit non-zero on any violation (treat lint failures as blocking).
#
# Customize or set HARNESS_LINT_CMD.

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_LINT_CMD:-}" ]; then
  eval "$HARNESS_LINT_CMD"
  exit 0
fi

if [ -f "$root_dir/Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
  cargo clippy --all-targets --all-features -- -D warnings
  exit 0
fi

if [ -f "$root_dir/package.json" ] && command -v npm >/dev/null 2>&1; then
  if node -e 'const p=require("./package.json"); process.exit(p.scripts&&p.scripts.lint?0:1)' 2>/dev/null; then
    npm run -s lint
    exit 0
  fi
fi

if [ -f "$root_dir/go.mod" ] && command -v go >/dev/null 2>&1; then
  go vet ./...
  if command -v golangci-lint >/dev/null 2>&1; then
    golangci-lint run
  fi
  exit 0
fi

if [ -f "$root_dir/pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1 && uv run ruff --version >/dev/null 2>&1; then
    uv run ruff check .
    uv run ruff format --check .
    exit 0
  elif command -v ruff >/dev/null 2>&1; then
    ruff check .
    ruff format --check .
    exit 0
  fi
fi

if ls "$root_dir"/*.csproj >/dev/null 2>&1 || ls "$root_dir"/*.sln >/dev/null 2>&1; then
  dotnet format --verify-no-changes
  exit 0
fi

echo "ERROR: No linter detected."
echo "Set HARNESS_LINT_CMD or customize scripts/harness/lint.sh"
exit 1
