#!/usr/bin/env bash
set -euo pipefail

# TEST — Run the project's test suite.
#
# Requirements:
#   - At least 5 meaningful tests covering core functionality (CRUD, error cases)
#   - Tests should verify real behavior, not just "assert True"
#   - Tests must be deterministic (no flaky network calls, no shared state leaks)
#
# Customize the detection below or set HARNESS_TEST_CMD.

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

if [ -n "${HARNESS_TEST_CMD:-}" ]; then
  eval "$HARNESS_TEST_CMD"
  exit 0
fi

if [ -f "$root_dir/Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
  cargo test --quiet
  exit 0
fi

if [ -f "$root_dir/package.json" ] && command -v npm >/dev/null 2>&1; then
  if node -e 'const p=require("./package.json"); process.exit(p.scripts&&p.scripts.test?0:1)' 2>/dev/null; then
    npm run -s test
    exit 0
  fi
fi

if [ -f "$root_dir/go.mod" ] && command -v go >/dev/null 2>&1; then
  go test ./...
  exit 0
fi

if [ -f "$root_dir/pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv run pytest -q
    exit 0
  elif command -v pytest >/dev/null 2>&1; then
    pytest -q
    exit 0
  fi
fi

if ls "$root_dir"/*.csproj >/dev/null 2>&1 || ls "$root_dir"/*.sln >/dev/null 2>&1; then
  dotnet test --verbosity quiet
  exit 0
fi

echo "ERROR: No test runner detected."
echo "Set HARNESS_TEST_CMD or customize scripts/harness/test.sh"
exit 1
