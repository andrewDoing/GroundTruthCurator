#!/usr/bin/env bash
set -euo pipefail

# SMOKE TEST — Verify the app starts, responds, and shuts down cleanly.
#
# Supports three modes via HARNESS_SMOKE_MODE:
#   server   — start an HTTP server, poll health, hit a smoke endpoint (default for web apps)
#   cli      — run the CLI tool with --help/--version and check exit code
#   library  — run a basic import/require check
#   auto     — auto-detect which mode to use
#
# See docs/OBSERVABILITY.md for the logging convention.

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

SMOKE_MODE="${HARNESS_SMOKE_MODE:-auto}"

# ─── AUTO-DETECT MODE ──────────────────────────────────────────────
detect_mode() {
  # Check for server indicators
  if [ -f "$root_dir/pyproject.toml" ]; then
    if grep -qE "uvicorn|fastapi|flask|django|gunicorn|starlette" "$root_dir/pyproject.toml" 2>/dev/null; then
      echo "server"; return
    fi
    if grep -qE "argparse|click|typer|fire" "$root_dir/pyproject.toml" 2>/dev/null; then
      echo "cli"; return
    fi
  fi
  if [ -f "$root_dir/package.json" ]; then
    if grep -qE '"express"|"fastify"|"koa"|"hapi"|"next"|"nuxt"' "$root_dir/package.json" 2>/dev/null; then
      echo "server"; return
    fi
    if grep -qE '"commander"|"yargs"|"meow"|"inquirer"' "$root_dir/package.json" 2>/dev/null; then
      echo "cli"; return
    fi
    # Has a "start" script → likely server
    if node -e 'const p=require("./package.json"); process.exit(p.scripts&&p.scripts.start?0:1)' 2>/dev/null; then
      echo "server"; return
    fi
  fi
  if [ -f "$root_dir/go.mod" ]; then
    if grep -rqE "net/http|gin|echo|fiber|chi" "$root_dir"/*.go "$root_dir"/cmd/ "$root_dir"/internal/ 2>/dev/null; then
      echo "server"; return
    fi
    if grep -rqE "cobra|urfave/cli|kong" "$root_dir"/*.go "$root_dir"/cmd/ "$root_dir"/internal/ 2>/dev/null; then
      echo "cli"; return
    fi
    # Has a main.go in root → likely CLI
    if [ -f "$root_dir/main.go" ]; then
      echo "cli"; return
    fi
  fi
  if [ -f "$root_dir/Cargo.toml" ]; then
    if grep -qE "actix|axum|rocket|warp|hyper" "$root_dir/Cargo.toml" 2>/dev/null; then
      echo "server"; return
    fi
    if grep -qE "clap|structopt" "$root_dir/Cargo.toml" 2>/dev/null; then
      echo "cli"; return
    fi
    # Has [[bin]] → likely CLI
    if grep -q '\[\[bin\]\]' "$root_dir/Cargo.toml" 2>/dev/null; then
      echo "cli"; return
    fi
  fi
  if ls "$root_dir"/*.csproj >/dev/null 2>&1; then
    if grep -qE "Microsoft\.AspNetCore|Kestrel" "$root_dir"/*.csproj 2>/dev/null; then
      echo "server"; return
    fi
    echo "cli"; return
  fi
  # Default: library (no server or CLI indicators found)
  echo "library"
}

if [ "$SMOKE_MODE" = "auto" ]; then
  SMOKE_MODE=$(detect_mode)
  echo "Auto-detected smoke mode: $SMOKE_MODE"
fi

# ─── LIBRARY MODE ──────────────────────────────────────────────────
smoke_library() {
  echo "Running library import check..."
  if [ -f "$root_dir/pyproject.toml" ]; then
    # Extract package name from pyproject.toml
    local pkg
    pkg=$(grep -E '^\s*name\s*=' "$root_dir/pyproject.toml" | head -1 | sed 's/.*=\s*["'"'"']\([^"'"'"']*\)["'"'"'].*/\1/' | tr '-' '_')
    if [ -n "$pkg" ]; then
      if command -v uv >/dev/null 2>&1; then
        uv run python -c "import $pkg; print('Import OK:', $pkg.__name__ if hasattr($pkg, '__name__') else '$pkg')"
      else
        python -c "import $pkg; print('Import OK:', $pkg.__name__ if hasattr($pkg, '__name__') else '$pkg')"
      fi
      echo "Library smoke test passed ✅"
      return 0
    fi
  fi
  if [ -f "$root_dir/package.json" ]; then
    local pkg
    pkg=$(node -e 'console.log(require("./package.json").name || "")' 2>/dev/null)
    if [ -n "$pkg" ]; then
      node -e "require('$pkg'); console.log('Import OK: $pkg')" 2>/dev/null || \
        node -e "require('.'); console.log('Import OK: $pkg')"
      echo "Library smoke test passed ✅"
      return 0
    fi
  fi
  if [ -f "$root_dir/Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
    cargo build --quiet
    echo "Library smoke test passed ✅ (cargo build succeeded)"
    return 0
  fi
  if [ -f "$root_dir/go.mod" ] && command -v go >/dev/null 2>&1; then
    go build ./...
    echo "Library smoke test passed ✅ (go build succeeded)"
    return 0
  fi
  echo "ERROR: Cannot determine library import check."
  echo "Set HARNESS_SMOKE_MODE=server or HARNESS_SMOKE_MODE=cli, or customize scripts/harness/smoke.sh"
  exit 1
}

# ─── CLI MODE ──────────────────────────────────────────────────────
smoke_cli() {
  local cli_cmd="${HARNESS_SMOKE_CLI_CMD:-}"

  if [ -z "$cli_cmd" ]; then
    # Auto-detect CLI command
    if [ -f "$root_dir/pyproject.toml" ]; then
      # Look for [project.scripts] entries
      local entry
      entry=$(grep -A5 '\[project\.scripts\]' "$root_dir/pyproject.toml" 2>/dev/null | grep -E '^\s*\w+\s*=' | head -1 | sed 's/\s*=.*//' | tr -d ' ')
      if [ -n "$entry" ]; then
        if command -v uv >/dev/null 2>&1; then
          cli_cmd="uv run $entry"
        else
          cli_cmd="$entry"
        fi
      fi
    fi
    if [ -z "$cli_cmd" ] && [ -f "$root_dir/package.json" ]; then
      local bin
      bin=$(node -e 'const p=require("./package.json"); const b=p.bin; if(typeof b==="string"){console.log(p.name)}else if(b){console.log(Object.keys(b)[0])}' 2>/dev/null)
      if [ -n "$bin" ]; then
        cli_cmd="npx $bin"
      fi
    fi
    if [ -z "$cli_cmd" ] && [ -f "$root_dir/go.mod" ]; then
      cli_cmd="go run ."
    fi
    if [ -z "$cli_cmd" ] && [ -f "$root_dir/Cargo.toml" ]; then
      cli_cmd="cargo run --quiet --"
    fi
  fi

  if [ -z "$cli_cmd" ]; then
    echo "ERROR: Cannot detect CLI command."
    echo "Set HARNESS_SMOKE_CLI_CMD or customize scripts/harness/smoke.sh"
    exit 1
  fi

  echo "Running CLI smoke: $cli_cmd --help"
  if $cli_cmd --help >/dev/null 2>&1; then
    echo "CLI smoke test passed ✅ (--help exited 0)"
    return 0
  fi

  echo "Trying: $cli_cmd --version"
  if $cli_cmd --version >/dev/null 2>&1; then
    echo "CLI smoke test passed ✅ (--version exited 0)"
    return 0
  fi

  echo "ERROR: CLI smoke failed ($cli_cmd --help and --version both failed)"
  exit 1
}

# ─── SERVER MODE ───────────────────────────────────────────────────
smoke_server() {
  # ─── CUSTOMIZE THESE ───────────────────────────────────────────────
  START_CMD="${HARNESS_SMOKE_START_CMD:-}"
  HEALTH_URL="${HARNESS_SMOKE_HEALTH_URL:-http://localhost:8080/health}"
  SMOKE_URL="${HARNESS_SMOKE_URL:-http://localhost:8080/}"
  PORT="${HARNESS_SMOKE_PORT:-8080}"
  READY_TIMEOUT=15

  # ─── AUTO-DETECT START COMMAND (if not set) ────────────────────────
  if [ -z "$START_CMD" ]; then
    if [ -f "$root_dir/pyproject.toml" ]; then
      if grep -q "uvicorn" "$root_dir/pyproject.toml" 2>/dev/null; then
        START_CMD="uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
      elif grep -q "fastapi" "$root_dir/pyproject.toml" 2>/dev/null; then
        START_CMD="uv run fastapi run --port $PORT"
      fi
    elif [ -f "$root_dir/package.json" ]; then
      if node -e 'const p=require("./package.json"); process.exit(p.scripts&&p.scripts.start?0:1)' 2>/dev/null; then
        START_CMD="npm run -s start"
      fi
    elif [ -f "$root_dir/go.mod" ]; then
      START_CMD="go run ."
    elif ls "$root_dir"/*.csproj >/dev/null 2>&1; then
      START_CMD="dotnet run --urls http://0.0.0.0:$PORT"
    fi
  fi

  if [ -z "$START_CMD" ]; then
    echo "ERROR: Cannot detect start command."
    echo "Set HARNESS_SMOKE_START_CMD or customize scripts/harness/smoke.sh"
    exit 1
  fi

  # ─── CLEANUP TRAP ──────────────────────────────────────────────────
  SERVER_PID=""
  cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
      kill "$SERVER_PID" 2>/dev/null || true
      wait "$SERVER_PID" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT

  # ─── START SERVER ──────────────────────────────────────────────────
  echo "Starting server: $START_CMD"
  $START_CMD &
  SERVER_PID=$!

  # ─── WAIT FOR READY ───────────────────────────────────────────────
  echo "Waiting for server on $HEALTH_URL (timeout: ${READY_TIMEOUT}s)..."
  elapsed=0
  while [ "$elapsed" -lt "$READY_TIMEOUT" ]; do
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
      echo "Server ready after ${elapsed}s"
      break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  if [ "$elapsed" -ge "$READY_TIMEOUT" ]; then
    echo "ERROR: Server did not become ready within ${READY_TIMEOUT}s"
    exit 1
  fi

  # ─── SMOKE REQUESTS ───────────────────────────────────────────────
  echo "Hitting smoke endpoint: $SMOKE_URL"
  HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "$SMOKE_URL" 2>&1 || echo "000")
  if [ "$HTTP_CODE" = "000" ]; then
    echo "ERROR: Smoke request failed (no response)"
    exit 1
  fi
  echo "Smoke response: HTTP $HTTP_CODE"

  # ─── DONE ─────────────────────────────────────────────────────────
  echo "Smoke test passed ✅"
}

# ─── DISPATCH ──────────────────────────────────────────────────────
case "$SMOKE_MODE" in
  server)  smoke_server ;;
  cli)     smoke_cli ;;
  library) smoke_library ;;
  *)
    echo "ERROR: Unknown HARNESS_SMOKE_MODE: $SMOKE_MODE"
    echo "Valid values: server, cli, library, auto"
    exit 1
    ;;
esac
