# GitHub Copilot Hooks

Hooks for GitHub Copilot agents — VS Code agent mode, Copilot CLI, and the coding agent (cloud). All three share the same hook configuration format.

**Sources:**
- [VS Code hooks docs](https://code.visualstudio.com/docs/copilot/customization/hooks)
- [GitHub hooks reference](https://docs.github.com/en/copilot/reference/hooks-configuration)
- [Copilot CLI hooks tutorial](https://docs.github.com/en/copilot/tutorials/copilot-cli-hooks)

---

## Configuration

Hooks are JSON files with a `hooks` object keyed by event type. VS Code and Copilot CLI share the same format (also compatible with Claude Code's `settings.json`).

### File Locations (searched in order)

| Location | Scope | Committed? |
|---|---|---|
| `.github/hooks/*.json` | Project (shared with team) | ✅ Yes |
| `.claude/settings.json` | Project (compatible format) | ✅ Yes |
| `.claude/settings.local.json` | Project (personal) | ❌ No |
| `~/.claude/settings.json` | User (all projects) | ❌ No |

Workspace hooks take precedence over user hooks for the same event type.

### Format

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "command",
        "command": "./scripts/pre-tool.sh",
        "timeout": 15
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": "./scripts/post-tool.sh"
      }
    ]
  }
}
```

### Command Properties

| Property | Type | Description |
|---|---|---|
| `type` | string | Must be `"command"` |
| `command` | string | Default command (cross-platform) |
| `bash` | string | Bash-specific command (CLI) |
| `windows` | string | Windows override |
| `linux` | string | Linux override |
| `osx` | string | macOS override |
| `cwd` | string | Working directory (relative to repo root) |
| `env` | object | Additional environment variables |
| `timeout` / `timeoutSec` | number | Timeout in seconds (default: 30) |

---

## Hook Events

### SessionStart
**When:** User submits first prompt of a new session (or resumes one).

**Input:**
```json
{
  "timestamp": 1704614400000,
  "cwd": "/path/to/project",
  "source": "new",
  "initialPrompt": "Fix the auth bug"
}
```
- `source`: `"new"`, `"resume"`, or `"startup"`

**Output:** Ignored.

**Harness use:** Validate project state, initialize resources, log session start.

### UserPromptSubmit
**When:** User submits a prompt.

**Input:**
```json
{
  "timestamp": 1704614500000,
  "cwd": "/path/to/project",
  "prompt": "Fix the authentication bug"
}
```

**Output:** Ignored.

**Harness use:** Audit trail of user prompts.

### PreToolUse ⚡ (most powerful)
**When:** Before the agent invokes any tool (bash, edit, view, create, etc.).

**Input:**
```json
{
  "timestamp": 1704614600000,
  "cwd": "/path/to/project",
  "toolName": "bash",
  "toolArgs": "{\"command\":\"rm -rf dist\"}"
}
```
- VS Code also includes `tool_input` (parsed object) and `tool_use_id`

**Output (optional):**
```json
{
  "permissionDecision": "deny",
  "permissionDecisionReason": "Destructive command blocked by policy"
}
```

| `permissionDecision` | Effect |
|---|---|
| `"allow"` | Auto-approve (skip user confirmation) |
| `"deny"` | Block execution, show reason to agent |
| `"ask"` | Require user confirmation (VS Code only) |

When multiple hooks run, **most restrictive wins** (deny > ask > allow).

VS Code also supports `updatedInput` (modify tool args) and `additionalContext` (inject context for the model).

**Harness use:** Block dangerous commands, enforce file path restrictions, require approval for sensitive ops.

### PostToolUse
**When:** After a tool completes (success or failure).

**Input:**
```json
{
  "timestamp": 1704614700000,
  "cwd": "/path/to/project",
  "toolName": "bash",
  "toolArgs": "{\"command\":\"npm test\"}",
  "toolResult": {
    "resultType": "success",
    "textResultForLlm": "All tests passed (15/15)"
  }
}
```
- `resultType`: `"success"`, `"failure"`, or `"denied"`

**Output:** Ignored.

**Harness use:** Auto-format, auto-lint, log tool results, trigger follow-up checks.

### PreCompact (VS Code only)
**When:** Before conversation context is compacted (truncated for length).

**Harness use:** Export important context before it's lost.

### SubagentStart / SubagentStop (VS Code only)
**When:** Subagent spawned / completed.

**Harness use:** Track nested agent usage, aggregate results.

### Stop
**When:** Agent session ends.

**Input:**
```json
{
  "timestamp": 1704618000000,
  "cwd": "/path/to/project",
  "reason": "complete"
}
```
- `reason`: `"complete"`, `"error"`, `"abort"`, `"timeout"`, `"user_exit"`

**Output:** Ignored.

**Harness use:** Generate reports, cleanup temp files, finalize audit log.

### ErrorOccurred (CLI only)
**When:** Error during agent execution.

**Harness use:** Log errors, alert on failures.

---

## Exit Codes

| Code | Behavior |
|---|---|
| 0 | Success — parse stdout as JSON |
| 2 | Blocking error — stop processing, show error to model |
| Other | Non-blocking warning — show warning, continue |

---

## Harness Engineering Hook Recipes

### Recipe 1: Auto-Format + Lint After Edits

`.github/hooks/post-tool.json`:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "./scripts/hooks/post-edit.sh",
        "timeout": 30
      }
    ]
  }
}
```

`scripts/hooks/post-edit.sh`:
```bash
#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolName')

# Only run after file edits
if [[ "$TOOL_NAME" == "edit" || "$TOOL_NAME" == "create" || "$TOOL_NAME" == "editFiles" ]]; then
  # Format
  npx prettier --write "$(echo "$INPUT" | jq -r '.toolArgs' | jq -r '.path // .files[0]')" 2>/dev/null

  # Quick lint (non-blocking — exit 0 regardless)
  npx eslint --format json "$(echo "$INPUT" | jq -r '.toolArgs' | jq -r '.path // .files[0]')" \
    >> .harness/lint-results.jsonl 2>/dev/null || true
fi
```

### Recipe 2: Block Dangerous Commands

`.github/hooks/safety.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "command",
        "command": "./scripts/hooks/safety-check.sh",
        "timeout": 5
      }
    ]
  }
}
```

`scripts/hooks/safety-check.sh`:
```bash
#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolName')
TOOL_ARGS=$(echo "$INPUT" | jq -r '.toolArgs')

# Block dangerous bash commands
if [ "$TOOL_NAME" = "bash" ]; then
  CMD=$(echo "$TOOL_ARGS" | jq -r '.command')
  if echo "$CMD" | grep -qE "rm -rf /|DROP TABLE|git push.*--force|:(){ :|:& };:"; then
    echo '{"permissionDecision":"deny","permissionDecisionReason":"Blocked by safety policy: destructive command detected"}'
    exit 0
  fi
fi

# Block edits outside src/ and test/
if [[ "$TOOL_NAME" == "edit" || "$TOOL_NAME" == "create" ]]; then
  FILE_PATH=$(echo "$TOOL_ARGS" | jq -r '.path')
  if [[ ! "$FILE_PATH" =~ ^(src/|test/|tests/) ]]; then
    echo '{"permissionDecision":"deny","permissionDecisionReason":"Can only edit files in src/ or test/ directories"}'
    exit 0
  fi
fi

# Allow everything else
echo '{"permissionDecision":"allow"}'
```

### Recipe 3: Audit Trail to JSONL

`.github/hooks/audit.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "command",
        "command": "./scripts/hooks/audit-log.sh"
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": "./scripts/hooks/audit-result.sh"
      }
    ]
  }
}
```

`scripts/hooks/audit-log.sh`:
```bash
#!/bin/bash
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.toolName')
ARGS=$(echo "$INPUT" | jq -r '.toolArgs')
TS=$(echo "$INPUT" | jq -r '.timestamp')

echo "{\"ts\":$TS,\"event\":\"pre_tool\",\"tool\":\"$TOOL\",\"args\":$ARGS}" >> .harness/agent-audit.jsonl
```

`scripts/hooks/audit-result.sh`:
```bash
#!/bin/bash
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.toolName')
RESULT=$(echo "$INPUT" | jq -r '.toolResult.resultType')
TS=$(echo "$INPUT" | jq -r '.timestamp')

echo "{\"ts\":$TS,\"event\":\"post_tool\",\"tool\":\"$TOOL\",\"result\":\"$RESULT\"}" >> .harness/agent-audit.jsonl
```

### Recipe 4: Session Init — Validate Project State

`.github/hooks/session.json`:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "./scripts/hooks/session-init.sh",
        "timeout": 60
      }
    ]
  }
}
```

`scripts/hooks/session-init.sh`:
```bash
#!/bin/bash
# Ensure dependencies are installed
if [ -f "package.json" ] && [ ! -d "node_modules" ]; then
  npm install --silent
fi

# Ensure .harness/ exists
mkdir -p .harness/queries
touch .harness/logs.jsonl .harness/traces.jsonl .harness/metrics.jsonl

# Clear stale telemetry from previous sessions
: > .harness/logs.jsonl
: > .harness/traces.jsonl

# Seed test data if needed
if [ -f "scripts/harness/seed.sh" ]; then
  ./scripts/harness/seed.sh
fi

echo "Session initialized" >> .harness/agent-audit.jsonl
```

---

## Copilot-Specific Customization Files

Hooks work alongside these other Copilot customization points:

| File | Purpose | Auto-loaded? |
|---|---|---|
| `.github/copilot-instructions.md` | Always-on coding standards | ✅ Every request |
| `AGENTS.md` | Agent instructions (multi-agent compat) | ✅ Every request |
| `.github/skills/*/SKILL.md` | Specialized capabilities | On-demand (task match) |
| `*.instructions.md` | File-pattern or task-based rules | On-demand (glob/description match) |
| `.agent.md` | Custom agent personas | When selected |
| `.github/hooks/*.json` | Lifecycle hooks (this doc) | At lifecycle events |

**Skills** are an [open standard](https://agentskills.io) that work across VS Code, Copilot CLI, and the coding agent. The harness engineering skill itself can be installed in `.github/skills/` or `.agents/skills/`.

---

## Tips

- **Keep hooks fast.** Hooks run synchronously — a slow hook blocks the agent. Use the `timeout` property.
- **Exit 0 for success.** Exit 2 to hard-block. Any other exit code is a non-blocking warning.
- **Hooks are deterministic.** Unlike instructions (which are suggestions), hooks execute your code. Use them for things that *must* happen.
- **Combine hooks + instructions.** Use hooks to enforce policy; use instructions to guide behavior. They're complementary.
- **Test hooks manually.** Pipe test JSON into your script: `echo '{"toolName":"bash","toolArgs":"{\"command\":\"rm -rf /\"}"}' | ./scripts/hooks/safety-check.sh`
