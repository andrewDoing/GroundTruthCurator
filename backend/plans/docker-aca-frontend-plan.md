# Plan: Dockerize API for Azure Container Apps and serve React frontend via API

## Overview

We will: (1) add a simple Dockerfile and .dockerignore to containerize this FastAPI app for Azure Container Apps (ACA) with uvicorn, and (2) add a minimal, opt-in static hosting endpoint to serve a pre-built React app from a directory on disk. Keep it simple: no frontend build steps in this repo, only serving already-built assets. API remains under `settings.API_PREFIX` (default `/v1`), and the SPA is served at root (`/`) with a catch-all fallback to `index.html` for client-side routing, without interfering with API routes.

## Implement only what we need now

- Docker image built from Python 3.11-slim, install deps via pip, run uvicorn, listen on `${PORT:-8080}` to align with ACA. Health at `/healthz`.
- Static frontend serving only when `GTC_FRONTEND_DIR` is configured and exists. If not set, no change to API behavior.
- SPA catch-all fallback returns `index.html` for non-API paths; API traffic continues to `/v1/*` unchanged.
- No React build in this repo; assume assets are provided (copied or volume-mounted) at container runtime.

## Files to add/change

New files:
- `Dockerfile` (at repo root for backend): Containerize API with uvicorn on `${PORT:-8080}`.
- `.dockerignore`: Exclude venvs, git, tests, local artifacts.

Minimal changes to existing code:
- `app/core/config.py`: Add `FRONTEND_DIR: str | None = None`, `FRONTEND_INDEX: str = "index.html"` (and optionally `FRONTEND_CACHE_SECONDS: int = 3600`). Loadable via env var `GTC_FRONTEND_DIR`.
- `app/main.py`:
  - Import and conditionally mount `StaticFiles` if `settings.FRONTEND_DIR` exists.
  - Register a lightweight catch-all route serving `index.html` for non-API paths when frontend is enabled.
  - Ensure static mount and fallback are added after the API router so API endpoints take precedence.

Optional (only if we want to keep `main.py` very small):
- `app/web/frontend.py` (new): Helpers for mounting static files and SPA fallback. Not required for initial slice.

## Functions (names and purpose)

Keep it simple and colocate in `app/main.py` unless we outgrow it.

- `def _get_frontend_dir() -> Path | None`
  - Validate `settings.FRONTEND_DIR` and return `Path` if it exists and contains `settings.FRONTEND_INDEX`, else `None`.

- `def mount_frontend(app: FastAPI) -> None`
  - If a valid frontend dir exists, `app.mount("/", StaticFiles(directory=dir, html=True), name="frontend")` and record a flag on `app.state` indicating SPA is enabled.

- `async def spa_fallback(request: Request) -> Response`
  - If SPA is enabled and path does not start with `settings.API_PREFIX` (or docs/openapi paths), return `index.html` from the frontend dir. Otherwise return 404. Registered as a catch-all GET route: `@app.get("/{full_path:path}", include_in_schema=False)` placed after API/router/StaticFiles.

Notes:
- Using `StaticFiles(..., html=True)` for directory index; we still add an explicit catch-all to support deep SPA routes that would otherwise 404.
- We will not add complex caching/ETags now; rely on default static file behavior. Optionally pass `max_age=settings.FRONTEND_CACHE_SECONDS` later.

## Dockerfile contents (high-level)

- Base: `python:3.11-slim`.
- Install minimal system deps: `curl`, `ca-certificates`.
- Install uv (Astral) and use it for deterministic, fast installs:
  - `curl -LsSf https://astral.sh/uv/install.sh | sh` (adds uv to PATH)
  - Set `ENV UV_LINK_MODE=copy` to avoid symlink issues in containers.
- Layered install for caching:
  - `COPY pyproject.toml uv.lock ./`
  - `RUN uv sync --frozen --no-dev` to resolve and install using the lockfile into a local virtualenv (`.venv`).
  - `ENV PATH="/app/.venv/bin:$PATH"` so runtime finds installed packages.
- Copy app source after dependencies: `COPY app ./app` plus project files as needed. Optionally copy prebuilt frontend into `/app/frontend` if available at build time.
- Env: `PORT=8080`, `PYTHONUNBUFFERED=1`.
- Expose port 8080.
- Entrypoint: `uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers`.

We can later switch to `gunicorn` with multiple uvicorn workers if needed; initial slice keeps uvicorn simple.

## .dockerignore (high-level)

- `.git`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`, `.venv/`, `env*/`, `tests/`, `exports/`, and local `.env` files (unless explicitly copied at build time).

## Environment variables

- `GTC_ENV_FILE`: Path(s) to env file(s) for runtime settings (already supported). For container, mount or bake minimal prod env.
- `GTC_FRONTEND_DIR`: Absolute path to directory with built React assets inside the container (e.g., `/app/frontend`). If present and valid, static frontend is enabled.
- `PORT`: Listening port (ACA commonly uses 8080). Default 8080.

## Test plan (unit/integration) — names and brief behaviors

- Unit — `test_config_frontend_dir_env_var_read`
  - Env var populates settings.FRONTEND_DIR correctly.

- Unit — `test_frontend_disabled_no_static_mount`
  - Without GTC_FRONTEND_DIR, root `/` returns 404.

- Unit — `test_frontend_enabled_serves_index_html`
  - With temp dir + index.html, GET `/` returns index content.

- Unit — `test_spa_fallback_for_deep_route`
  - Unknown path `/foo/bar` returns index.html when enabled.

- Unit — `test_api_routes_not_intercepted_by_frontend`
  - `/v1/health` or `/v1/...` still handled by API.

- Unit — `test_docs_and_openapi_not_intercepted`
  - `/v1/docs` and `/v1/openapi.json` not overridden.

- Integration — `test_healthz_ok_in_containerized_env`
  - Basic health endpoint returns status ok (smoke).

## Acceptance criteria

- Building the Docker image succeeds, container runs uvicorn on `${PORT:-8080}`, and `/healthz` returns JSON `{status: "ok", ...}`.
- When `GTC_FRONTEND_DIR` points to a directory containing `index.html`, `/` returns that index and deep SPA routes return the same file.
- API under `/v1/*` works exactly as before and is not intercepted by the SPA fallback.

## Follow-ups (out of scope for first slice)

- Add `gunicorn` with multiple uvicorn workers and health/readiness probes tuned for ACA.
- Add optional immutable caching headers for hashed static assets.
- Multi-stage build to compile the React app (when frontend source is colocated).
- Use BuildKit cache mounts for `uv` to speed builds further.
- IaC for ACA (Bicep/terraform) and GitHub Actions workflow for CI/CD.
