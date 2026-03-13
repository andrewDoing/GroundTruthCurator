---
name: harness-engineering-playbook
description: Bootstrap any repository with agent-first harness engineering — deterministic commands, structured JSONL observability, compact docs, and strict boundaries. Use when setting up or improving a repo for coding agent workflows. Default observability is JSONL + jq (zero deps); devtel is the upgrade path.
---

# Harness Engineering Playbook

Operationalize OpenAI's Harness Engineering practices in any repo so coding agents can run against it repeatedly and safely.

## Quick Start

```bash
# Bootstrap a repo
./scripts/bootstrap_harness.sh /path/to/repo

# Or from within the repo
./scripts/bootstrap_harness.sh .
```

This creates:
- `AGENTS.md` — agent-facing docs (commands, constraints, guardrails, debugging loop)
- `PLANS.md` — durable planning context for multi-step tasks
- `docs/ARCHITECTURE.md` — module boundaries and data flow
- `docs/OBSERVABILITY.md` — JSONL logging convention + jq query patterns
- `Makefile.harness` — `make setup`, `make format`, `make smoke`, `make check`, `make ci`
- `scripts/harness/` — deterministic wrappers (setup, format, smoke, test, lint, typecheck)
- `.harness/` — JSONL telemetry files + jq query library (gitignored)
- `.github/workflows/harness.yml` — CI integration

## What To Load

- `references/openai-harness-practices.md` — full practice-to-artifact mapping
- `references/static-analysis.md` — linter recommendations per language + agent-friendly output patterns
- `references/agent-hooks/` — lifecycle hooks for agent automation (format, lint, audit, safety)
  - `copilot-hooks/` — GitHub Copilot (VS Code, CLI, coding agent) hook config + recipes
  - _(add claude-code/, cursor/, etc. as needed)_
- `references/browser-tools/` — browser automation and debugging for runtime verification
  - `playwright-cli/` — CLI for navigate, interact, snapshot, screenshot (primary tool)
  - `chrome-devtools-mcp/` — MCP server for deep debugging, perf profiling, network analysis
- `references/rollout-checklist.md` — phased adoption for active repos
- `assets/templates/` — all template files

## The Nine Practices

### 1. Make Easy To Do Hard Thing
One command for every high-value task: `make setup`, `make format`, `make smoke`, `make check`, `make ci`. No manual prep.

### 2. Communicate Actionable Constraints With Compact Docs
`AGENTS.md` — short, concrete, command-first. Not narrative prose.

### 3. Structure Codebase With Strict Boundaries And Flow
`docs/ARCHITECTURE.md` — clear module boundaries, typed contracts, parse at edges.

### 4. Build Observability In From Day 1
**Default: JSONL + jq** (zero dependencies, any language).

```bash
# Your app appends structured JSON to .harness/logs.jsonl:
{"ts":"...","level":"ERROR","msg":"timeout","service":"api","trace_id":"abc"}

# Agent queries with jq:
jq 'select(.level == "ERROR")' .harness/logs.jsonl
jq --arg tid abc 'select(.trace_id == $tid)' .harness/logs.jsonl .harness/traces.jsonl

# Pre-built queries in .harness/queries/:
jq -f .harness/queries/errors.jq .harness/logs.jsonl
jq --argjson threshold 500 -f .harness/queries/slow.jq .harness/traces.jsonl
```

**Upgrade to devtel** when you need joins, aggregations, auto-instrumentation, or 100K+ events:
```bash
npm install devtel && npx devtel init
# import "devtel/init" in app entry point
npx devtel logs --level error --last 5m
```

See `docs/OBSERVABILITY.md` for full logging convention, field names, and language examples.

### 5. Optimize For Agent Flow, Not Human Flow
`PLANS.md` for multi-step tasks. Front-load context so restarts are cheap.

### 6. Bring Your Own Harness
Repo-local wrappers in `scripts/harness/`. Same commands work locally and in CI.

### 7. Prototype In Natural Language First
Draft logic and tests in prose in `PLANS.md` before coding.

### 8. Invest In Static Analysis And Linting
`make check` (lint + typecheck) runs before `make test`. Fast-fail on static errors.

See `references/static-analysis.md` for per-language tool recommendations (ESLint, Ruff, golangci-lint, Biome, MegaLinter for monorepos) and agent-friendly JSON output patterns.

### 9. Manage Entropy
`scripts/audit_harness.sh` catches docs drift, stale scripts, missing artifacts.

## Workflow

1. **Baseline** — inventory the repo's existing commands, CI, and pain points
2. **Bootstrap** — `bootstrap_harness.sh` installs templates (won't overwrite existing files)
3. **Read the output** — bootstrap prints next steps; follow them in order
4. **Customize docs** — AGENTS.md, docs/ARCHITECTURE.md (replace ALL placeholders), docs/OBSERVABILITY.md
5. **Install deps** — `make setup` auto-detects and installs dependencies (override with `HARNESS_SETUP_CMD`)
6. **Fill in scripts** — `scripts/harness/*.sh` with real project commands (not stubs)
7. **Add observability** — implement `hlog()` per the language example in docs/OBSERVABILITY.md; follow the Level Policy
8. **Validate** — `make -f Makefile.harness ci` must pass; `scripts/verify_customized.sh .` catches leftover boilerplate; `scripts/audit_harness.sh .` checks for gaps
9. **Iterate** — observe an agent run, patch gaps, re-audit

## Agent Verify Loop

After any code change, the agent should:

```bash
make ci                                          # lint + typecheck + test
jq 'select(.level == "ERROR" or .level == "WARN")' .harness/logs.jsonl | tail -5   # check for runtime errors
jq 'select(.duration_ms > 1000)' .harness/traces.jsonl | tail -5  # check for regressions
```

If errors or slow traces appear → fix and re-run. When clean → commit.

## Adaptation Rules

- Preserve existing project conventions; replace templates incrementally
- Don't overwrite user-authored files without explicit approval
- Keep command names stable; change internals behind wrappers
- Favor deterministic, scriptable workflows over ad-hoc interactive steps
