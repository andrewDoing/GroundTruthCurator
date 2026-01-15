# Ground Truth Curator — Backend Codebase Guide (v2)

This document is a concise, skimmable map of the backend so you can read, run, test, and extend it quickly. It reflects the current code across app wiring, APIs, services, repositories, domain models, config, tests, and Docker packaging.

- Tech stack: FastAPI, Pydantic v2, httpx, uvicorn, pytest, Azure Cosmos DB (async SDK)
- Dependency manager: uv (virtualenv + lockfile)
- Python: 3.11

## Runtime entrypoints

- app/main.py
  - create_app() builds the FastAPI app (CORS intentionally omitted; handled via Azure Container Apps configuration), mounts the v1 API router, optional SPA static serving, and convenience redirects for docs.
  - lifespan() initializes the Cosmos repo (and tags repo) outside of test mode, seeds default tags, and ignores startup failures (emulator might not be ready yet).
  - GET /healthz returns repo/backend info (Cosmos details when active).
- app/container.py
  - Central wiring. Creates the repository instance and attaches services.
  - init_cosmos_repo() constructs the Cosmos repo and tags repo, then rebinds services to use them.
  - init_search() and init_llm() wire optional adapters when settings are present.

## High-level architecture

Layered with explicit composition:

- API layer: app/api/v1 routers expose HTTP endpoints under settings.API_PREFIX (default /v1).
- Services layer: app/services/*_service.py contain workflow logic (assignments, snapshots, tagging, curation, search, LLM).
- Repositories/adapters: app/adapters/repos/* implement the GroundTruthRepo protocol; Cosmos is the production backend. Tags repo is separate.
- Domain layer: app/domain/* defines Pydantic models, enums, and validators aligned to the wire schema (camelCase aliases).
- Core: app/core/* has configuration, auth, logging, and error helpers.
- Composition: app/container.py holds a singleton container used by routers/services.

Key conventions
- Pydantic v2 with aliases: accept snake_case or camelCase on input; always output camelCase via model_dump(..., by_alias=True).
- Concurrency uses ETag: updates require If-Match header or etag in body; 412 on missing/mismatch.
- Soft-delete via status=deleted; list APIs filter unless status is specified.

## Project layout (selected)

- app/
  - main.py — FastAPI factory, lifespan init, healthz, SPA serving.
  - container.py — wires repo + services; optional search/LLM wiring.
  - core/
    - config.py — pydantic-settings, GTC_ prefix; supports GTC_ENV_FILE overlays.
    - auth.py — dev auth via optional X-User-Id; Entra placeholder.
    - logging.py — sets logging and suppresses noisy SDK logs.
  - domain/
    - models.py — GroundTruthItem, Reference, HistoryItem, AssignmentDocument, Stats, DatasetCurationInstructions.
    - enums.py, validators.py, tags.py — enums, tag validation, default tag schema.
  - api/v1/
    - router.py — composes sub-routers under /v1.
    - ground_truths.py — import/list/get/update/delete GT items; snapshot exports.
    - assignments.py — self-serve assignments, list “my” assignments, SME update/approve.
    - stats.py, tags.py, datasets.py, schemas.py, search.py, answers.py — auxiliary endpoints.
  - services/
    - assignment_service.py, snapshot_service.py, curation_service.py, tag_registry_service.py, tagging_service.py, search_service.py, llm_service.py.
  - adapters/repos/
    - base.py — GroundTruthRepo protocol.
    - cosmos_repo.py — async Cosmos DB implementation for GT + assignments.
    - tags_repo.py — Cosmos repo for tag registry.
- Top-level
  - pyproject.toml — dependencies and tool configs (ruff, black, pytest).
  - Dockerfile — multi-stage build: Vite frontend then Python runtime using uv.
  - environments/*.env — committed defaults plus local overlays.
  - tests/ — unit, integration, and stress tests; dockerized smoke test.
  - exports/snapshots/ — snapshot outputs written by SnapshotService.
  - CODEBASE.md — earlier guide; this v2 augments it with current state.

## Configuration

Defined in app/core/config.py using pydantic-settings.
- Prefix: GTC_
- Default env file: environments/.dev.env from the repo root.
- Overlays: set GTC_ENV_FILE to a single path or a comma-separated list. Relative paths resolve from repo root. When not set, auto-detect and layer development.local.env and local.env if present.
- Notable settings:
  - ENV, API_PREFIX, LOG_LEVEL
  - AUTH_MODE (dev|entra)
  - REPO_BACKEND (memory|cosmos) — the app wires Cosmos in lifespan when configured.
  - Cosmos: COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DB_NAME, COSMOS_CONTAINER_GT, COSMOS_CONTAINER_ASSIGNMENTS, COSMOS_CONTAINER_TAGS, COSMOS_CREATE_IF_NOT_EXISTS, COSMOS_CONNECTION_VERIFY, COSMOS_TEST_MODE, USE_COSMOS_EMULATOR.
  - Azure Search: AZ_SEARCH_ENDPOINT, AZ_SEARCH_INDEX, AZ_SEARCH_KEY, AZ_SEARCH_API_VERSION.
  - LLM (Azure AI Foundry): AZ_FOUNDRY_*, LLM_ENABLED.
  - SPA: FRONTEND_DIR, FRONTEND_INDEX, FRONTEND_CACHE_SECONDS.
  - Sampling: SAMPLING_ALLOCATION CSV like datasetA:50,datasetB:50.

## Domain models (wire schema v1)

Key models in app/domain/models.py (selected fields):
- GroundTruthItem
  - Core: id, datasetName, bucket (UUID), status, docType, schemaVersion.
  - Curation: synthQuestion, editedQuestion, answer, refs[], tags[].
  - History: history[] with { role, msg }.
  - Provenance: contextUsedForGeneration, contextSource, modelUsedForGeneration.
  - Sampling: semanticClusterNumber, weight, samplingBucket, questionLength.
  - Audit/assignment: assignedTo, assignedAt, updatedAt, updatedBy, reviewedAt, _etag (alias etag).
- AssignmentDocument — secondary document for SME assignment tracking.
- DatasetCurationInstructions — dataset-level instructions stored in GT container with NIL UUID bucket.

Pydantic v2 config: populate_by_name=True. Prefer model_dump(mode="json", by_alias=True) when returning responses.

## API surface (selected)

Mounted at /v1 by default. See app/api/v1/router.py.

Ground-truths
- POST /v1/ground-truths — bulk import; optional ?buckets=N and ?approve=true to pre-approve.
- GET /v1/ground-truths/{datasetName} — list by dataset; optional status filter.
- GET /v1/ground-truths/{datasetName}/{bucket}/{item_id} — fetch one.
- PUT /v1/ground-truths/{datasetName}/{bucket}/{item_id} — update with ETag; supports edited_question, answer, status, refs, tags.
- DELETE /v1/ground-truths/{datasetName}/{bucket}/{item_id} — soft delete.
- POST /v1/ground-truths/snapshot — export approved items to exports/snapshots/<ts>.

Assignments (SME)
- POST /v1/assignments/self-serve — request N items; returns assigned, requested, assignedCount.
- GET /v1/assignments/my — list items still assigned to current user and in draft state.
- PUT /v1/assignments/{dataset}/{bucket}/{item_id} — SME update, approve/skip/delete with ETag enforcement.

Other routers
- stats, tags, datasets, schemas, search, answers exist under /v1 and are wired in router.py.

Auth
- Dev mode: get_current_user() reads X-User-Id header; anonymous becomes "anonymous".
- Entra mode is a placeholder; not yet implemented.

ETag concurrency
- Provide If-Match: <etag> header or include "etag": "..." in request body for updates.
- API returns 412 on missing or mismatch.

## Services overview

- AssignmentService
  - self_assign(user_id, limit) chooses unassigned draft/skipped GT items and assigns them.
  - Approve/delete flows delegate to repo updates; SME route clears assignment on approve/delete.
- SnapshotService
  - export_json() writes approved items to exports/snapshots/<timestamp>/ and returns summary.
- CurationService, TagRegistryService, TaggingService
  - Dataset instructions and tag management helpers.
- SearchService
  - Defaults to a no-op; wired to AzureAISearchAdapter when Azure Search env vars are set.
- LLMService
  - Defaults to a no-op; wired to Azure AI Foundry when enabled and configured.

## Repository contract and Cosmos notes

See app/adapters/repos/base.py for the repo protocol. Highlights:
- Ground-truths: import/list/get/upsert/soft-delete; dataset-level bulk delete; stats.
- Assignments: sample unassigned, assign to user, list by user; maintain separate assignment docs.

Cosmos implementation (cosmos_repo.py)
- Async SDK; _init() can create DB/containers when COSMOS_CREATE_IF_NOT_EXISTS=true.
- GT container uses MultiHash partition key [/datasetName, /bucket].
- Assignments and tags live in separate containers.
- Updates use ETag for concurrency; API translates mismatches to HTTP 412.

Known areas to watch
- For MultiHash PK, API calls that update/replace must provide partition key values; code does so using (datasetName, bucket) when applicable.
- Ensure emulator env vars are set for local/integration.

## Local development

- Install deps: uv sync
- Run API: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
- Health check: GET /healthz
- Cosmos Emulator (Docker) quickstart is covered in README.md (and VS Code tasks set env overlays for tests).

Environment overlays
- Default .env: environments/.dev.env.
- Optional overlays: development.local.env, local.env, or explicit GTC_ENV_FILE="envA,envB".

## Testing and quality gates

Use VS Code tasks under this workspace:
- Install deps: “Install Python deps with uv”
- Unit tests: “Run unit tests”
- Integration tests: “Run integration tests (integration env)”
- Large/stress: “Run large/stress integration tests (integration env)”
- Full suite: “Run tests”
- Mypy: “Run mypy”
- Container smoke test: “Run container smoke test” (builds image, runs container, verifies /healthz and frontend)

Manual equivalents (examples):
- uv run pytest -q tests/unit
- GTC_ENV_FILE="environments/integration-tests.env,environments/local.env" uv run pytest -q tests/integration
- uv run mypy --hide-error-codes --show-column-numbers .

Aim to keep: ruff clean, black formatted, mypy passing, tests green.

## Docker image

Dockerfile performs a two-stage build:
1) node:20-alpine builds the frontend with Vite into /work/frontend/dist.
2) python:3.11-slim installs uv, syncs locked deps (no dev), copies backend app, and copies the frontend dist to /app/frontend_dist.

Runtime
- CMD sh -c 'uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers'
- Env var GTC_FRONTEND_DIR is preset to /app/frontend_dist so the app can serve the SPA.

## Adjacent references

- Prior guide: CODEBASE.md
- Setup/how-to: README.md
- Planning docs: docs/
- Environment examples: environments/

## Quick contracts (cheat sheet)

- Update GT item
  - Inputs: datasetName, bucket (UUID), item_id, JSON body with changes; ETag via If-Match or body.
  - Success: 200 with updated item (fresh etag), or 412 on mismatch/missing.
- Self-serve assignments
  - Input: { "limit": <int> } body.
  - Success: 200 with { assigned: GroundTruthItem[], requested, assignedCount }.
- Snapshot export
  - Input: none.
  - Success: 200 { status: "ok", ... } and files under exports/snapshots/<timestamp>/.

## What to implement next (common tasks)

- Add a field to GroundTruthItem: update model with alias, touch repo projections, update API/service, add tests.
- New endpoint: create app/api/v1/<feature>.py, include in router.py, add tests, update docs.
- New repo backend: implement GroundTruthRepo, add selection in container.py, ensure ETag/soft-delete semantics, add tests.

---

Questions or gaps you spot while working? Add clarifications to this file alongside your changes so it stays authoritative.
