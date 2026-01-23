#!/bin/bash
# Ralph Loop for GitHub Copilot CLI
# Usage: ./ralph-loop.sh [plan] [max_iterations] [--model MODEL]
# Examples:
#   ./ralph-loop.sh                        # Build mode, unlimited iterations
#   ./ralph-loop.sh 20                     # Build mode, max 20 iterations
#   ./ralph-loop.sh plan                   # Plan mode, unlimited iterations
#   ./ralph-loop.sh plan 5                 # Plan mode, max 5 iterations
#   ./ralph-loop.sh --model gpt-4o         # Build mode with custom model
#   ./ralph-loop.sh plan --model gpt-4o 5  # Plan mode with custom model

set -euo pipefail

# Default models per mode
DEFAULT_MODEL_PLAN="claude-opus-4.5"
DEFAULT_MODEL_BUILD="gpt-5.2-codex"

# Parse arguments
MODE="build"
AGENT="ralph-implementor"
MAX_ITERATIONS=0
MODEL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        plan)
            MODE="plan"
            AGENT="ralph-planner"
            shift
            ;;
        --model)
            if [[ -z "${2:-}" || "$2" == --* ]]; then
                echo "Error: --model requires an argument" >&2
                exit 1
            fi
            MODEL="$2"
            shift 2
            ;;
        [0-9]*)
            MAX_ITERATIONS=$1
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Set default model based on mode if not specified
if [[ -z "$MODEL" ]]; then
    if [[ "$MODE" == "plan" ]]; then
        MODEL="$DEFAULT_MODEL_PLAN"
    else
        MODEL="$DEFAULT_MODEL_BUILD"
    fi
fi

ITERATION=0
CURRENT_BRANCH=$(git branch --show-current)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mode:   $MODE"
echo "Agent:  $AGENT"
echo "Model:  $MODEL"
echo "Branch: $CURRENT_BRANCH"
[ "$MAX_ITERATIONS" -gt 0 ] && echo "Max:    $MAX_ITERATIONS iterations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verify agent files exist
AGENT_FILE=".github/agents/${AGENT}.agent.md"
if [ ! -f "$AGENT_FILE" ]; then
    echo "Error: Agent file not found: $AGENT_FILE"
    echo "Ensure ralph-planner.agent.md and ralph-implementor.agent.md exist in .github/agents/"
    exit 1
fi

# Build the prompt based on mode
build_prompt() {
    local mode=$1
    
    if [ "$mode" = "plan" ]; then
        cat <<'EOF'
Study the codebase and create/update the implementation plan.

1. Read AGENTS.md (if present) to understand project-specific commands and patterns.
2. Study specs/* (if present) to learn the application specifications.
3. Study IMPLEMENTATION_PLAN.md (if present) to understand the plan so far.
4. Study src/lib/* to understand shared utilities and components.
5. Compare specs against existing code and identify gaps: missing features, incomplete implementations, TODOs, placeholders, skipped tests, inconsistent patterns.
6. Create/update IMPLEMENTATION_PLAN.md as a prioritized bullet point list of items yet to be implemented.

IMPORTANT: Plan only. Do NOT implement anything. Do NOT assume functionality is missing; confirm with code search first.
EOF
    else
        cat <<'EOF'
Implement the next task from the implementation plan.

1. Read AGENTS.md (if present) to understand project-specific commands and patterns.
2. Study IMPLEMENTATION_PLAN.md and choose the most important item to address.
3. Before making changes, search the codebase (don't assume not implemented).
4. Implement the functionality per specifications.
5. Run tests and validation for the implemented code.
6. When tests pass, update IMPLEMENTATION_PLAN.md, then git add -A, git commit, git push.
7. Update AGENTS.md with any operational learnings (keep it brief).

IMPORTANT: Implement functionality completely. Placeholders and stubs waste efforts.
When you are done and no further work is needed, output a single line: COMPLETE
EOF
    fi
}

# Main loop
while true; do
    if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "Reached max iterations: $MAX_ITERATIONS"
        break
    fi

    ITERATION=$((ITERATION + 1))
    echo -e "\n======================== LOOP $ITERATION ========================\n"

    # Build the prompt
    PROMPT=$(build_prompt "$MODE")

    # Run Copilot CLI with the agent
    # --agent: Use the specified agent from .github/agents/
    # --model: Use the specified model
    # --yolo: Auto-approve all tool calls (equivalent to --dangerously-skip-permissions)
    copilot_output_file=$(mktemp)
    copilot -p "$PROMPT" --agent "$AGENT" --model "$MODEL" --yolo | tee "$copilot_output_file"

    if grep -q "^COMPLETE$" "$copilot_output_file"; then
        rm -f "$copilot_output_file"
        echo "Completion signal received. Exiting loop."
        break
    fi

    rm -f "$copilot_output_file"

    # Push changes after each iteration (build mode only)
    # if [ "$MODE" = "build" ]; then
    #     CURRENT_BRANCH=$(git branch --show-current)
    #     git push origin "$CURRENT_BRANCH" 2>/dev/null || {
    #         echo "Failed to push. Creating remote branch..."
    #         git push -u origin "$CURRENT_BRANCH"
    #     }
    # fi

    echo -e "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Iteration $ITERATION complete"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
done

echo ""
echo "Ralph loop finished after $ITERATION iteration(s)"
