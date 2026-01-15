#!/usr/bin/env bash
#
# ralph-once.sh
# Run a prompt with the ralph-implementor agent with manual confirmation between runs.

set -euo pipefail

## Optional Environment Variables:
# RALPH_MODEL  - Default model name when not provided via args
# RALPH_AGENT  - Default agent to use (default: ralph-implementor)
# RALPH_PRD_FILE  - Default PRD file path referenced in templates

usage() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local default_prompt_file="${script_dir}/ralph-prd.txt"

  echo "Usage: ${0##*/} [-m|--model MODEL] [-a|--agent AGENT] [-p|--prompt PROMPT | -f|--prompt-file FILE | -t|--prompt-template FILE] [-d|--prd-file FILE] [prompt] [count] [copilot-args...]"
  echo ""
  echo "Options:"
  echo "  -m, --model            Model name (default: \"${RALPH_MODEL:-gpt-5.2}\")"
  echo "  -a, --agent            Agent to use (default: \"${RALPH_AGENT:-ralph-implementor}\")"
  echo "  -p, --prompt           Prompt text to send"
  echo "  -f, --prompt-file      Read prompt text from a file"
  echo "  -t, --prompt-template  Read template text from a file"
  echo "  -d, --prd-file         PRD file path to reference in the prompt"
  echo "  -h, --help             Show this help message"
  echo ""
  echo "Defaults:"
  echo "  Prompt file: ${default_prompt_file}"
  echo ""
  echo "Template tokens (used with --prompt-template or default prompt file):"
  echo "  {{PRD_FILE}}  PRD file path"
  echo ""
  echo "Available agents:"
  echo "  ralph-implementor    CLI-compatible implementation executor (default)"
  echo "  task-researcher      Deep research operations"
  echo "  task-planner         Task planning workflows"
  exit 1
}

err() {
  printf "ERROR: %s\n" "$1" >&2
  exit 1
}

parse_args() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local default_prompt_file="${script_dir}/ralph-prd.txt"

  model="${RALPH_MODEL:-gpt-5.2}"
  agent="${RALPH_AGENT:-ralph-implementor}"
  prompt=""
  prompt_file=""
  prompt_template=""
  prd_file="${RALPH_PRD_FILE:-}"
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
      -a|--agent)
        if [[ -z "${2:-}" || "$2" == --* ]]; then
          err "--agent requires a value"
        fi
        agent="$2"
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

  if [[ -z "${prompt}" && -z "${prompt_file}" && -z "${prompt_template}" ]]; then
    prompt_file="${default_prompt_file}"
  fi

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

  for ((i=1; i<=count; i++)); do
    echo "=== run ${i}/${count} (model=${model}, agent=${agent}) ==="
    copilot --model "${model}" --agent "${agent}" -p "${prompt}" --yolo \
      "${extra_args[@]}"
    read -r -p "Press Enter to continue (Ctrl+C to stop) " _
  done
}

main "$@"
