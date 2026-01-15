#!/usr/bin/env bash
#
# continue.sh
# Run an initial prompt once, then resume the same Copilot session and send
# "continue" repeatedly.

set -euo pipefail

usage() {
  echo "Usage: ${0##*/} [-m|--model MODEL] [-p|--prompt PROMPT | -f|--prompt-file FILE | -t|--prompt-template FILE] [-d|--prd-file FILE] [count] [copilot-args...]"
  echo ""
  echo "Options:"
  echo "  -m, --model            Model name (default: \"${CONTINUE_MODEL:-gpt-5.2}\")"
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

extract_session_id() {
  local session_file="$1"

  if [[ ! -f "${session_file}" ]]; then
    err "session export file not found: ${session_file}"
  fi

  sed -n 's/^> \*\*Session ID:\*\* `\(.*\)`/\1/p' "${session_file}"
}

parse_args() {
  model="${CONTINUE_MODEL:-gpt-5.2}"
  prompt=""
  prompt_file=""
  prompt_template=""
  prd_file="${CONTINUE_PRD_FILE:-}"
  count="5"
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
}

main() {
  parse_args "$@"

  if ! command -v copilot &>/dev/null; then
    err "'copilot' command is required but not installed"
  fi

  if ! [[ "${count}" =~ ^[0-9]+$ ]]; then
    err "count must be a positive integer"
  fi

  local session_file
  session_file="$(mktemp -t copilot-session-continue.XXXXXX.md 2>/dev/null || true)"
  if [[ -z "${session_file}" ]]; then
    session_file=".copilot-session-continue.md"
  fi

  echo "=== initial run (model=${model}) ==="
  copilot --model "${model}" -p "${prompt}" --yolo --share "${session_file}" \
    "${extra_args[@]}"

  local session_id
  session_id="$(extract_session_id "${session_file}")"
  if [[ -z "${session_id}" ]]; then
    err "failed to extract session ID from: ${session_file}"
  fi

  echo "=== session: ${session_id} ==="

  for ((i=1; i<=count; i++)); do
    echo "=== continue ${i}/${count} ==="
    copilot --resume "${session_id}" --model "${model}" -p "continue" --yolo \
      "${extra_args[@]}"
  done

  if [[ "${CONTINUE_KEEP_SESSION_FILE:-}" != "1" ]]; then
    rm -f "${session_file}" || true
  else
    echo "Kept session export: ${session_file}"
  fi
}

main "$@"
