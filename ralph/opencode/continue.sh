#!/usr/bin/env bash
#
# continue.sh
# Run an initial prompt once, then resume the same OpenCode session and send
# "continue" repeatedly.
#
# Optional Environment Variables:
# CONTINUE_MODEL     - Default model (provider/model), e.g. github-copilot/gpt-5.2
# CONTINUE_PRD_FILE  - Default PRD file path referenced in templates
# CONTINUE_EXPORT    - If set to a filepath, exports the final session JSON there

set -euo pipefail

usage() {
  echo "Usage: ${0##*/} [-m|--model MODEL] [--agent AGENT] [--variant VARIANT] [--format default|json] [--share] [--title TITLE] [--attach-file FILE ...] [-p|--prompt PROMPT | -f|--prompt-file FILE | -t|--prompt-template FILE] [-d|--prd-file FILE] [count] [-- opencode-run-args...]"
  echo ""
  echo "Options:"
  echo "  -m, --model            Model (provider/model) (default: \"${CONTINUE_MODEL:-github-copilot/gpt-5.2}\")"
  echo "      --agent            Agent to use (default: none)"
  echo "      --variant          Model variant (provider-specific) (default: none)"
  echo "      --format           Output format for opencode run (default|json) (default: default)"
  echo "      --share            Share the session (passes --share to opencode run)"
  echo "      --title            Session title for the initial run (passes --title to opencode run)"
  echo "      --attach-file      File(s) to attach to the message (passes --file to opencode run)"
  echo "  -p, --prompt           Prompt text to send (initial run)"
  echo "  -f, --prompt-file      Read prompt text from a file (initial run)"
  echo "  -t, --prompt-template  Read template text from a file (initial run)"
  echo "  -d, --prd-file         PRD file path to reference in the prompt"
  echo "  -h, --help             Show this help message"
  echo ""
  echo "Defaults:"
  echo "  count: 5 (number of 'continue' turns after the initial prompt)"
  echo ""
  echo "Template tokens (used with --prompt-template):"
  echo "  {{PRD_FILE}}  PRD file path"
  exit 1
}

err() {
  printf "ERROR: %s\n" "$1" >&2
  exit 1
}

require_cmd() {
  local name="$1"
  if ! command -v "${name}" &>/dev/null; then
    err "'${name}' command is required but not installed"
  fi
}

python_cmd() {
  if command -v python3 &>/dev/null; then
    echo "python3"
    return 0
  fi
  if command -v python &>/dev/null; then
    echo "python"
    return 0
  fi
  return 1
}

get_latest_session_id() {
  local py
  py="$(python_cmd)" || err "python3 (or python) is required to parse JSON"

  opencode session list --format json -n 1 | "${py}" - <<'PY'
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    sys.exit(1)

data = json.loads(raw)

# Accept a few possible shapes.
sessions = None
if isinstance(data, list):
    sessions = data
elif isinstance(data, dict):
    for key in ("sessions", "items", "data"):
        if isinstance(data.get(key), list):
            sessions = data[key]
            break

if not sessions:
    sys.exit(1)

first = sessions[0]
if not isinstance(first, dict):
    sys.exit(1)

for key in ("id", "sessionId", "sessionID"):
    if key in first and first[key]:
        sys.stdout.write(str(first[key]))
        sys.exit(0)

sys.exit(1)
PY
}

parse_args() {
  model="${CONTINUE_MODEL:-github-copilot/gpt-5.2}"
  agent=""
  variant=""
  format="default"
  share_mode="false"
  title=""
  prompt=""
  prompt_file=""
  prompt_template=""
  prd_file="${CONTINUE_PRD_FILE:-}"
  count="5"
  attach_files=()
  extra_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -m|--model)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--model requires a value"
        fi
        model="$2"
        shift 2
        ;;
      --agent)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--agent requires a value"
        fi
        agent="$2"
        shift 2
        ;;
      --variant)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--variant requires a value"
        fi
        variant="$2"
        shift 2
        ;;
      --format)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--format requires a value (default|json)"
        fi
        format="$2"
        shift 2
        ;;
      --share)
        share_mode="true"
        shift
        ;;
      --title)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--title requires a value"
        fi
        title="$2"
        shift 2
        ;;
      --attach-file)
        shift
        while [[ $# -gt 0 && "$1" != --* ]]; do
          attach_files+=("$1")
          shift
        done
        ;;
      -p|--prompt)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--prompt requires a value"
        fi
        prompt="$2"
        prompt_file=""
        prompt_template=""
        shift 2
        ;;
      -f|--prompt-file)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--prompt-file requires a value"
        fi
        prompt_file="$2"
        prompt_template=""
        shift 2
        ;;
      -t|--prompt-template)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--prompt-template requires a value"
        fi
        prompt_template="$2"
        prompt_file=""
        shift 2
        ;;
      -d|--prd-file)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--prd-file requires a value"
        fi
        prd_file="$2"
        shift 2
        ;;
      --)
        shift
        extra_args+=("$@")
        break
        ;;
      -h|--help)
        usage
        ;;
      *)
        if [[ "${count}" == "5" && "$1" =~ ^[0-9]+$ ]]; then
          count="$1"
        elif [[ -z "${prompt}" && -z "${prompt_file}" && -z "${prompt_template}" ]]; then
          prompt="$1"
        else
          extra_args+=("$1")
        fi
        shift
        ;;
    esac
  done

  if [[ -n "${prompt}" && ( -n "${prompt_file}" || -n "${prompt_template}" ) ]]; then
    err "Use either --prompt or --prompt-file/--prompt-template, not both"
  fi

  if [[ -n "${prompt_template}" ]]; then
    if [[ -n "${prompt_file}" ]]; then
      err "Use either --prompt-file or --prompt-template, not both"
    fi
    prompt_file="${prompt_template}"
  fi

  if [[ -n "${prompt_file}" ]]; then
    if [[ ! -f "${prompt_file}" ]]; then
      err "Prompt file not found: ${prompt_file}"
    fi
    prompt="$(cat "${prompt_file}")"
  fi

  if [[ -n "${prd_file}" ]]; then
    if [[ ! -f "${prd_file}" ]]; then
      err "PRD file not found: ${prd_file}"
    fi
    prompt="${prompt//\{\{PRD_FILE\}\}/${prd_file}}"
  else
    prompt="${prompt//\{\{PRD_FILE\}\}/}"
  fi

  if [[ -z "${prompt}" ]]; then
    usage
  fi

  if ! [[ "${count}" =~ ^[0-9]+$ ]]; then
    err "count must be a positive integer"
  fi

  if [[ "${format}" != "default" && "${format}" != "json" ]]; then
    err "--format must be 'default' or 'json'"
  fi
}

main() {
  parse_args "$@"

  require_cmd "opencode"

  echo "=== initial run (model=${model}) ==="
  local opencode_args
  opencode_args=("opencode" "run" "--model" "${model}" "--format" "${format}")

  if [[ -n "${agent}" ]]; then
    opencode_args+=("--agent" "${agent}")
  fi

  if [[ -n "${variant}" ]]; then
    opencode_args+=("--variant" "${variant}")
  fi

  if [[ "${share_mode}" == "true" ]]; then
    opencode_args+=("--share")
  fi

  if [[ -n "${title}" ]]; then
    opencode_args+=("--title" "${title}")
  fi

  for file_path in "${attach_files[@]}"; do
    if [[ ! -f "${file_path}" ]]; then
      err "Attach file not found: ${file_path}"
    fi
    opencode_args+=("--file" "${file_path}")
  done

  if [[ ${#extra_args[@]} -gt 0 ]]; then
    opencode_args+=("${extra_args[@]}")
  fi

  "${opencode_args[@]}" "${prompt}"

  local session_id
  session_id="$(get_latest_session_id)" || err "failed to discover latest session id"

  echo "=== session: ${session_id} ==="

  for ((i=1; i<=count; i++)); do
    echo "=== continue ${i}/${count} ==="
    local continue_args
    continue_args=("opencode" "run" "--session" "${session_id}" "--model" "${model}" "--format" "${format}")

    if [[ -n "${agent}" ]]; then
      continue_args+=("--agent" "${agent}")
    fi

    if [[ -n "${variant}" ]]; then
      continue_args+=("--variant" "${variant}")
    fi

    if [[ "${share_mode}" == "true" ]]; then
      continue_args+=("--share")
    fi

    if [[ -n "${title}" ]]; then
      continue_args+=("--title" "${title}")
    fi

    for file_path in "${attach_files[@]}"; do
      continue_args+=("--file" "${file_path}")
    done

    if [[ ${#extra_args[@]} -gt 0 ]]; then
      continue_args+=("${extra_args[@]}")
    fi

    "${continue_args[@]}" "continue"
  done

  if [[ -n "${CONTINUE_EXPORT:-}" ]]; then
    echo "=== export session to: ${CONTINUE_EXPORT} ==="
    opencode export "${session_id}" >"${CONTINUE_EXPORT}"
  fi
}

main "$@"
