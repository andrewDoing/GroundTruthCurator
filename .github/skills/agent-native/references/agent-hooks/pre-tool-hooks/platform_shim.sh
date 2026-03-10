#!/bin/bash
# platform_shim.sh - Normalize Claude Code and Copilot CLI hook I/O

detect_platform() {
  local input="${1:-}"
  if [[ "${input}" == *'"toolName"'* ]]; then
    echo "copilot"
    return 0
  fi
  if jaq -e 'has("toolName")' <<<"${input}" >/dev/null 2>&1; then
    echo "copilot"
  else
    echo "claude"
  fi
}

get_tool_name() {
  local input="${1:-}"
  local platform="${2:-$(detect_platform "${input}")}"
  local raw=""
  if [[ "${platform}" == "copilot" ]]; then
    raw=$(jaq -r '.toolName // empty' <<<"${input}" 2>/dev/null) || raw=""
    case "${raw}" in
      edit) echo "Edit" ;;
      create|write) echo "Write" ;;
      bash) echo "Bash" ;;
      *) echo "${raw}" ;;
    esac
  else
    raw=$(jaq -r '.tool_name // empty' <<<"${input}" 2>/dev/null) || raw=""
    echo "${raw}"
  fi
}

get_tool_input() {
  local input="${1:-}"
  local platform="${2:-$(detect_platform "${input}")}"
  if [[ "${platform}" == "copilot" ]]; then
    local args=""
    args=$(jaq -r '.toolArgs // empty' <<<"${input}" 2>/dev/null) || args=""
    if [[ -z "${args}" ]]; then
      echo "{}"
    else
      jaq -cn --arg args "${args}" '$args | fromjson? // {}' 2>/dev/null || echo "{}"
    fi
  else
    jaq -c '.tool_input // {}' <<<"${input}" 2>/dev/null || echo "{}"
  fi
}

get_file_path() {
  local input="${1:-}"
  local platform="${2:-$(detect_platform "${input}")}"
  local tool_input
  tool_input=$(get_tool_input "${input}" "${platform}")
  jaq -r '.file_path // .filePath // .path // empty' <<<"${tool_input}" 2>/dev/null || echo ""
}

get_command() {
  local input="${1:-}"
  local platform="${2:-$(detect_platform "${input}")}"
  local tool_input
  tool_input=$(get_tool_input "${input}" "${platform}")
  jaq -r '.command // empty' <<<"${tool_input}" 2>/dev/null || echo ""
}

emit_approve() {
  local platform="${1:-claude}"
  if [[ "${platform}" == "copilot" ]]; then
    echo '{"permissionDecision":"allow"}'
  else
    echo '{"decision":"approve"}'
  fi
}

emit_block() {
  local platform="${1:-claude}"
  local reason="${2:-Blocked by hook policy}"
  local system_message="${3:-}"
  if [[ "${platform}" == "copilot" ]]; then
    jaq -n --arg reason "${reason}" \
      '{"permissionDecision":"deny","permissionDecisionReason":$reason}'
  else
    if [[ -n "${system_message}" ]]; then
      jaq -n --arg reason "${reason}" --arg msg "${system_message}" \
        '{"decision":"block","reason":$reason,"systemMessage":$msg}'
    else
      jaq -n --arg reason "${reason}" \
        '{"decision":"block","reason":$reason}'
    fi
  fi
}
