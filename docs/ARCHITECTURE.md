# Architecture

## Purpose

Ground Truth Curator is a monorepo for curating, reviewing, and exporting high-quality ground truth items. The backend owns HTTP APIs, orchestration, and persistence. The frontend owns curator workflows, typed API access, and the browser editing experience.

## Entrypoints

- **Backend app:** `backend/app/main.py`
  - `create_app()` builds the FastAPI application.
  - Mounts the versioned API under `/v1`.
  - Exposes `/healthz`.
  - Installs auth, request logging, and optional harness JSONL middleware.
  - Optionally serves the built SPA when `GTC_FRONTEND_DIR` points at a frontend dist folder.
- **Frontend app:** `frontend/src/main.tsx`
  - Initializes frontend telemetry.
  - Renders `App`, which currently renders `GTAppDemo`.
  - Uses the Vite dev server and proxies `/v1` to the backend during local development.

## Boundaries

| Boundary | Input | Output | Owner |
|---|---|---|---|
| Browser shell | Browser route and user interaction | React component tree rooted at `src/main.tsx` | `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/demo.tsx` |
| Frontend state and workflow orchestration | UI events, runtime config, provider responses | Editable `GroundTruthItem` state, save/approve/delete actions | `frontend/src/hooks/useGroundTruth.ts` |
| Frontend API access | Typed method calls from hooks/providers | HTTP requests to `/v1` and mapped frontend models | `frontend/src/api/`, `frontend/src/services/`, `frontend/src/adapters/` |
| HTTP API boundary | FastAPI request, headers, path params, JSON body | Status code + JSON response under `/v1` | `backend/app/api/v1/` |
| Service orchestration | Typed request data from routers | Business workflow calls into repositories/adapters | `backend/app/services/` |
| Persistence and external integrations | Service requests | Ground truth records, assignments, tags, search, inference side effects | `backend/app/adapters/` |
| Domain contracts | External data normalized at edges | Typed backend models and validators | `backend/app/domain/` |
| Plugin enrichment | Registry-driven tag or workflow extensions | Computed tags and plugin-owned behavior | `backend/app/plugins/` |
| Local observability mirror | Completed request context | JSONL entries in `.harness/logs.jsonl` and `.harness/traces.jsonl` | `backend/app/core/harness_observability.py` |

## Request And Data Flow

1. **Frontend boot**
   - Vite loads `frontend/src/main.tsx`.
   - Frontend telemetry initializes before the React tree renders.
   - `App` renders `GTAppDemo`.
2. **Provider selection**
   - `useGroundTruth()` chooses a provider.
   - Demo flows use `JsonProvider` when `VITE_DEMO_MODE` / `DEMO_MODE` is active in supported builds.
   - Normal flows use `ApiProvider`.
3. **Frontend to backend**
   - `ApiProvider` calls typed service helpers in `frontend/src/services/`.
   - The Vite dev server proxies `/v1` to `HARNESS_BACKEND_URL` or `http://localhost:8000`.
   - Runtime UI switches such as approval requirements and self-serve limits come from `/v1/config`, with environment fallback when the backend is unavailable.
4. **HTTP parse and routing**
   - `backend/app/main.py` includes `api_router` under `settings.API_PREFIX` (default `/v1`).
   - Route modules in `backend/app/api/v1/` own request parsing, status codes, auth dependencies, and response shapes.
5. **Service orchestration**
   - Route modules call container-wired services in `backend/app/services/`.
   - Services apply workflow rules such as assignment handling, snapshot export, tagging, search, and curation behavior.
6. **Persistence and integrations**
   - Services call repository or adapter implementations in `backend/app/adapters/`.
   - The local default is memory-backed data for harness-friendly smoke runs.
   - Production-oriented integrations include Cosmos DB, Azure AI Search, Blob-backed assets, and optional LLM/inference adapters when configured.
7. **Return path**
   - Backend responses serialize typed models in the wire schema expected by the frontend.
   - `ApiProvider` maps API payloads into frontend models and preserves ETag metadata for retry-on-`412` flows.
   - The React tree updates queue state, editor state, and stats views from provider results.
8. **Observability**
   - When `GTC_HARNESS_JSONL_ENABLED=true`, backend middleware writes one log record and one trace record per HTTP request to `.harness/`.
   - Deployed environments may also emit Azure Monitor / OpenTelemetry telemetry, but `.harness/*.jsonl` is the local agent-facing contract.

## Guardrails

- Preserve the backend layering: `api/v1 -> services -> adapters`.
- Do not import adapters directly from FastAPI route modules.
- Keep backend domain models in `backend/app/domain/`; do not redefine backend data contracts in route handlers.
- Keep frontend network calls in `frontend/src/api/` or `frontend/src/services/`, not in presentational components.
- Keep provider-specific mapping logic in `frontend/src/adapters/`; components should consume normalized frontend models.
- Regenerate frontend API types when backend schema changes: `cd frontend && npm run api:types`.
- Respect ETag concurrency for update paths. Backend updates can return `412`; frontend retry logic belongs in the provider/service boundary, not in components.
- Use `/v1/config` or centralized config helpers for runtime switches instead of scattering direct environment reads through feature code.
- Do not modify `infra/` or deployment mechanics unless the workflow itself is changing and the task explicitly asks for it.

## Backend And Frontend Ownership

### Backend owns

- HTTP routing, auth enforcement, OpenAPI generation, and request lifecycle middleware.
- Assignment, curation, tagging, snapshot, search, and inference orchestration.
- Persistence backends and Azure-facing adapters.
- Local harness JSONL emission for request logs and traces.

### Frontend owns

- Queue, editor, evidence review, stats, and workflow interactions.
- Provider selection between demo and real API flows.
- Typed API consumption and ETag-aware save behavior.
- Client-side telemetry initialization and UI error boundaries.

## Data Shape Contracts

- Parse and validate external HTTP input at the API boundary.
- Normalize backend data into typed domain models before service-layer use.
- Keep wire-shape transformations centralized:
  - backend: route parsing + domain models
  - frontend: `src/adapters/apiMapper.ts`, service helpers, and provider mapping
- Preserve the backend camelCase wire contract expected by the generated frontend API types.

## Enforcing Boundaries With Static Analysis

Architecture docs help humans. Static analysis keeps the guardrails enforceable.

### Existing quality gates

- Backend lint: `cd backend && uv run ruff check app/`
- Backend typecheck: `cd backend && uv run ty check app/`
- Frontend lint: `cd frontend && npm run lint:check`
- Frontend typecheck: `cd frontend && npm run typecheck`
- Repo wrapper: `make -f Makefile.harness check`

### Concrete next enforcement to add

Add a backend import-boundary contract so the repo fails fast when cross-layer shortcuts appear.

Recommended contract:

- `app.domain` must not import from `app.api.v1`
- `app.services` must not import from `app.api.v1`
- `app.adapters` must not import from `app.api.v1`

Example using `import-linter`:

```toml
[tool.importlinter]
root_packages = ["app"]

[[tool.importlinter.contracts]]
name = "Backend layers must not depend on api.v1"
type = "forbidden"
source_modules = ["app.domain", "app.services", "app.adapters"]
forbidden_modules = ["app.api.v1"]
```

Wire it into the existing harness after Ruff in `scripts/harness/lint.sh` so it runs in `make -f Makefile.harness check` and `make -f Makefile.harness ci`.

## Change Checklist

- [ ] Boundary ownership still matches `backend/app/` and `frontend/src/`
- [ ] API schema changes are reflected in regenerated frontend types
- [ ] New data transformations live at boundaries, not in components or route glue
- [ ] New cross-layer imports are covered by lint or typecheck rules
- [ ] Observability behavior changes are documented in `docs/OBSERVABILITY.md`
