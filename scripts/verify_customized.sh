#!/usr/bin/env bash
set -euo pipefail

# VERIFY CUSTOMIZED — Checks that template boilerplate has been replaced.
#
# Run after setting up harness engineering to catch leftover placeholders.
# Exit code 0 = all customized, 1 = boilerplate detected.

target_path="${1:-.}"
target_path=$(cd "$target_path" && pwd)

failures=0
total=0

pass() {
  total=$((total + 1))
  echo "  ✅ $1"
}

fail() {
  total=$((total + 1))
  failures=$((failures + 1))
  echo "  ❌ $1"
}

check_no_placeholders() {
  local file="$1"
  local label="$2"
  local full="$target_path/$file"

  if [ ! -f "$full" ]; then
    fail "$label — file missing"
    return
  fi

  if grep -qE '<project-name>|<runtime>|<entrypoints>|_Replace:|_Replace_' "$full"; then
    fail "$label — still contains template placeholders"
    echo "       $(grep -nE '<project-name>|<runtime>|<entrypoints>|_Replace:|_Replace_' "$full" | head -3)"
    return
  fi

  pass "$label"
}

check_not_empty_template() {
  local file="$1"
  local label="$2"
  local min_lines="${3:-10}"
  local full="$target_path/$file"

  if [ ! -f "$full" ]; then
    fail "$label — file missing"
    return
  fi

  local lines
  lines=$(wc -l < "$full" | tr -d ' ')
  if [ "$lines" -lt "$min_lines" ]; then
    fail "$label — only $lines lines (expected >=$min_lines, likely not customized)"
    return
  fi

  pass "$label ($lines lines)"
}

check_plans_customized() {
  local full="$target_path/PLANS.md"

  if [ ! -f "$full" ]; then
    fail "PLANS.md — file missing"
    return
  fi

  local placeholder_count
  placeholder_count=$(grep -cE '^\s*-\s*\[ \]|<describe|<list|_TBD_|_TODO_' "$full" 2>/dev/null || true)
  placeholder_count="${placeholder_count:-0}"
  placeholder_count=$(echo "$placeholder_count" | tr -d '[:space:]')
  local total_lines
  total_lines=$(wc -l < "$full" | tr -d ' ')

  if [ "$placeholder_count" -gt 3 ] && [ "$total_lines" -lt 30 ]; then
    fail "PLANS.md — appears to be raw template ($placeholder_count placeholders in $total_lines lines)"
    return
  fi

  pass "PLANS.md customized"
}

check_smoke_is_real() {
  local full="$target_path/scripts/harness/smoke.sh"

  if [ ! -f "$full" ]; then
    fail "smoke.sh — file missing"
    return
  fi

  if grep -qE 'curl|wget|health|localhost|127\.0\.0\.1|uvicorn|openapi' "$full"; then
    pass "smoke.sh — contains server lifecycle logic"
  else
    fail "smoke.sh — no server start/health check detected (might be a build-only stub)"
  fi
}

check_tests_exist() {
  local test_count=0

  test_count=$((test_count + $(find "$target_path/backend" -name 'test_*.py' -o -name '*_test.py' 2>/dev/null | wc -l | tr -d ' ')))
  test_count=$((test_count + $(find "$target_path/frontend" -name '*.test.ts' -o -name '*.spec.ts' -o -name '*.test.js' -o -name '*.spec.js' 2>/dev/null | wc -l | tr -d ' ')))
  test_count=$((test_count + $(find "$target_path" -name '*_test.go' 2>/dev/null | wc -l | tr -d ' ')))
  test_count=$((test_count + $(find "$target_path" -name '*Test*.cs' -o -name '*Tests*.cs' 2>/dev/null | wc -l | tr -d ' ')))

  if [ "$test_count" -gt 0 ]; then
    pass "Test files found ($test_count files)"
  else
    fail "No test files found"
  fi
}

check_observability_wired() {
  local hits=0

  if [ -d "$target_path/backend/app" ]; then
    hits=$(grep -rlE 'GTC_HARNESS_JSONL_ENABLED|\.harness/logs|\.harness/traces|trace_id|duration_ms' "$target_path/backend/app"               --include='*.py' 2>/dev/null | wc -l | tr -d ' ')
  fi

  if [ "$hits" -gt 0 ]; then
    pass "Observability wired in application source ($hits files)"
  else
    fail "No harness JSONL observability wiring found in application source"
  fi
}

echo "🔍 Verifying harness customization in: $target_path"
echo ""

echo "📄 Template Placeholders:"
check_no_placeholders "AGENTS.md" "AGENTS.md"
check_no_placeholders "docs/ARCHITECTURE.md" "docs/ARCHITECTURE.md"
check_no_placeholders "docs/OBSERVABILITY.md" "docs/OBSERVABILITY.md"
echo ""

echo "📋 Content Depth:"
check_not_empty_template "AGENTS.md" "AGENTS.md" 15
check_not_empty_template "docs/ARCHITECTURE.md" "docs/ARCHITECTURE.md" 20
check_not_empty_template "docs/OBSERVABILITY.md" "docs/OBSERVABILITY.md" 15
check_plans_customized
echo ""

echo "🔧 Harness Scripts:"
check_smoke_is_real
check_tests_exist
echo ""

echo "📊 Observability:"
check_observability_wired
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$failures" -gt 0 ]; then
  echo "❌ Verification failed: $failures/$total checks failed."
  echo "   Fix the issues above before considering the harness complete."
  exit 1
fi

echo "✅ All $total checks passed — harness is customized and wired."
