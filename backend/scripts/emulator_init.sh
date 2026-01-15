#!/usr/bin/env bash

# Initialize the Cosmos DB Emulator schema for Ground Truth Curator.
#
# This script mirrors the CD workflow's Cosmos DB creation steps, but targets
# the local Cosmos DB Emulator (key auth + SSL verify disabled).
#
# It creates:
# - Database:                 $DB_NAME
# - Ground truth container:   $GT_CONTAINER   (HPK: /datasetName + /bucket, with indexing policy)
# - Assignments container:    $ASSIGNMENTS_CONTAINER (PK: /pk)
# - Tags container:           $TAGS_CONTAINER (PK: /pk)

set -euo pipefail

# Require bash (arrays and other features); avoid running under sh/dash
if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "This script requires bash. Run: bash $0 ..." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/../.." && pwd)"

DEFAULT_ENDPOINT="http://localhost:8081"
# Well-known Cosmos Emulator master key
DEFAULT_KEY="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
DEFAULT_INDEXING_POLICY="$SCRIPT_DIR/indexing-policy.json"

ENDPOINT="${COSMOS_EMULATOR_ENDPOINT:-$DEFAULT_ENDPOINT}"
KEY="${COSMOS_EMULATOR_KEY:-$DEFAULT_KEY}"
DB_NAME="${GTC_COSMOS_DB_NAME:-gt-curator}"
GT_CONTAINER="${GTC_COSMOS_CONTAINER_GT:-ground_truth}"
ASSIGNMENTS_CONTAINER="${GTC_COSMOS_CONTAINER_ASSIGNMENTS:-assignments}"
TAGS_CONTAINER="${GTC_COSMOS_CONTAINER_TAGS:-tags}"
INDEXING_POLICY_PATH="${GTC_COSMOS_DB_INDEXING_POLICY:-$DEFAULT_INDEXING_POLICY}"

DRY_RUN=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -e, --endpoint URL         Emulator endpoint (default: ${DEFAULT_ENDPOINT})
  -k, --key KEY              Emulator master key (default: well-known emulator key)
  -d, --db NAME              Database name (default: env GTC_COSMOS_DB_NAME or 'gt-curator')
      --gt-container NAME    Ground truth container name (default: env GTC_COSMOS_CONTAINER_GT or 'ground_truth')
      --assignments NAME     Assignments container name (default: env GTC_COSMOS_CONTAINER_ASSIGNMENTS or 'assignments')
      --tags NAME            Tags container name (default: env GTC_COSMOS_CONTAINER_TAGS or 'tags')
  -i, --indexing-policy PATH Indexing policy JSON for ground truth container
                             (default: scripts/indexing-policy.json)
      --dry-run              Print the command without running it
  -h, --help                 Show this help and exit

Environment variable shortcuts (override defaults):
  COSMOS_EMULATOR_ENDPOINT, COSMOS_EMULATOR_KEY,
  GTC_COSMOS_DB_NAME, GTC_COSMOS_CONTAINER_GT, GTC_COSMOS_CONTAINER_ASSIGNMENTS, GTC_COSMOS_CONTAINER_TAGS,
  GTC_COSMOS_DB_INDEXING_POLICY

Notes:
  - Requires Cosmos Emulator to be running and reachable at the endpoint.
  - Uses key-based auth and passes --no-verify (required for emulator TLS).
EOF
}

while ((${#})); do
  case "$1" in
    -e|--endpoint)
      ENDPOINT="$2"; shift 2 ;;
    -k|--key)
      KEY="$2"; shift 2 ;;
    -d|--db)
      DB_NAME="$2"; shift 2 ;;
    --gt-container)
      GT_CONTAINER="$2"; shift 2 ;;
    --assignments)
      ASSIGNMENTS_CONTAINER="$2"; shift 2 ;;
    --tags)
      TAGS_CONTAINER="$2"; shift 2 ;;
    -i|--indexing-policy)
      INDEXING_POLICY_PATH="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$DB_NAME" ]]; then
  echo "Error: database name is required (--db or GTC_COSMOS_DB_NAME)." >&2
  exit 2
fi

if [[ ! -f "$INDEXING_POLICY_PATH" ]]; then
  echo "Error: indexing policy file not found: $INDEXING_POLICY_PATH" >&2
  echo "Tip: expected at $DEFAULT_INDEXING_POLICY" >&2
  exit 1
fi

# Prefer uv if available (keeps dependencies aligned with backend/pyproject.toml)
RUNNER=()
if command -v uv >/dev/null 2>&1; then
  RUNNER=("uv" "run" "python")
elif command -v python3 >/dev/null 2>&1; then
  RUNNER=("python3")
elif command -v python >/dev/null 2>&1; then
  RUNNER=("python")
else
  echo "Error: couldn't find a Python interpreter (expected 'uv', 'python3', or 'python')." >&2
  exit 1
fi

CMD=(
  "${RUNNER[@]}"
  "$BACKEND_DIR/scripts/cosmos_container_manager.py"
  --endpoint "$ENDPOINT"
  --key "$KEY"
  --no-verify
  --db "$DB_NAME"
  --gt-container "$GT_CONTAINER"
  --assignments-container "$ASSIGNMENTS_CONTAINER"
  --tags-container "$TAGS_CONTAINER"
  --indexing-policy "$INDEXING_POLICY_PATH"
)

echo "Repo root:   $REPO_ROOT"
echo "Backend dir: $BACKEND_DIR"
echo "Endpoint:    $ENDPOINT"
echo "Database:    $DB_NAME"
echo "Containers:  GT=$GT_CONTAINER, assignments=$ASSIGNMENTS_CONTAINER, tags=$TAGS_CONTAINER"
echo "Indexing:    $INDEXING_POLICY_PATH"
echo

echo "Running:"
printf '  %q' "${CMD[@]}"
echo

if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry-run: not executing." 
  exit 0
fi

# Run from backend dir so relative imports/config match existing docs.
pushd "$BACKEND_DIR" >/dev/null
"${CMD[@]}"
popd >/dev/null
