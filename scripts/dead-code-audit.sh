#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
FRONTEND_DIR="${REPO_ROOT}/frontend"

ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

banner() {
  local message="$1"
  local border="============================================="
  echo
  echo "${border}"
  echo "${message}"
  echo "${border}"
}

run_backend_command() {
  local description="$1"
  shift
  banner "Backend · ${description}"
  (
    cd "${BACKEND_DIR}"
    echo "→ $*"
    "$@"
  )
}

run_frontend_command() {
  local description="$1"
  shift
  banner "Frontend · ${description}"
  (
    cd "${FRONTEND_DIR}"
    echo "→ $*"
    "$@"
  )
}

ensure_command uv
ensure_command npx

if [[ ! -d "${BACKEND_DIR}" || ! -d "${FRONTEND_DIR}" ]]; then
  echo "Run this script from the GroundTruthCurator repo (./scripts/dead-code-audit.sh)." >&2
  exit 1
fi

banner "GroundTruthCurator Dead-Code Audit (Detection Only)"
echo "Repo root: ${REPO_ROOT}"

echo "Running detection-only scans. No files will be modified."

run_backend_command "ruff (imports & locals)" \
  uv run ruff check app/ --select F401,F841,F811,ERA001,RUF059

run_backend_command "vulture (confidence ≥80)" \
  uv run vulture app/ --min-confidence 80 --sort-by-size

run_frontend_command "biome (unused imports)" \
  npx biome check src/

run_frontend_command "knip (unused exports/files/deps)" \
  npx knip

banner "Next Steps"
cat <<'EOF'
Tool Coverage Summary:
  - ruff: Unused imports (F401), unused variables (F841), redefined imports (F811)
  - vulture: Unused functions, classes, attributes (whole-program heuristic)
  - biome: Unused imports, code style violations
  - knip: Unused exports between modules, dead files, unused dependencies

Known Limitations:
  - Unused private functions within a file are not detected. Requires ESLint with config file.
  - Functions exported via public APIs (e.g., useGroundTruth return) are not flagged
  - Consider manual review or ESLint with @typescript-eslint/no-unused-vars for completeness

Next actions for addressing findings:
  - Backend safe fixes: (cd backend && uv run ruff check app/ --select F401,F811,RUF059 --fix)
  - Backend variable cleanup (unsafe): (cd backend && uv run ruff check app/ --select F401,F841,F811,RUF059 --fix --unsafe-fixes)
  - Backend whitelist refresh: (cd backend && uv run vulture app/ --make-whitelist > vulture_whitelist.py)
  - Frontend fixes: (cd frontend && npx biome check src/ --fix --unsafe)
  - Frontend unused export cleanup: (cd frontend && npx knip --fix --allow-remove-files)

Review diffs carefully before committing; the emulator and build pipelines rely on the intentional ignores configured during the audit.
EOF
