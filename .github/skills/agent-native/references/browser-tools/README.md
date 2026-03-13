# Browser Tools for Agent Harnesses

Coding agents are blind to what their code does in the browser. They can read source files but can't see runtime behavior — layout breaks, console errors, network failures, slow renders. Browser tools close this gap.

## Why This Matters for Harness Engineering

The verify loop isn't complete without runtime validation. An agent can pass lint and tests but still ship a broken UI. Browser tools let agents:

- **See what users see** — take snapshots of the rendered page
- **Debug runtime errors** — read console logs, inspect network requests
- **Verify fixes** — navigate, interact, confirm the bug is gone
- **Profile performance** — measure Core Web Vitals, find bottlenecks

## Two Approaches

| Tool | Type | Best For | Setup |
|---|---|---|---|
| **Playwright CLI** | CLI (skill) | Coding agents (Copilot CLI, Claude Code) | `npm i -g @playwright/cli` |
| **Chrome DevTools MCP** | MCP server | Any MCP-compatible agent | MCP config entry |

They're complementary — Playwright CLI is better for agent-driven automation (snapshot → interact → verify), Chrome DevTools MCP is better for deep debugging (performance traces, network analysis, DOM inspection).

## Recommendation

- **Start with Playwright CLI** — it's simpler, works as an agent skill, and covers the 80% case (navigate, interact, snapshot, verify)
- **Add Chrome DevTools MCP** when you need performance profiling, network analysis, or deep DOM inspection
- **For frontend-heavy projects**, use both

## Setup

### Playwright CLI

Install globally:
```bash
npm install -g @playwright/cli
```

The skill is auto-discovered by Copilot and Claude Code when installed. For explicit use:
```bash
# Open a page, take a snapshot, interact
playwright-cli open http://localhost:3000
playwright-cli snapshot
playwright-cli click e5
playwright-cli fill e7 "test@example.com"
playwright-cli screenshot --filename=after-fix.png
playwright-cli close
```

See `playwright-cli/` for the full skill reference.

### Chrome DevTools MCP

Add to your MCP config (`.github/copilot-mcp.json`, `claude_desktop_config.json`, etc.):
```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["chrome-devtools-mcp@latest"]
    }
  }
}
```

See `chrome-devtools-mcp/` for the full skill reference.

## Harness Integration

### Verify Loop With Browser Checks

```bash
# In scripts/harness/smoke.sh or verify script:

# 1. Static checks
make check

# 2. Run tests
make test

# 3. Browser verification (if app is running)
if curl -s http://localhost:3000 > /dev/null 2>&1; then
  playwright-cli open http://localhost:3000
  playwright-cli snapshot --filename=.harness/page-snapshot.yml
  playwright-cli console  # check for JS errors
  playwright-cli close
fi
```

### PostToolUse Hook for Auto-Verify

After file edits in a frontend project, auto-snapshot the running app:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "./scripts/hooks/browser-verify.sh",
        "timeout": 30
      }
    ]
  }
}
```

```bash
#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolName')

# Only verify after file edits
if [[ "$TOOL_NAME" == "edit" || "$TOOL_NAME" == "create" ]]; then
  FILE=$(echo "$INPUT" | jq -r '.toolArgs' | jq -r '.path // .files[0]')
  # Only for frontend files
  if [[ "$FILE" =~ \.(tsx?|jsx?|css|html|vue|svelte)$ ]]; then
    # Wait for hot reload
    sleep 2
    playwright-cli snapshot --filename=.harness/post-edit-snapshot.yml 2>/dev/null || true
  fi
fi
```
