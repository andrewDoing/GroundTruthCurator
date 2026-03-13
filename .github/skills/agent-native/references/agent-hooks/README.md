# Agent Hooks Reference

Agent hooks are lifecycle callbacks that fire at key points during an agent's session — before/after tool use, on session start/stop, etc. They provide **deterministic, code-driven automation** that runs regardless of how the agent is prompted.

Hooks are the harness engineering mechanism for enforcing policy, automating quality checks, and creating audit trails without relying on the agent to "remember" to do things.

## Why Hooks Matter for Harness Engineering

| Practice | How Hooks Help |
|---|---|
| Make easy to do hard thing | PostToolUse auto-runs formatters/linters after edits |
| Build observability in from day 1 | Log every tool invocation to JSONL for audit |
| Invest in static analysis | PostToolUse triggers lint after file changes |
| Manage entropy | Session hooks validate project state on start |
| Bring your own harness | Hooks enforce repo-specific policies deterministically |

## Hook Implementations by Agent

Each agent has its own hook configuration format. See the subfolder for your agent:

- **[copilot-hooks/](./copilot-hooks/)** — GitHub Copilot (VS Code, CLI, coding agent)
- _(future: claude-code/, cursor/, openclaw/, etc.)_

## Common Patterns (Agent-Agnostic)

These patterns apply regardless of which agent you're using. Implement them in your agent's hook format.

### 1. Auto-Format After File Edits

Run your formatter (Prettier, Ruff, gofmt, etc.) after every file edit. The agent sees the formatted result, not its raw output.

### 2. Auto-Lint After File Edits

Run lint checks after edits. If the agent introduced a violation, the error appears in context immediately — no waiting for CI.

### 3. Block Dangerous Commands

Deny destructive operations (`rm -rf /`, `DROP TABLE`, `git push --force`) at the pre-tool-use stage. The agent gets a clear denial reason and can retry safely.

### 4. Audit Trail

Log every tool invocation (tool name, args, result, timestamp) to `.harness/agent-audit.jsonl`. Useful for debugging agent behavior and measuring tool usage patterns.

### 5. Session Initialization

On session start, validate project state: check dependencies are installed, test DB is seeded, required env vars exist. Inject context about project state into the agent.

### 6. Observability Integration

After tool use, append structured events to `.harness/logs.jsonl`:
```json
{"ts":"...","level":"INFO","msg":"tool_use","tool":"bash","args":"npm test","result":"success","duration_ms":3200}
```

This bridges agent activity into the same JSONL observability pipeline the app uses.
