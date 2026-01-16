# Ground Truth Curation — FastAPI Backend Implementation Plan (MVP)

This plan turns the Ground Truth Curation MVP requirements into a concrete, staged FastAPI backend implementation that’s easy to run locally and ready to integrate with Azure services. We’ll start with a clean app skeleton, clear contracts, and tight feedback loops before wiring full Azure integrations.

Source of truth for requirements: `../docs/ground-truth-curation-reqs.md` (provided separately).


## Goals (for this plan)

- Stand up an initial Python FastAPI service aligned with the MVP endpoints and data model.
- Use a local venv and uv-managed dependencies for speed and reproducibility.
- Provide stubs/interfaces for Azure integrations (Cosmos DB, Blob Storage, Entra ID JWT validation, AI Search) that can be swapped from in-memory to Azure implementations without changing API contracts.
- Ship in small, verifiable phases with unit tests and a minimal smoke test.


## Assumptions and scope (initial)

- Python 3.11+.
- Local development will run without Azure credentials by default, using in-memory repositories and relaxed auth in “dev mode”.
- Auth: We’ll validate Microsoft Entra ID JWTs in non-dev modes using JWKS; dev mode can accept a static test token or skip validation behind a feature flag.
- Data model will follow the conceptual schema and evolve with migrations as needed.
- Cosmos DB will use hierarchical partition keys: `/datasetName`, `/bucket`.
- Snapshot/export produces JSON (one JSON per item + manifest) in Blob Storage; for dev it writes to local filesystem first, then we add Blob.


## High-level architecture

- FastAPI app with versioned API under `/v1`.
- Layered modules:
  - api: routers, request/response schemas, validation.
  - domain: pydantic models, business rules.
  - services: orchestration (assignment selection, snapshot/export, tagging, search attach/detach, LLM answer gen facade).
  - adapters: ports for storage and external systems with two implementations each:
    - in-memory (dev)
    - Azure (Cosmos, Blob, AI Search, Entra JWT validation)
  - core: config, logging, error handling, auth middleware.


## Project layout

```
backend/
  app/
    main.py
    core/
      config.py
      logging.py
      auth.py
      errors.py
    api/
      v1/
        __init__.py
        router.py
        assignments.py              # SME self-serve + update/approve
        ground_truths.py            # curator CRUD + snapshot/export
        stats.py                    # basic counts
    domain/
      models.py                     # GroundTruthItem, Reference, Assignment, Stats
      enums.py                      # status enums, doc types
    services/
      assignment_service.py
      snapshot_service.py
      tagging_service.py
      search_service.py             # AI Search attach/detach
      llm_service.py                # generate answer (stub initially)
    adapters/
      repos/
        base.py                     # repository interfaces
        memory_repo.py              # in-memory impl
        cosmos_repo.py              # cosmos impl (later)
      storage/
        base.py
        local_fs.py                 # dev export target
        blob_storage.py             # azure blob (later)
      search/
        base.py
        noop_search.py              # dev no-op
        azure_search.py             # azure ai search (later)
      auth/
        dev_allow_all.py            # dev mode
        entra_jwt.py                # JWKS validation
  tests/
    unit/
      test_health.py
      test_assignments.py
      test_ground_truths.py
    integration/ (later)
  docs/
    fastapi-implementation-plan.md
  pyproject.toml
  README.md
```


## Runtime dependencies (initial)

- fastapi
- uvicorn[standard]
- pydantic >= 2, pydantic-settings (for typed config)
- httpx (JWKS fetch + outbound calls)
- python-jose[cryptography] (JWT validation)
- typing-extensions (if needed on older 3.11.x)

Azure integrations (add when wiring cloud):
- azure-cosmos
- azure-storage-blob
- azure-identity (managed identity/client creds)
- azure-search-documents
- opentelemetry-instrumentation-fastapi, opentelemetry-sdk, azure-monitor-opentelemetry-exporter (observability; optional in phase 2+)

Dev/tooling:
- pytest, pytest-asyncio
- ruff (lint), black (format)
- ty (type check)

Note: We’ll use uv to manage these in `pyproject.toml` with a `dev` dependency group.


## Environment and configuration

Centralized with pydantic-settings; environment variables (prefix `GTC_`):

- App
  - GTC_ENV: dev|test|prod (controls adapter selection)
  - GTC_API_PREFIX: default "/v1"
  - GTC_LOG_LEVEL: info|debug|warning
- Auth
  - GTC_AUTH_MODE: dev|entra
  - GTC_ENTRA_TENANT_ID
  - GTC_ENTRA_AUDIENCE (API application ID URI or client ID)
  - GTC_ENTRA_ISSUER (https://login.microsoftonline.com/{tenantId}/v2.0)
- Cosmos
  - GTC_COSMOS_ENDPOINT
  - GTC_COSMOS_KEY (dev only; use managed identity in prod)
  - GTC_COSMOS_DB_NAME
  - GTC_COSMOS_CONTAINER_GT: ground_truth
  - GTC_COSMOS_CONTAINER_ASSIGN: assignments
- Blob
  - GTC_BLOB_ACCOUNT_URL
  - GTC_BLOB_CONTAINER: snapshots
- Search
  - GTC_SEARCH_ENDPOINT
  - GTC_SEARCH_KEY
  - GTC_SEARCH_INDEX
- LLM (stub first)
  - GTC_LLM_PROVIDER
  - GTC_LLM_DEPLOYMENT

All secrets via environment or dev `.env` (excluded from VCS).


## AuthN/AuthZ approach

- Dev mode: simple header-based user identity (e.g., `X-User-Id`) or static JWT bypass; role set via config.
- Entra mode: Bearer token required; middleware validates:
  - `iss` matches tenant issuer
  - `aud` contains configured audience
  - `exp`/`nbf` checks
  - Signature verified via JWKS (cached)
- Authorization:
  - SME vs Curator derived from `roles`/`scp` claims; minimal role check at router level where needed.


## Data model (pydantic)

Key entities:
- GroundTruthItem
- Reference
- AssignmentDocument (SME assignment doc)
- Stats

Cosmos partitioning:
- ground_truth container PK: `/datasetName`, `/bucket`
- assignments container PK: `/partitionKey` (SME id)

Optimistic concurrency:
- Respect `_etag` on updates (If-Match) to avoid lost updates and ensure single assignment.

Soft delete:
- `status: deleted` and retain history; cleanup job/endpoint for permanent removal.


## API surface (MVP)

Base: `/v1`, Auth: Bearer (Entra mode) or dev header.

SME
- POST `/assignments/self-serve` — request new batch (default 50; configurable)
- GET `/assignments/my` — list current SME assignments
- PUT `/assignments/{id}` — edit/approve (preserve original `synth-question`; save edited); soft delete via status=deleted
- GET `/ground-truths/stats` — counts by status (approved, draft, deleted), optionally scoped by sprint window

Curator
- POST `/ground-truths` — bulk import synthetic GT
- GET `/ground-truths/{datasetName}` — filter by `status=approved|draft|deleted`
- PUT `/ground-truths/{datasetName}/{id}` — curator update
- DELETE `/ground-truths/{datasetName}` — delete dataset (admin)
- DELETE `/ground-truths/{datasetName}/{id}` — delete item (admin)
- POST `/ground-truths/snapshot` — create weekly export (JSON documents + manifest to blob/local)

Integration with Retrieval System
- Attach/detach references to items; enforce “relevant paragraph required” when attaching a document.

LLM Answer Generation
- POST `/assignments/{id}:generate-answer` (or within PUT with flag) — facade to LLM based on latest version + attached refs; stub in phase 1.


## Assignment strategy (service)

- Input: SME id, requested batch size, dataset ratios config, sampling distribution hints (e.g., `samplingBucket`).
- Process:
  - Query candidate items (status=draft, unassigned) across configured datasets with ratio sampling.
  - Attempt to atomically mark `assignedTo` with `_etag` check; write assignment doc with partitionKey = SME id.
  - Return assigned items (materialized view fields denormalized for UI).
- On approval:
  - Update item to `accepted`; remove from SME queue immediately.
- On delete:
  - Set `status=deleted`; keep edit history for potential restore.


## Snapshot/export

- Query approved items (optionally by dataset list) at cutoff time.
- Write JSON documents with immutable artifact names (include schemaVersion, timestamp) and a manifest.json.
- Dev: write under `./exports/snapshots/{ts}/ground-truth-*.json` plus `manifest.json`.
- Azure: write to Blob container `snapshots/{ts}/...` with content MD5 and metadata.


## Observability

- Structured logging via Uvicorn + Python logging.
- Request IDs and correlation IDs (propagate if present).
- Health endpoints: `/healthz` (unauthenticated).
- Phase 2+: OpenTelemetry auto-instrumentation with exporter to Azure Monitor.


## Phased delivery

Phase 0 — Scaffolding (in-memory, dev auth)
- Create FastAPI app skeleton, routers, domain models, in-memory repositories.
- Implement all MVP endpoints with in-memory state.
- Basic assignment algorithm, soft delete, approval flow.
- Health checks, config system, logging.
- Unit tests for happy paths + a few edge cases.

Phase 1 — Azure adapters (feature flagged)
- Cosmos repository with partitioning and `_etag` concurrency.
- Local filesystem export for snapshot; add Blob adapter interface.
- Entra JWT validation; toggle via `GTC_AUTH_MODE`.
- Minimal rate limiting/validation hardening.

Phase 2 — Blob + AI Search + LLM stubs
- Snapshot/export to Azure Blob (JSON documents + manifest, immutable path naming, metadata).
- AI Search adapter: attach/detach references, enforce relevant paragraph field.
- LLM facade endpoint (stubbed; returns placeholder) with interface for later provider.
- Observability via OpenTelemetry (optional if timeline allows).

Phase 3 — Hardening and cleanup
- Tag management endpoints (admin), periodic cleanup for soft-deleted items.
- More tests (concurrency, auth edge cases), ty/ruff/black in CI.
- Performance tuning: pagination, query filters, indices guidance for Cosmos.


## Acceptance criteria (per phase)

Phase 0
- Running server exposes `/v1` endpoints with in-memory behavior matching contracts.
- Approve/Delete/Edit flows enforced; approved items are removed from SME list immediately.
- Attach/detach refs reflected in item metadata.
- Unit tests pass locally; lint/format checks clean.

Phase 1
- Cosmos adapter passes integration tests: create/read/update with `_etag` checks; partition keys respected.
- Entra mode: valid JWTs accepted; invalid `aud`/`iss` rejected; JWKS cache works.

Phase 2
- Snapshot writes JSON documents and manifest to Blob with correct schema and metadata; artifacts immutable by naming convention.
- AI Search attach/detach endpoints update item metadata accordingly and persist.
- LLM endpoint returns generated text in dev mode; interface pluggable for provider.


## Edge cases and risks

- Concurrency on assignment/approval: use `_etag` and idempotent operations.
- Large batches and pagination for listing assignments.
- Token clock skew and JWKS rotation; add small leeway and cache invalidation.
- Soft-delete cleanup safety: protect recently deleted items; dry-run.
- Cosmos RU costs and query patterns: prefer point reads with partition keys when possible.


## Local dev workflow (plan)

- Use uv to manage venv and dependencies under `.venv/`.
- Keep `pyproject.toml` as the single source of dependencies; `uv.lock` committed.
- Dev server run via `uv run`.

Proposed commands (to run later):

```sh
# create venv in project root
uv venv --python 3.11

# activate (zsh)
source .venv/bin/activate

# add runtime deps
uv add fastapi uvicorn[standard] pydantic pydantic-settings httpx "python-jose[cryptography]"

# add azure deps later
uv add azure-cosmos azure-storage-blob azure-identity azure-search-documents

# dev tooling
uv add -g dev pytest pytest-asyncio ruff black ty

# run app
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# run tests
uv run pytest -q
```


## Testing strategy

- Unit tests for routers (FastAPI TestClient), services (assignment, snapshot), and auth (dev and entra modes).
- Minimal integration tests for Cosmos adapter once added (skippable without credentials).
- Contract tests for request/response schemas; JSON schema validation for export.


## CI/CD (outline)

- Lint (ruff), format check (black --check), type check (ty), tests (pytest) on PR.
- Build container image with multi-stage Dockerfile (later); health endpoints for readiness.
- Deployment pipeline to Azure (later) with managed identity and private endpoints (future).


## Next steps

1) Confirm plan scope and phases.
2) Initialize project structure under `app/` with minimal routers and in-memory repos.
3) Add dependencies to `pyproject.toml` via uv and commit lockfile.
4) Implement Phase 0 endpoints + tests until green.
5) Plan Phase 1 Azure adapter wiring and secrets handling.


---
Requirements coverage (plan mapping):
- Review UI scope via SME endpoints and auth scoping: covered.
- Import new GT (bulk): covered.
- Approve/Reject/Edit with original preserved: covered.
- LLM answer generation (stub): covered.
- Retrieval/AI Search attachments with relevant paragraph: covered.
- Tagging from controlled vocabulary: planned; admin manage tags in Phase 3.
- Soft delete + restore + cleanup: covered.
- Batch assignment (single assignee, self-serve): covered with `_etag`.
- Snapshot/export weekly JSONL to Blob with schema v1: covered.
- Roles/permissions via Entra roles: covered in auth section.
