#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root_dir"

backend_pid_file="$root_dir/.harness/dev/backend.pid"
frontend_pid_file="$root_dir/.harness/dev/frontend.pid"
overall_status=0

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

stop_process() {
  local name="$1"
  local pid_file="$2"
  local pid

  pid=$(read_pid "$pid_file")
  if [ -z "$pid" ]; then
    echo "==> ${name} is not running"
    return
  fi

  if ! pid_is_running "$pid"; then
    echo "==> Removing stale ${name} PID file (${pid})"
    rm -f "$pid_file"
    return
  fi

  echo "==> Stopping ${name} (PID ${pid})"
  kill "$pid"

  for _ in $(seq 1 10); do
    if ! pid_is_running "$pid"; then
      rm -f "$pid_file"
      return
    fi
    sleep 1
  done

  echo "ERROR: ${name} (PID ${pid}) did not stop cleanly." >&2
  overall_status=1
}

stop_process backend "$backend_pid_file"
stop_process frontend "$frontend_pid_file"

exit "$overall_status"
