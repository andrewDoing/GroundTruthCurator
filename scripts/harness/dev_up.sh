#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

backend_pid_file="$root_dir/.harness/dev/backend.pid"
frontend_pid_file="$root_dir/.harness/dev/frontend.pid"
backend_log_file="$root_dir/.harness/dev/backend.log"
frontend_log_file="$root_dir/.harness/dev/frontend.log"
backend_port="${HARNESS_BACKEND_PORT:-8000}"
frontend_port="${HARNESS_FRONTEND_PORT:-5173}"

command -v uv >/dev/null 2>&1 || { echo 'ERROR: uv is required for backend startup.' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for frontend startup.' >&2; exit 1; }

mkdir -p "$root_dir/.harness/dev"

read_pid() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    tr -d '[:space:]' <"$pid_file"
  fi
}

pid_is_running() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

port_listener_info() {
  local port="$1"

  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi

  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tail -n +2
}

resolve_available_port() {
  local name="$1"
  local requested_port="$2"
  local port="$requested_port"
  local listener_info
  local attempts=0

  while [ "$attempts" -lt 100 ]; do
    listener_info=$(port_listener_info "$port" || true)
    if [ -z "$listener_info" ]; then
      if [ "$port" -ne "$requested_port" ]; then
        echo "==> ${name} port ${requested_port} is busy; using ${port} instead" >&2
      fi
      printf '%s\n' "$port"
      return 0
    fi

    if [ "$attempts" -eq 0 ]; then
      echo "==> ${name} port ${requested_port} is busy; searching for the next available port" >&2
      echo "$listener_info" >&2
    fi

    port=$((port + 1))
    attempts=$((attempts + 1))
  done

  echo "ERROR: unable to find an available ${name} port starting at ${requested_port}." >&2
  return 1
}

ensure_not_running() {
  local name="$1"
  local pid_file="$2"
  local pid

  pid=$(read_pid "$pid_file")
  if pid_is_running "$pid"; then
    echo "ERROR: ${name} is already running with PID ${pid}. Use 'make -f Makefile.harness dev-down' first." >&2
    exit 1
  fi

  rm -f "$pid_file"
}

start_process() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  shift 3

  : >"$log_file"

  (
    cd "$root_dir/$name"
    nohup "$@" >"$log_file" 2>&1 &
    echo $! >"$pid_file"
  )
}

cleanup_started_processes() {
  local pid
  for pid in "$(read_pid "$backend_pid_file")" "$(read_pid "$frontend_pid_file")"; do
    if pid_is_running "$pid"; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  rm -f "$backend_pid_file" "$frontend_pid_file"
}

ensure_not_running "backend" "$backend_pid_file"
ensure_not_running "frontend" "$frontend_pid_file"
backend_port=$(resolve_available_port "backend" "$backend_port")
frontend_port=$(resolve_available_port "frontend" "$frontend_port")

echo '==> Starting backend in background'
start_process backend "$backend_pid_file" "$backend_log_file" uv run uvicorn app.main:app --reload --host 127.0.0.1 --port "$backend_port"

echo '==> Starting frontend in background'
start_process frontend "$frontend_pid_file" "$frontend_log_file" env HARNESS_BACKEND_URL="http://127.0.0.1:${backend_port}" npm run dev -- --port "$frontend_port"

sleep 2

backend_pid=$(read_pid "$backend_pid_file")
frontend_pid=$(read_pid "$frontend_pid_file")
startup_failed=0

if ! pid_is_running "$backend_pid"; then
  echo "ERROR: backend exited during startup. Check $backend_log_file" >&2
  startup_failed=1
fi

if ! pid_is_running "$frontend_pid"; then
  echo "ERROR: frontend exited during startup. Check $frontend_log_file" >&2
  startup_failed=1
fi

if [ "$startup_failed" -ne 0 ]; then
  cleanup_started_processes
  exit 1
fi

echo "Backend PID: $backend_pid"
echo "Frontend PID: $frontend_pid"
echo "Backend URL: http://127.0.0.1:${backend_port}"
echo "Frontend URL: http://127.0.0.1:${frontend_port}"
echo "Logs: $root_dir/.harness/dev/"
echo "Stop both with: make -f Makefile.harness dev-down"
