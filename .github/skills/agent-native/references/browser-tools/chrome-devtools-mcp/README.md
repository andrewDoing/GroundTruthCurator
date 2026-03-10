# Chrome DevTools MCP — Agent Skill Reference

**Source:** [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp/)
**Type:** MCP server (Model Context Protocol)
**Compatibility:** Any MCP-compatible agent (Copilot, Claude Code, Gemini CLI, Cursor, etc.)
**Official blog:** [Chrome for Developers](https://developer.chrome.com/blog/chrome-devtools-mcp)

---

## Overview

MCP server that gives AI agents access to Chrome DevTools Protocol. Deep browser debugging — performance profiling, network analysis, DOM inspection, console monitoring, device emulation. Complements Playwright CLI: use Playwright for interaction, DevTools MCP for deep inspection.

## Setup

Add to your MCP config:

**Copilot (VS Code)** — `.github/copilot-mcp.json` or VS Code settings:
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

**Claude Code** — `.mcp.json` or `claude_desktop_config.json`:
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

**Copilot CLI** — `~/.copilot/config.json` or per-project config.

## Tool Categories

### Navigation & Page Management
- `new_page` — open a new tab
- `navigate_page` — go to URL, reload, back/forward
- `select_page` — switch between open tabs
- `list_pages` — see all open tabs and their IDs
- `close_page` — close a tab
- `wait_for` — wait for text to appear

### Input & Interaction
- `click` — click element (use `uid` from snapshot)
- `fill` / `fill_form` — type into inputs or fill multiple fields
- `hover` — mouse over element
- `press_key` — keyboard shortcuts (`Enter`, `Control+C`)
- `drag` — drag and drop
- `handle_dialog` — accept/dismiss alerts
- `upload_file` — file input upload

### Debugging & Inspection
- `take_snapshot` — accessibility tree (best for identifying elements)
- `take_screenshot` — visual capture
- `list_console_messages` / `get_console_message` — console output
- `evaluate_script` — run JS in page context
- `list_network_requests` / `get_network_request` — network traffic

### Performance & Emulation
- `resize_page` — viewport dimensions
- `emulate` — CPU/network throttling, geolocation
- `performance_start_trace` — start performance recording
- `performance_stop_trace` — stop and save trace
- `performance_analyze_insight` — automated analysis of Core Web Vitals

## When to Use (vs Playwright CLI)

| Scenario | Playwright CLI | Chrome DevTools MCP |
|---|---|---|
| Navigate + interact | ✅ Better (CLI-driven, fast) | ✅ Works |
| Take snapshots | ✅ Primary method | ✅ Works |
| Console errors | ✅ `console` command | ✅ More detailed |
| Network analysis | Basic (`network`) | ✅ **Full request/response details** |
| Performance profiling | Basic (`tracing-start`) | ✅ **Core Web Vitals, LCP analysis** |
| Device emulation | Basic (`resize`) | ✅ **Full emulation (CPU, network, geo)** |
| Request mocking | ✅ `route` command | ❌ Not available |
| Cookie/storage mgmt | ✅ Full support | ❌ Not available |

**Rule of thumb:** Start with Playwright CLI for interaction. Add DevTools MCP when you need the "why" behind performance or network issues.

## Workflow Patterns

### Pattern A: Identify Elements (Snapshot-First)
```
1. take_snapshot → get accessibility tree with uid values
2. Find target element's uid
3. click(uid=...) or fill(uid=..., value=...)
```

### Pattern B: Troubleshoot Errors
```
1. list_console_messages → check for JS errors
2. list_network_requests → identify 4xx/5xx failures
3. evaluate_script → inspect DOM state
```

### Pattern C: Performance Audit
```
1. performance_start_trace(reload=true, autoStop=true)
2. Wait for page load
3. performance_analyze_insight → get LCP, layout shift, bottleneck analysis
```

## Harness Engineering Integration

### Add to Project MCP Config

Create `.github/copilot-mcp.json` (committed, shared with team):
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

### Performance Gate in Verify Loop

```markdown
After fixing a performance issue:
1. Start the app (`make dev`)
2. Use chrome-devtools MCP: `performance_start_trace` on the target page
3. Check that LCP < 2.5s, CLS < 0.1
4. If failing, investigate with `performance_analyze_insight`
```

## Best Practices

- **Use snapshots over screenshots** — snapshots give `uid` values needed for interaction, and use fewer tokens
- **Re-snapshot after DOM changes** — `uid` values may shift
- **Use `list_pages` + `select_page`** when working with multiple tabs
- **Set reasonable timeouts** for `wait_for` — don't hang on slow elements
