# Init Agent-Native

> **Purpose:** Make this repository agent-native — structured so any AI coding agent can work in it effectively.
> **Usage:** Run `/init-agent-native` in Copilot Chat, or feed this file to any agent CLI.

---

## Prompt

You are setting up agent-native infrastructure for this repository. This gives AI agents clear instructions, observable execution, verifiable quality gates, and architectural guardrails.

### Step 1: Bootstrap

Run the bootstrap script from the agent-native skill:

```bash
bash .agents/skills/agent-native/scripts/bootstrap_harness.sh .
```

Read the output carefully — it tells you what to do next, in order.

### Step 2: Build or identify the app

If there's already an app in this repo, skip to Step 3.

If you're also building the app, build it now. The bootstrap output assumes an app exists when you customize the harness.

### Step 3: Follow the bootstrap instructions

The bootstrap printed numbered steps. Follow them in order:

1. **Read AGENTS.md** — it tells you what to customize and what conventions to follow
2. **Read docs/OBSERVABILITY.md** — follow the Level Policy (2xx=INFO, 4xx=WARN, 5xx=ERROR) and implement hlog()/htrace() per the language examples
3. **Customize docs/ARCHITECTURE.md** — replace ALL placeholders with real project info, add at least one lint rule for boundary enforcement
4. **Fill in scripts/harness/*.sh** — the auto-detect should work for most projects, but verify each script runs successfully
5. **Add observability to the app** — hlog() for structured logs, htrace() for request traces (see language examples in OBSERVABILITY.md)
6. **Verify CI passes:** `make -f Makefile.harness ci`
7. **Verify customization:** `scripts/verify_customized.sh .`
8. **Run audit:** `scripts/audit_harness.sh .`

### Step 4: Verify observability end-to-end

Start the app, make a few requests including one that returns a 404, then check:

```bash
# Should see WARN entries for 4xx, ERROR for 5xx
jq 'select(.level == "WARN" or .level == "ERROR")' .harness/logs.jsonl

# Should see trace entries with duration_ms
jq 'select(.duration_ms > 0)' .harness/traces.jsonl
```

### Step 5: Final check

Run all three verification commands. All must pass:

```bash
make -f Makefile.harness ci
scripts/verify_customized.sh .
scripts/audit_harness.sh .
```

### What you're installing

| Artifact | Purpose |
|---|---|
| `AGENTS.md` | Agent instructions — commands, constraints, conventions |
| `docs/ARCHITECTURE.md` | Module boundaries + lint rules to enforce them |
| `docs/OBSERVABILITY.md` | Structured logging convention (JSONL, level policy) |
| `Makefile.harness` | Stable command surface: `make smoke`, `make check`, `make ci` |
| `scripts/harness/` | Real scripts behind the Makefile (smoke, test, lint, typecheck) |
| `.harness/` | Runtime observability data (logs.jsonl, traces.jsonl) |
| `scripts/verify_customized.sh` | Catches leftover template boilerplate |
| `scripts/audit_harness.sh` | Checks for structural gaps |

### Key conventions

- **Level Policy:** 2xx → INFO, 4xx → WARN, 5xx/exceptions → ERROR
- **Two output files:** `.harness/logs.jsonl` (structured logs) and `.harness/traces.jsonl` (request traces with duration_ms)
- **Required log fields:** `ts`, `level`, `msg`, `service`
- **Required trace fields:** `trace_id`, `span_id`, `name`, `service`, `start`, `end`, `duration_ms`, `status`
- **Minimum tests:** At least 5 meaningful tests covering core operations
- **smoke.sh must:** start the server → poll health → make a request → kill the server
