# Pre-Tool Hooks for Copilot CLI

Extracted from [plankton](https://github.com/alexfazio/plankton) — these are the hooks that **actually work** with GitHub Copilot CLI today.

## Why only PreToolUse?

Copilot CLI hooks have a critical limitation: **only `preToolUse` output is processed** by the model. Specifically, only `permissionDecision: "deny"` is honored.

| Hook Event | Copilot CLI Behavior |
|---|---|
| `preToolUse` | ✅ `deny` blocks tool execution, reason shown to model |
| `postToolUse` | ❌ Output ignored — fire-and-forget only |
| `sessionStart/End` | ❌ Output ignored |
| `errorOccurred` | ❌ Output ignored |

PostToolUse hooks (linting, feedback) can still *log* to files, but the LLM never sees the results. That makes lint-detect-fix pipelines non-functional on Copilot CLI. PreToolUse guardrails are the real value.

## What's Included

| File | Lines | Purpose |
|---|---|---|
| `platform_shim.sh` | ~90 | Detects Claude Code vs Copilot CLI, normalizes tool names and JSON formats |
| `protect_linter_configs.sh` | ~90 | Blocks edits to linter config files (`.ruff.toml`, `biome.json`, etc.) |
| `enforce_package_managers.sh` | ~500 | Blocks legacy package managers (`pip` → `uv`, `npm` → `bun`, etc.) |
| `config.json` | — | Protected files list + package manager enforcement config |
| `copilot-hooks.json` | — | Drop-in `.github/hooks/` config for Copilot CLI |

## Setup

### For Copilot CLI (`.github/hooks/`)

```bash
# From your repo root
mkdir -p .github/hooks
cp platform_shim.sh protect_linter_configs.sh enforce_package_managers.sh .github/hooks/
cp config.json .github/hooks/
cp copilot-hooks.json .github/hooks/plankton.json
chmod +x .github/hooks/*.sh
```

### For Claude Code (`.claude/settings.json`)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": ".claude/hooks/protect_linter_configs.sh" }]
      },
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": ".claude/hooks/enforce_package_managers.sh" }]
      }
    ]
  }
}
```

Note: Claude Code supports matchers (hooks only fire for matching tools). Copilot CLI does not — the scripts filter internally via the platform shim.

## Configuration

Edit `config.json` to customize:

### `protected_files`
Array of filenames that agents cannot modify. Default includes common linter configs.

### `package_managers`
Per-language enforcement. Values: `"uv"`, `"bun"`, `"uv:warn"` (warn instead of block), or `false` (disabled).

```json
{
  "package_managers": {
    "python": "uv",
    "javascript": "bun"
  }
}
```

### `allowed_subcommands`
Read-only subcommands that bypass enforcement (e.g., `npm audit`, `pip download`).

## Dependencies

- `jaq` or `jq` — JSON parsing (scripts prefer `jaq`, fall back to `jq`)
- `bash` 4+

## Platform Shim

The shim auto-detects which agent platform is running based on the input JSON shape:

| | Claude Code | Copilot CLI |
|---|---|---|
| Tool name field | `tool_name` | `toolName` |
| Tool input field | `tool_input` (object) | `toolArgs` (JSON string) |
| Deny output | `{"decision": "block", "reason": "..."}` | `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` |
| Tool name casing | `edit`, `create`, `bash` | `edit`, `create`, `bash` (same) |

## Credit

Based on [plankton](https://github.com/alexfazio/plankton) by Alex Fazio. Platform shim and Copilot CLI support by [@bertclaws](https://github.com/bertclaws).
