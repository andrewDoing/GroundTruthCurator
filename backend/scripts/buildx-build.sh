#!/usr/bin/env bash

# Build and optionally push the multi-stage backend image using docker buildx.
#
# Defaults:
# - Dockerfile: backend/Dockerfile
# - Context:    . (repo root that contains frontend/ and backend/)
# - Image:      gtc-backend:latest
# - Platforms:  linux/amd64 (override with -p for multi-arch)
# - Output:     --load (local image) unless --push is specified
#
# Examples:
#   # Local test build for amd64
#   backend/scripts/buildx-build.sh -t dev --load
#
#   # Push multi-arch to Docker Hub
#   backend/scripts/buildx-build.sh -i gtc-backend -t 1.0.0 -p linux/amd64,linux/arm64 \
#     --push -r yourdockerhubuser
#
#   # Push multi-arch to Azure Container Registry
#   backend/scripts/buildx-build.sh -i gtc-backend -t 1.0.0 -p linux/amd64,linux/arm64 \
#     --push -r myregistry.azurecr.io

set -euo pipefail

# Require bash (arrays and other features); avoid running under sh/dash
if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "This script requires bash. Run: bash $0 ..." >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Project root is two levels up from backend/scripts
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
# Try to detect repo root via git; fallback to PROJECT_ROOT
if REPO_ROOT=$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel 2>/dev/null); then
  :
else
  REPO_ROOT="${PROJECT_ROOT}"
fi

IMAGE_NAME="gtc-backend"
TAG="latest"
PLATFORMS="linux/amd64"
DOCKERFILE=""
CONTEXT=""
PUSH="false"
LOAD="true"   # default to local load unless --push given
BUILDER="gtc-builder"
REGISTRY=""
DEBUG="0"
NO_CACHE=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -i, --image <name>         Image name (default: ${IMAGE_NAME})
  -t, --tag <tag>            Image tag (default: ${TAG})
  -r, --registry <prefix>    Registry prefix (e.g., youruser or myreg.azurecr.io)
  -p, --platforms <list>     Target platforms (default: ${PLATFORMS})
  -f, --file <Dockerfile>    Dockerfile path (default: auto-detected)
  -c, --context <dir>        Build context (default: auto-detected)
      --push                 Push image to registry (disables --load)
      --load                 Load image into local docker (default if --push not set)
      --builder <name>       Buildx builder name (default: ${BUILDER})
      --build-arg KEY=VAL    Pass build arg (can be repeated)
      --no-cache             Disable build cache
      --debug                Enable verbose execution
  -h, --help                 Show this help

Examples:
  backend/scripts/buildx-build.sh -i gtc-backend -t dev --load
  backend/scripts/buildx-build.sh -r yourdockerhubuser -i gtc-backend -t 1.0.0 -p linux/amd64,linux/arm64 --push
  backend/scripts/buildx-build.sh -r myregistry.azurecr.io -i gtc-backend -t 1.0.0 -p linux/amd64,linux/arm64 --push
EOF
}

while ((${#})); do
  case "$1" in
    -i|--image)
      IMAGE_NAME="$2"; shift 2 ;;
    -t|--tag)
      TAG="$2"; shift 2 ;;
    -r|--registry)
      REGISTRY="$2"; shift 2 ;;
    -p|--platforms)
      PLATFORMS="$2"; shift 2 ;;
    -f|--file)
      DOCKERFILE="$2"; shift 2 ;;
    -c|--context)
      CONTEXT="$2"; shift 2 ;;
    --push)
      PUSH="true"; LOAD="false"; shift ;;
    --load)
      LOAD="true"; PUSH="false"; shift ;;
    --builder)
      BUILDER="$2"; shift 2 ;;
    --no-cache)
      NO_CACHE="--no-cache"; shift ;;
    --debug)
      DEBUG="1"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage; exit 1 ;;
  esac
done

if [[ "${DEBUG}" == "1" ]]; then
  set -x
fi

###############################################
# Auto-detect Dockerfile and build context
###############################################
# 1) If user provided -f or -c, respect those. Otherwise, try common layouts.
if [[ -z "${DOCKERFILE}" ]]; then
  # Prefer project root (GroundTruthCurator) layout: <project>/backend/Dockerfile
  if [[ -f "${PROJECT_ROOT}/backend/Dockerfile" ]]; then
    DOCKERFILE="${PROJECT_ROOT}/backend/Dockerfile"
    CONTEXT="${PROJECT_ROOT}"
  # Fallback: repo root layout when project is nested: <repo>/GroundTruthCurator/backend/Dockerfile
  elif [[ -f "${REPO_ROOT}/GroundTruthCurator/backend/Dockerfile" ]]; then
    DOCKERFILE="${REPO_ROOT}/GroundTruthCurator/backend/Dockerfile"
    CONTEXT="${REPO_ROOT}"
  fi
fi

# If context still empty, derive it from Dockerfile location
if [[ -n "${DOCKERFILE}" && -z "${CONTEXT}" ]]; then
  # If Dockerfile ends with /backend/Dockerfile, use its parent directory's parent as context
  DF_DIR=$(cd "$(dirname "${DOCKERFILE}")" && pwd)
  if [[ -d "${DF_DIR}/.." ]]; then
    CONTEXT=$(cd "${DF_DIR}/.." && pwd)
  fi
fi

# Final validation
if [[ -z "${DOCKERFILE}" || ! -f "${DOCKERFILE}" ]]; then
  echo "Error: Could not locate Dockerfile automatically. Try passing -f <path> and -c <context>." >&2
  exit 1
fi
if [[ -z "${CONTEXT}" || ! -d "${CONTEXT}" ]]; then
  echo "Error: Build context directory not found. Try passing -c <context>." >&2
  exit 1
fi

# Validate expected folders relative to context
if grep -q "COPY frontend" "${DOCKERFILE}" && [[ ! -d "${CONTEXT}/frontend" ]]; then
  echo "Error: frontend/ directory not found under context ${CONTEXT}, but Dockerfile expects it." >&2
  exit 1
fi
if [[ ! -d "${CONTEXT}/backend" ]]; then
  echo "Error: backend/ directory not found under context ${CONTEXT}." >&2
  exit 1
fi

if [[ "${PUSH}" == "true" && "${LOAD}" == "true" ]]; then
  echo "Error: --push and --load are mutually exclusive." >&2
  exit 1
fi

FULL_IMAGE="${IMAGE_NAME}:${TAG}"
if [[ -n "${REGISTRY}" ]]; then
  # allow passing either a login server (e.g., foo.azurecr.io) or a Docker Hub user/org
  REG_TRIMMED="${REGISTRY%/}"
  FULL_IMAGE="${REG_TRIMMED}/${IMAGE_NAME}:${TAG}"
fi

# Create/use a buildx builder
if ! docker buildx inspect "${BUILDER}" >/dev/null 2>&1; then
  docker buildx create --name "${BUILDER}" --use >/dev/null
else
  docker buildx use "${BUILDER}" >/dev/null
fi

# Determine output mode
OUTPUT_FLAG=("--load")
if [[ "${PUSH}" == "true" ]]; then
  OUTPUT_FLAG=("--push")
fi

# If loading locally, buildx can only load a single platform into the docker image store
PLATFORM_ARG=("--platform" "${PLATFORMS}")
if [[ "${OUTPUT_FLAG[*]}" == "--load" && "${PLATFORMS}" == *,* ]]; then
  echo "Warning: --load supports a single platform. Using the first from: ${PLATFORMS}" >&2
  PLATFORM_ARG=("--platform" "${PLATFORMS%%,*}")
fi

# Labels for traceability
CREATED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
REVISION=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || true)
LABELS=(
  "--label" "org.opencontainers.image.created=${CREATED}"
)
if [[ -n "${REVISION}" ]]; then
  LABELS+=("--label" "org.opencontainers.image.revision=${REVISION}")
fi

echo "Building ${FULL_IMAGE} with platforms ${PLATFORM_ARG[1]} using ${DOCKERFILE} (context: ${CONTEXT})"

set -o pipefail
docker buildx build \
  "${PLATFORM_ARG[@]}" \
  -f "${DOCKERFILE}" \
  -t "${FULL_IMAGE}" \
  ${NO_CACHE} \
  "${LABELS[@]}" \
  "${OUTPUT_FLAG[@]}" \
  "${CONTEXT}"

echo
if [[ "${PUSH}" == "true" ]]; then
  echo "Pushed: ${FULL_IMAGE}"
else
  echo "Loaded locally: ${FULL_IMAGE}"
fi
