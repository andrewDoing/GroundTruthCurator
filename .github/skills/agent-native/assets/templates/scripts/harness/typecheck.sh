#!/usr/bin/env bash
set -euo pipefail

# TYPECHECK — Run the type checker / compiler verification.
#
# Must exit non-zero on type errors (treat type failures as blocking).
# For compiled languages (Go, C#, Rust), this is the build step.
#
# Customize or set HARNESS_TYPECHECK_CMD.

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_TYPECHECK_CMD:-}" ]; then
  eval "$HARNESS_TYPECHECK_CMD"
  exit 0
fi

if [ -f "$root_dir/Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
  cargo check --quiet
  exit 0
fi

if [ -f "$root_dir/package.json" ] && command -v npm >/dev/null 2>&1; then
  if node -e 'const p=require("./package.json"); process.exit(p.scripts&&p.scripts.typecheck?0:1)' 2>/dev/null; then
    npm run -s typecheck
    exit 0
  fi
  # Fallback: direct tsc
  if command -v npx >/dev/null 2>&1 && [ -f "$root_dir/tsconfig.json" ]; then
    npx tsc --noEmit
    exit 0
  fi
fi

if [ -f "$root_dir/go.mod" ] && command -v go >/dev/null 2>&1; then
  go vet ./...
  exit 0
fi

if [ -f "$root_dir/pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1 && uv run mypy --version >/dev/null 2>&1; then
    uv run mypy .
    exit 0
  elif command -v mypy >/dev/null 2>&1; then
    mypy .
    exit 0
  elif command -v pyright >/dev/null 2>&1; then
    pyright
    exit 0
  fi
fi

if ls "$root_dir"/*.csproj >/dev/null 2>&1 || ls "$root_dir"/*.sln >/dev/null 2>&1; then
  dotnet build --nologo --verbosity quiet
  exit 0
fi

echo "ERROR: No type checker detected."
echo "Set HARNESS_TYPECHECK_CMD or customize scripts/harness/typecheck.sh"
exit 1
