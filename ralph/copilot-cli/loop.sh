#!/bin/bash
# Ralph Loop for GitHub Copilot CLI
# Usage: ./loop.sh --prompt "prompt text" [--agent AGENT] [--model MODEL] [--max N]
# Examples:
#   ./loop.sh --prompt "Implement the next task"
#   ./loop.sh --prompt "Plan the implementation" --agent ralph-planner
#   ./loop.sh --prompt "Fix bugs" --model gpt-4o --max 5

set -euo pipefail

DEFAULT_MODEL="claude-opus-4.5"
DEFAULT_AGENT="ralph-implementor"

PROMPT=""
AGENT="$DEFAULT_AGENT"
MODEL="$DEFAULT_MODEL"
MAX_ITERATIONS=0

usage() {
    echo "Usage: ${0##*/} --prompt \"prompt text\" [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  --prompt TEXT    The prompt to send to the agent"
    echo ""
    echo "Options:"
    echo "  --agent AGENT    Agent to use (default: $DEFAULT_AGENT)"
    echo "  --model MODEL    Model to use (default: $DEFAULT_MODEL)"
    echo "  --max N          Maximum iterations (default: unlimited)"
    echo "  --help, -h       Show this help message"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt)
            if [[ -z "${2:-}" || "$2" == --* ]]; then
                echo "Error: --prompt requires an argument" >&2
                usage
            fi
            PROMPT="$2"
            shift 2
            ;;
        --agent)
            if [[ -z "${2:-}" || "$2" == --* ]]; then
                echo "Error: --agent requires an argument" >&2
                usage
            fi
            AGENT="$2"
            shift 2
            ;;
        --model)
            if [[ -z "${2:-}" || "$2" == --* ]]; then
                echo "Error: --model requires an argument" >&2
                usage
            fi
            MODEL="$2"
            shift 2
            ;;
        --max)
            if [[ -z "${2:-}" || "$2" == --* ]]; then
                echo "Error: --max requires an argument" >&2
                usage
            fi
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            ;;
    esac
done

if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required" >&2
    usage
fi

ITERATION=0
CURRENT_BRANCH=$(git branch --show-current)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Agent:  $AGENT"
echo "Model:  $MODEL"
echo "Branch: $CURRENT_BRANCH"
[[ "$MAX_ITERATIONS" -gt 0 ]] && echo "Max:    $MAX_ITERATIONS iterations"
echo "Prompt: ${PROMPT:0:60}..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

AGENT_FILE=".github/agents/${AGENT}.agent.md"
if [[ ! -f "$AGENT_FILE" ]]; then
    echo "Error: Agent file not found: $AGENT_FILE" >&2
    exit 1
fi

while true; do
    if [[ "$MAX_ITERATIONS" -gt 0 ]] && [[ "$ITERATION" -ge "$MAX_ITERATIONS" ]]; then
        echo "Reached max iterations: $MAX_ITERATIONS"
        break
    fi

    ITERATION=$((ITERATION + 1))
    echo -e "\n======================== LOOP $ITERATION ========================\n"

    copilot -p "$PROMPT" --agent "$AGENT" --model "$MODEL" --yolo

    echo -e "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Iteration $ITERATION complete"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
done

echo ""
echo "Ralph loop finished after $ITERATION iteration(s)"
