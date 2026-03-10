#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bootstrap_harness.sh [repo_path] [--force]

Install harness templates into a target repository.

Arguments:
  repo_path   Target repository path (default: current directory)
  --force     Overwrite existing template-managed files
EOF
}

target_path="."
force=0

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      force=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ "$target_path" != "." ]; then
        echo "error: multiple repo paths provided" >&2
        usage
        exit 1
      fi
      target_path="$1"
      ;;
  esac
  shift
done

if [ ! -d "$target_path" ]; then
  echo "error: target path does not exist: $target_path" >&2
  exit 1
fi

target_path=$(cd "$target_path" && pwd)
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
skill_dir=$(cd "$script_dir/.." && pwd)
template_dir="$skill_dir/assets/templates"

if [ ! -d "$template_dir" ]; then
  echo "error: template directory missing: $template_dir" >&2
  exit 1
fi

copy_template() {
  local relative="$1"
  local source="$template_dir/$relative"
  local destination="$target_path/$relative"

  if [ ! -f "$source" ]; then
    echo "[error] missing template: $relative" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$destination")"

  if [ -f "$destination" ] && [ "$force" -ne 1 ]; then
    echo "[skip]  $relative (exists)"
    return 0
  fi

  cp "$source" "$destination"
  echo "[write] $relative"
}

templates=(
  "AGENTS.md"
  "PLANS.md"
  "docs/ARCHITECTURE.md"
  "docs/OBSERVABILITY.md"
  "Makefile.harness"
  "scripts/audit_harness.sh"
  "scripts/verify_customized.sh"
  "scripts/harness/setup.sh"
  "scripts/harness/format.sh"
  "scripts/harness/smoke.sh"
  "scripts/harness/test.sh"
  "scripts/harness/lint.sh"
  "scripts/harness/typecheck.sh"
  ".github/workflows/harness.yml"
)

for relative in "${templates[@]}"; do
  copy_template "$relative"
done

makefile="$target_path/Makefile"
if [ ! -f "$makefile" ]; then
  cat > "$makefile" <<'EOF'
-include Makefile.harness
EOF
  echo "[write] Makefile"
elif ! grep -Eq '(^|[[:space:]])-?include[[:space:]]+Makefile\.harness([[:space:]]|$)' "$makefile"; then
  cat >> "$makefile" <<'EOF'

# Harness engineering targets
-include Makefile.harness
EOF
  echo "[update] Makefile (+ include Makefile.harness)"
else
  echo "[skip]  Makefile already includes Makefile.harness"
fi

chmod +x \
  "$target_path/scripts/audit_harness.sh" \
  "$target_path/scripts/verify_customized.sh" \
  "$target_path/scripts/harness/setup.sh" \
  "$target_path/scripts/harness/format.sh" \
  "$target_path/scripts/harness/smoke.sh" \
  "$target_path/scripts/harness/test.sh" \
  "$target_path/scripts/harness/lint.sh" \
  "$target_path/scripts/harness/typecheck.sh"

# Create .harness/ observability directory and jq query library
mkdir -p "$target_path/.harness/queries"

# Seed empty JSONL files
for f in logs.jsonl traces.jsonl metrics.jsonl; do
  touch "$target_path/.harness/$f"
done

# Write jq query library
cat > "$target_path/.harness/queries/errors.jq" <<'JQ'
# Recent errors
select(.level == "ERROR")
JQ

cat > "$target_path/.harness/queries/problems.jq" <<'JQ'
# All problems (4xx warnings + 5xx errors)
select(.level == "ERROR" or .level == "WARN")
JQ

cat > "$target_path/.harness/queries/slow.jq" <<'JQ'
# Slow requests — usage: jq --argjson threshold 500 -f slow.jq traces.jsonl
select(.duration_ms > $threshold)
JQ

cat > "$target_path/.harness/queries/trace.jq" <<'JQ'
# All events for a trace — usage: jq --arg tid <id> -f trace.jq logs.jsonl traces.jsonl
select(.trace_id == $tid)
JQ

cat > "$target_path/.harness/queries/summary.jq" <<'JQ'
# Error summary by service
[.] | group_by(.service) | map({service: .[0].service, count: length})
JQ

echo "[write] .harness/ (observability: JSONL files + jq query library)"

# Add .harness/ to .gitignore if not already there
gitignore="$target_path/.gitignore"
if [ -f "$gitignore" ]; then
  if ! grep -qF '.harness/' "$gitignore"; then
    echo '.harness/' >> "$gitignore"
    echo "[update] .gitignore (+ .harness/)"
  fi
else
  echo '.harness/' > "$gitignore"
  echo "[write] .gitignore"
fi

echo
echo "Bootstrap complete."
echo "Next:"
echo "  1) Read AGENTS.md — it tells you what to customize and what conventions to follow"
echo "  2) Read docs/OBSERVABILITY.md — follow the Level Policy (2xx=INFO, 4xx=WARN, 5xx=ERROR)"
echo "  3) Customize docs/ARCHITECTURE.md — replace ALL placeholders with real project info"
echo "  4) Fill in scripts/harness/*.sh with real project commands"
echo "  5) Add hlog() calls to your app (see language examples in docs/OBSERVABILITY.md)"
echo "  6) Verify: make -f Makefile.harness ci"
echo "  7) Verify customization: scripts/verify_customized.sh ."
echo "  8) Audit: scripts/audit_harness.sh ."
