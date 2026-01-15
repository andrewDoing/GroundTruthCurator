# CI/CD pipeline plan for GroundTruthCurator

Short overview: Implement a simple GitHub Actions workflow that (1) installs deps with uv and Node, (2) runs backend unit and integration tests plus mypy, (3) builds the frontend, and (4) on main branch tags/releases, builds and pushes the backend Docker image to Azure Container Registry and updates a Container App to the new image. Only the minimum required steps, no extra matrix/legacy fallbacks.

## Scope and success criteria

- CI
  - Backend: run unit tests and integration tests (Cosmos emulator), skip stress/large markers, collect coverage artifact (optional).
  - Backend: run mypy against `app/`.
  - Frontend: run `npm ci` and `npm run build`.
- CD
  - Build multi-stage Docker image from `backend/Dockerfile` (which also builds the frontend) using repo root context.
  - Push to Azure Container Registry (ACR) using OIDC/Azure login.
  - Update Azure Container App to use the freshly pushed image tag.

Assumptions
- GitHub Actions is the CI/CD runner (workflows under `.github/workflows/`).
- Azure subscription has ACR and Container Apps set up; the Container App already exists with configured registry access (admin creds or managed identity).
- Workflows will use OpenID Connect (OIDC) for Azure login; required role assignments exist.
- Python 3.11 and Node 20 are the target toolchains (matches Dockerfile and package.json).

## Files to add/change

Add
- `.github/workflows/gtc-ci.yml` — CI for backend tests/mypy and frontend build on PRs and pushes.
- `.github/workflows/gtc-cd.yml` — CD for building/pushing image to ACR and updating Container App on `main` (and tags).

Optional (docs)
- `README.md` (root or backend/frontend readmes) — brief section on CI/CD, required secrets/permissions, and how to trigger.

No code changes required in source directories.

## Minimal job/step “functions” and purpose

Function: setup_python_with_uv
- Install Python 3.11 and uv; run `uv sync --frozen` to get dev deps for tests and mypy.

Function: ci_backend_unit_tests
- Run fast tests: `uv run pytest -m "not stress and not large and not cosmos"` in `backend/`. Fail fast on errors.

Function: start_cosmos_emulator_service
- Start Cosmos DB Emulator as a service container for integration tests; expose 8081 and wait for readiness.

Function: ci_backend_integration_tests
- Load env from `backend/environments/integration-tests.env` and run `uv run pytest -m "cosmos"`. Skip stress/large markers.

Function: ci_mypy
- Run `uv run mypy app` in `backend/`. Treat errors as failures.

Function: setup_node_and_install
- Use Node 20.x; run `npm ci` in `frontend/` using a cached npm folder.

Function: ci_frontend_build
- Run `npm run build` in `frontend/` to ensure TypeScript compiles and Vite builds.

Function: cd_azure_login
- Authenticate to Azure via OIDC (`azure/login`) with `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` or a federated service connection.

Function: cd_docker_build_and_push
- Build with `docker/build-push-action@v6` from repo root using `backend/Dockerfile`; tag as `${ACR_LOGIN_SERVER}/${IMAGE_REPO}:${GIT_SHA}` and `:${VERSION_OR_BRANCH}`; push to ACR.

Function: cd_update_container_app
- Update the Container App image via `az containerapp update --name ${CONTAINER_APP} --resource-group ${RESOURCE_GROUP} --image ${ACR_LOGIN_SERVER}/${IMAGE_REPO}:${TAG}` and roll out.

## CI details

Triggers
- Pull requests to any branch and pushes to branches (include `main`).

Python/uv caching
- Cache `~/.cache/uv` keyed by `backend/uv.lock` and Python version to speed up installs.

Node caching
- Cache `~/.npm` keyed by `frontend/package-lock.json` and Node version.

Backend test selection
- Unit tests: discover under `backend/tests/unit/` automatically via `pytest.ini` and `pyproject.toml` with markers filtered by `-m "not stress and not large and not cosmos"`.
- Integration tests: run with `-m "cosmos"`. Provide env file: `dotenv -f environments/integration-tests.env` or export via `env` block. Service container for emulator uses default key.

Cosmos emulator service container (Linux)
- Image: `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator` with ports `8081:8081` and env `AZURE_COSMOS_EMULATOR_PARTITION_COUNT=3` (defaults ok). Wait loop: curl `http://localhost:8081/_explorer/emulator.pem` with retries.

Mypy
- Run against `backend/app` package. If additional config is needed later, add `mypy.ini`—not required for the initial pass.

Frontend build
- `npm ci && npm run build` in `frontend/`. No e2e tests in CI initially; keep it simple.

Artifacts (optional)
- Upload `frontend/dist/` and backend coverage xml as artifacts for PR inspection.

## CD details

Trigger
- On push to `main` and on version tags `v*.*.*`.

Image build
Context: use repository root so the Dockerfile can COPY both `frontend/` and `backend/`.
Dockerfile path: `backend/Dockerfile` (multi-stage; builds frontend then runtime image).
Tags: use two tags minimum
  - `${ACR_LOGIN_SERVER}/${IMAGE_REPO}:${GITHUB_SHA}` (immutable)
  - `${ACR_LOGIN_SERVER}/${IMAGE_REPO}:main` or `${ACR_LOGIN_SERVER}/${IMAGE_REPO}:${GIT_TAG}` when applicable

Registry push
- Login to ACR via Azure CLI (`az acr login -n ${ACR_NAME}`) or `docker/login-action` with `username/password` if admin enabled. Prefer OIDC + `az acr login`.

Container App update
- `az containerapp update --name ${CONTAINER_APP} --resource-group ${RESOURCE_GROUP} --image ${ACR_LOGIN_SERVER}/${IMAGE_REPO}:${RESOLVED_TAG}`
- If the app uses a managed identity to pull: ensure identity has `AcrPull` role on the ACR; include `--registry-identity` only if required by environment.

Roll-forward/rollback
- Keep the `${GITHUB_SHA}`-tagged image to enable quick rollback: `az containerapp update --image ...:${PREV_SHA}`.

## Required secrets/variables

GitHub Actions secrets/vars
- AZURE_CLIENT_ID (if using OIDC service principal)
- AZURE_TENANT_ID
- AZURE_SUBSCRIPTION_ID
- ACR_NAME (e.g., `myregistry`)
- ACR_LOGIN_SERVER (e.g., `myregistry.azurecr.io`)
- RESOURCE_GROUP (e.g., `gtc-rg`)
- CONTAINER_APP (e.g., `gtc-backend`)
- IMAGE_REPO (e.g., `groundtruthcurator/backend`)

No API keys are needed for unit/integration tests when using Cosmos emulator. Ensure tests do not make real outbound LLM or Search calls, or set `GTC_LLM_ENABLED=False` in CI env.

## Concrete test commands and filters

- Unit tests
  - Command: `uv run pytest -q -m "not stress and not large and not cosmos"`

- Integration tests (Cosmos)
  - Command: `uv run pytest -q -m "cosmos"`
  - Env file: `backend/environments/integration-tests.env`

- Mypy
  - Command: `uv run mypy app`

- Frontend build
  - Command: `(cd frontend && npm ci && npm run build)`

## Test names and behaviors to cover

- backend unit: repository methods basic CRUD — fast, no network.
- backend unit: service-layer validation — pydantic types enforced.
- backend integration: cosmos create/read/update/delete — emulator-backed persistence.
- backend integration: API endpoints happy path — FastAPI test client.
- typing: app module mypy pass — no new type errors.
- frontend build: vite/tsc compile succeeds — no type errors.

## Acceptance checklist

- CI workflow runs on PRs and blocks merge on failures.
- Backend unit tests pass; integration tests pass against emulator.
- Mypy passes on `backend/app`.
- Frontend build succeeds.
- CD workflow builds and pushes image to ACR on main/tag.
- Container App updates to the new image successfully.

## Follow-ups (deferred, not in initial scope)

- Add coverage reporting and PR annotations.
- Add Playwright e2e in a nightly workflow.
- Promote via environments (dev/stage/prod) with approvals.
- Use versioned release tags and changelog automation.
