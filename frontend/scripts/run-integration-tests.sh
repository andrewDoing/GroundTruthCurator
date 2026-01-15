#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}/.."
ENV_FILE="${FRONTEND_DIR}/.env.e2e.integration"
PYTHON_BIN="${E2E_PYTHON:-python3}"

cd "${FRONTEND_DIR}"

if [[ -f "${ENV_FILE}" ]]; then
	echo "[run-integration-tests] Loading ${ENV_FILE}" >&2
	set -a
	source "${ENV_FILE}"
	set +a
fi

COSMOS_ENDPOINT="${GTC_COSMOS_ENDPOINT:-https://localhost:8081/}"
CHECK_SCRIPT=$(cat <<'PY'
import socket
import sys
from urllib.parse import urlparse

endpoint = sys.argv[1]
parts = urlparse(endpoint)
host = parts.hostname or "localhost"
port = parts.port or (443 if parts.scheme == "https" else 80)
try:
    socket.create_connection((host, port), timeout=2.0)
except OSError as exc:
    print(f"Cosmos emulator not reachable at {host}:{port} ({exc})", file=sys.stderr)
    sys.exit(1)
PY
)

if ! "${PYTHON_BIN}" -c "${CHECK_SCRIPT}" "${COSMOS_ENDPOINT}"; then
	echo "[run-integration-tests] Cosmos emulator check failed" >&2
	exit 1
fi

echo "[run-integration-tests] Cosmos emulator online at ${COSMOS_ENDPOINT}" >&2

echo "[run-integration-tests] Running Playwright integration suite" >&2
npx playwright test --config=playwright.config.integration.ts "$@"
