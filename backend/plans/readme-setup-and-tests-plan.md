# README update plan: local setup + integration tests

## Overview

We will update `README.md` to provide clear, copy-pasteable, step-by-step instructions for getting the backend running locally and executing all integration tests. The guide will use Python 3.11 with uv, the Azure Cosmos DB Emulator (Linux container), and the existing VS Code tasks already defined in this repository. We will keep it simple and focused on what’s needed right now to unblock contributors.

## Files to change

- `README.md` (only)

No code changes are required. We’ll reference existing tasks and scripts (no new scripts).

## What we’ll add to the README (step-by-step content)

1) Prerequisites
- macOS or Linux (Windows similar)
- Python 3.11
- uv (virtualenv + package manager)
- Docker Desktop (for Cosmos DB Emulator)

2) Bootstrap environment
- From `backend/`:
  - Create and activate venv with uv
  - `uv sync` to install dependencies

3) Start Cosmos DB Emulator (Docker)
- Pull and run the Linux emulator container, exposing port 8081
- Minimal working command (macOS/Apple Silicon supported):
  - `docker pull mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview`
  - `docker run --rm -d --name cosmos-emulator -p 8081:8081 mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview`

4) Configure environment files (GTC_ENV_FILE)
- Explain default auto-load of `environments/.dev.env`
- Recommend creating `environments/local.env` (git-ignored) for secrets/overrides
- Show overlay pattern with multiple env files: `GTC_ENV_FILE="environments/.dev.env,environments/local.env"`
- For tests, prefer: `GTC_ENV_FILE="environments/integration-tests.env,environments/local.env"`

5) Run the API locally
- Run uvicorn with reload
- Verify health: GET `http://localhost:8000/healthz` returns `{ status: "ok" }` and Cosmos details

6) (Optional) Seed sample data via API
- Use `scripts/init_seed_data.py` to bulk import into a dataset and register default tags
- Example: `uv run python scripts/init_seed_data.py --dataset demo --count 50 --approve`

7) Run tests
- Unit tests: VS Code task “Run unit tests” or `uv run pytest -q tests/unit`
- Integration tests: VS Code task “Run integration tests (integration env)” (sets `GTC_ENV_FILE` automatically)
  - Alt command: `GTC_ENV_FILE="environments/integration-tests.env,environments/local.env" uv run pytest -q tests/integration`
- Full suite: “Run tests” task or `uv run pytest -q`
- Container smoke: “Run container smoke test” task builds image and verifies `/healthz`

8) Troubleshooting
- Emulator not ready yet → wait a few seconds then retry
- Connection issues → ensure container is running and port 8081 mapped
- Self-signed TLS → keep `GTC_COSMOS_CONNECTION_VERIFY=false` (already set in provided env files)
- Endpoint mismatch → use `http://localhost:8081` (emulator HTTP endpoint)

9) Cleanup (optional)
- Delete all emulator databases: `uv run python scripts/delete_cosmos_emulator_dbs.py`

10) Success criteria
- `/healthz` returns 200 with Cosmos details
- Integration tests pass using the emulator env
- Container smoke test passes

## Proposed README section outline

- Title + short project blurb
- Quickstart (TL;DR)
- Prerequisites
- Setup (uv venv + sync)
- Cosmos DB Emulator (Docker) – minimal commands
- Environment configuration (GTC_ENV_FILE overlays) – short examples
- Run the API locally – command + health check
- Optional: Seed sample data – command
- Run tests
  - Unit
  - Integration (with emulator env)
  - Full suite
  - Container smoke test
- Troubleshooting
- Links: CODEBASE.md and docs folder

## Functions to reference (no code changes)

- `app.main:create_app` and `app.main:app`
  - Uvicorn entrypoint. Starts FastAPI, mounts routers, exposes `/healthz`.
- `app.container.Container.init_cosmos_repo`
  - Wires the Cosmos repo and services; startup init creates DB/containers when configured.
- `scripts.init_seed_data:main`
  - CLI to seed ground truth items via API and register default tags; useful for demo/testing.
- `tests/integration/test_container_smoke.py::test_healthz_ok_in_containerized_env`
  - Builds the Docker image, runs the container, and validates `/healthz`.

## Tests to cover (names + brief behavior)

- `tests/integration/test_env_loading.py::test_env_files_overlay_applied`
  - Later env files override earlier via GTC_ENV_FILE.
- `tests/integration/test_cosmos_emulator_setup.py::test_cosmos_emulator_reachable`
  - Healthz shows Cosmos backend and correct endpoint.
- `tests/integration/test_import_and_list_flow.py::test_bulk_import_then_list_by_dataset`
  - Import returns ok; list shows imported items.
- `tests/integration/test_assignments_flow.py::test_self_serve_and_approve_happy_path`
  - Self-serve assignments, then approve with ETag.
- `tests/integration/test_snapshot_flow.py::test_snapshot_exports_manifest_and_items`
  - Snapshot writes manifest and per-item JSON files.
- `tests/integration/test_container_smoke.py::test_healthz_ok_in_containerized_env`
  - Containerized API serves healthz successfully.
- `tests/unit/test_settings_loader.py::test_multiple_env_files_override_order`
  - Confirms overlay order is respected by loader.
- `tests/unit/test_tag_registry.py::test_default_tags_added_on_startup`
  - Startup seeds default tags into registry (idempotent).

## Assumptions

- Contributors use macOS with zsh by default; commands are POSIX-compatible.
- Docker Desktop is installed and running.
- We use the Linux Cosmos Emulator image with port 8081. No HTTPS or certificate setup required for local runs (HTTP endpoint is used in env files).

## Out of scope (now)

- Azure-hosted Cosmos DB setup and credentials.
- CI pipelines or cloud deployment steps.
- Frontend build/run instructions (only mention optional static serving already supported).
