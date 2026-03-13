# AGENTS.md

> **CUSTOMIZE THIS FILE** — replace all `<placeholder>` values with real project info.
> Read `docs/OBSERVABILITY.md` and `docs/ARCHITECTURE.md` before writing code.

## Project Overview

- Project: `<project-name>`
- Primary runtime(s): `<runtime>`
- Main entrypoint(s): `<entrypoints>`

## Harness Commands

Run from repository root:

| Goal | Command |
|---|---|
| Install dependencies | `make setup` |
| Auto-format code | `make format` |
| Fast sanity check | `make smoke` |
| Static checks | `make check` |
| Full test suite | `make test` |
| CI-equivalent local run | `make ci` |

## Debugging Loop

When `make ci` fails, don't just re-run and hope. Read the error, fix the cause, then verify.

1. **Identify which stage failed** — `make ci` runs `smoke → check (lint + typecheck) → test`. Check which one errored.

2. **Lint fails** → run `make format` first (auto-fixes formatting), then re-run `make check`. If it still fails, read the linter output — it tells you exactly which file and rule.

3. **Typecheck fails** → read the error output carefully. It gives you the file, line number, and expected types. Fix the specific issue; don't suppress the error.

4. **Test fails** → check `.harness/logs.jsonl` for runtime errors (`jq 'select(.level == "ERROR")' .harness/logs.jsonl`). Read the test output for assertion details — which test, what was expected vs actual.

5. **Smoke fails** → the app didn't start or respond. Common causes:
   - Missing dependencies → run `make setup`
   - Port conflict → check if something else is on the port
   - Wrong start command → check `HARNESS_SMOKE_START_CMD` or `scripts/harness/smoke.sh`
   - For non-server projects, set `HARNESS_SMOKE_MODE` to `cli`, `library`, or `auto`

6. **General** — read the actual error message. Fix the root cause. Then run `make ci` again to confirm the fix didn't break something else.

## Constraints And Guardrails

- Prefer deterministic scripts over interactive/manual steps.
- Keep command names stable (`setup`, `format`, `smoke`, `check`, `test`, `ci`).
- Update docs and scripts in the same change when workflow behavior changes.
- Avoid side effects outside the repo unless explicitly required.

## Architecture Boundaries

- Parse and validate external data at boundaries.
- Keep internal data models typed and normalized.
- Keep each module focused on one responsibility.
- **Enforce boundaries with lint rules** (see `docs/ARCHITECTURE.md` for examples).
- Customize `docs/ARCHITECTURE.md` with real module boundaries and execution flow — do not leave template boilerplate.

## Observability Convention

**Read `docs/OBSERVABILITY.md` for the full logging convention.**

Key rules:
- All structured logs write to `.harness/logs.jsonl`, traces to `.harness/traces.jsonl`
- Generate a `trace_id` per request and propagate it through context
- Track `duration_ms` per request
- **Level policy:** 2xx → INFO, 4xx → WARN, 5xx/exceptions → ERROR
- Required fields: `ts`, `level`, `msg`, `service`
- Customize `docs/OBSERVABILITY.md` with project-specific endpoint examples

## Execution Plans

- For tasks expected to exceed ~30 minutes, create/update `PLANS.md` before coding.
- Track scope, constraints, milestones, and verification steps.

## Static Analysis And Quality Gates

- Run `make check` before `make test`.
- Run `make ci` before pushing large refactors.
- Treat lint/type failures as blocking.
- **Minimum test coverage:** at least 5 meaningful tests covering core operations (CRUD, error cases, edge cases). Tests must verify real behavior, not just "assert True".

## Entropy Management

- Remove stale scripts/docs quickly.
- Keep templates and real workflows in sync.
- **Before considering setup complete, run:** `scripts/verify_customized.sh .` — it catches leftover template placeholders, stub scripts, and missing observability wiring.
- Run periodic harness audits: `scripts/audit_harness.sh .`
