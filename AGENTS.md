# AGENTS.md

Ground Truth Curator is a monorepo for curating high-quality ground truth datasets for agent evaluation and model accuracy measurement. The backend is FastAPI/Python, the frontend is React/TypeScript, and the production data plane is centered on Azure services such as Cosmos DB, Blob Storage, Search, and Azure AI.

## Project Overview

- Project: `Ground Truth Curator`
- Primary runtimes: Python 3.11 (`backend/`) and Node.js 20 (`frontend/`)
- Main entrypoints: backend FastAPI app at `backend/app/main.py`, frontend Vite app at `frontend/src/main.tsx`

## Harness Commands

Run from repository root:

| Goal | Command |
|---|---|
| Install dependencies | `make -f Makefile.harness setup` |
| Start backend dev server | `make -f Makefile.harness backend` |
| Start frontend dev server | `make -f Makefile.harness frontend` |
| Start both dev servers (foreground) | `make -f Makefile.harness dev` |
| Start both dev servers (background) | `make -f Makefile.harness dev-up` |
| Stop background dev servers | `make -f Makefile.harness dev-down` |
| Auto-format code | `make -f Makefile.harness format` |
| Fast sanity check | `make -f Makefile.harness smoke` |
| API contract and generated types | `make -f Makefile.harness api-check` |
| Static checks | `make -f Makefile.harness check` |
| Full test suite | `make -f Makefile.harness test` |
| Backend integration tests | `make -f Makefile.harness backend-integration-test` |
| CI-equivalent local run | `make -f Makefile.harness ci` |
| Backend deploy | `make -f Makefile.harness deploy` |
| CI + telemetry review | `make -f Makefile.harness verify` |

Use `dev` for interactive local work, and `dev-up` / `dev-down` when an agent or developer needs the servers managed in the background. Background PID files and logs live under `.harness/dev/`.
Run GitLab deploy pipelines with `DEPLOY_BACKEND=true`, `DEPLOYMENT_TARGET_NAME=<environment>`, and either `TAG_NAME=<image-tag>` or `CONTAINER_IMAGE=<full-image>`, plus environment-scoped Azure and `GTC_*` deploy variables.

### Demo Mode

To start dev servers with in-memory demo data (no Cosmos dependency):

```bash
VITE_DEMO_MODE=true VITE_DEV_USER_ID=demo-user make dev-up
```

If you prefer a single shortcut target with the same stable demo identity, use:

```bash
make -f Makefile.harness dev-up-demo
```

The `sample.env` sets `GTC_REPO_BACKEND=cosmos` by default. To force the in-memory backend (e.g. when no Cosmos emulator is running), add `GTC_REPO_BACKEND=memory`:

```bash
GTC_REPO_BACKEND=memory VITE_DEMO_MODE=true VITE_DEV_USER_ID=demo-user make dev-up
```

## Backend Commands

Run from `backend/`:

| Goal | Command |
|---|---|
| Install deps | `uv sync` |
| Dev server | `uv run uvicorn app.main:app --reload` |
| Test (all) | `uv run pytest tests/unit/ -v` |
| Test (integration) | `uv run pytest tests/integration/ -v` |
| Test (single) | `uv run pytest tests/unit/test_dos_prevention.py -v` |
| Test (keyword) | `uv run pytest tests/unit/ -k "bulk" -v` |
| Type check | `uv run ty check app/` |
| Lint | `uv run ruff check app/` |
| Docs build | `uv run mkdocs build -f ../mkdocs.yml` |

## Frontend Commands

Run from `frontend/`:

| Goal | Command |
|---|---|
| Install deps | `npm install` |
| Dev server | `npm run dev` |
| Test (all) | `npm run test:run -- --pool=threads --poolOptions.threads.singleThread` |
| Build | `npm run build` |
| Type check | `npm run typecheck` |
| Lint (check) | `npm run lint:check` |
| Lint (fix) | `npm run lint` |
| Pre-commit | `npm run pre-commit` |

## Frontend React Guidance

- For React and TypeScript work in `frontend/`, consult `.github/skills/react-best-practices/SKILL.md` and `.github/skills/react-best-practices/APPLICABILITY.md`.
- This frontend is a Vite + React app, not Next.js.
- Apply framework-agnostic React, re-render, rendering, bundle, and JavaScript performance rules normally.
- Translate `next/dynamic` guidance to `React.lazy()` or gated `import()` patterns instead of copying Next.js examples directly.
- Treat Next.js-only rules (`async-api-routes`, `server-*`, API routes, server actions, `after()`, and other server-only guidance) as not applicable unless the stack changes.
- Treat SWR-specific guidance as reference-only; current frontend data access uses `fetch` / `openapi-fetch` helpers under `frontend/src/api/` and `frontend/src/services/`.

## Debugging Loop

When `make -f Makefile.harness ci` fails, identify the stage before changing code blindly.

1. `smoke` failed: the backend did not start cleanly, the health probes failed, or the harness telemetry files were not produced.
2. `check` failed: run the backend/frontend lint or typecheck command directly to isolate the failing side.
3. `test` failed: run the backend and frontend test commands directly and inspect the failing suite.
4. `verify` shows warnings/errors: inspect `.harness/logs.jsonl` and `.harness/traces.jsonl` with `jq` before rerunning.

## Constraints And Guardrails

- Preserve the backend layering: `api/v1 -> services -> adapters`.
- Do not import adapters directly from FastAPI route modules.
- Domain models belong in `backend/app/domain/`, not in route handlers or React components.
- Frontend network calls belong in `frontend/src/api/` or `frontend/src/services/`, not in presentational components.
- Regenerate frontend API types when backend API schemas change: `cd frontend && npm run api:types`.
- Do not modify `infra/` without explicit user direction.
- Treat `scripts/harness/` and `Makefile.harness` as operational code: change them only when the repo workflow actually changes.
- Backend deploys use `scripts/harness/deploy_backend.sh` (via `make -f Makefile.harness deploy` locally) and expect Azure/auth/runtime values from CI/CD variables rather than repo-side deployment env files.

## Architecture Boundaries

- `backend/app/api/v1/` owns HTTP parsing, status codes, and response shapes.
- `backend/app/services/` owns orchestration and business workflows.
- `backend/app/adapters/` owns external I/O: Cosmos DB, Search, Blob Storage, inference, and similar integrations.
- `backend/app/domain/` owns typed request/response/data models shared across backend layers.
- `backend/app/plugins/` owns computed-tag extensions and registry-driven enrichment.
- `frontend/src/api/` owns typed backend communication, while `frontend/src/components/` owns rendering and interaction.

See `docs/ARCHITECTURE.md` before changing cross-layer behavior.

## Observability Convention

- Local harness runs emit JSONL request logs to `.harness/logs.jsonl` and request traces to `.harness/traces.jsonl`.
- The backend keeps Azure Monitor / OpenTelemetry support for deployed environments; harness JSONL is the local agent-facing mirror.
- Request level policy is `INFO` for 2xx, `WARN` for 4xx, and `ERROR` for 5xx or unhandled exceptions.
- `make -f Makefile.harness verify` reads the last runtime errors and slow traces with `jq`.

See `docs/OBSERVABILITY.md` for field names, examples, and query patterns.

## Execution Plans

- Use `PLANS.md` for multi-step work that spans investigation, implementation, and verification.
- Capture the objective, non-goals, relevant files, risks, and the exact commands that prove the work is done.
- Refresh the plan when scope changes so a restarted agent can pick up quickly.

## Static Analysis And Quality Gates

- Run `make -f Makefile.harness format` before committing code changes.
- Run `make -f Makefile.harness check` before `make -f Makefile.harness test`.
- Backend quality gate: `uv run ruff check app/` and `uv run ty check app/`.
- Frontend quality gate: `npm run lint:check` and `npm run typecheck`.
- Test gate: backend unit tests plus frontend Vitest suite must pass.
- Smoke gate: backend must boot locally, respond on `/healthz`, answer `/v1/openapi.json`, and emit `.harness` telemetry.

## Known Gotchas

- Backend type checking uses `ty`, not mypy.
- Frontend linting uses Biome, not ESLint.
- Frontend unit tests should use `--pool=threads --poolOptions.threads.singleThread` in agent automation.
- The backend defaults to `REPO_BACKEND=memory`, which keeps local smoke checks self-contained.
- `.harness/` is intentionally ephemeral and should never be committed.
