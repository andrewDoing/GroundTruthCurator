# Ground Truth Curator (Backend)

Local setup and test guide for contributors. This walks you from zero to a running API backed by the Azure Cosmos DB Emulator, plus unit/integration tests and a container smoke test.

## Quickstart (TL;DR)

```bash
# From backend/
# 1) Install deps into a local .venv (created automatically by uv)
uv sync

# 2) Start Cosmos DB Emulator (Docker) on port 8081
#    Works on macOS/Apple Silicon and Linux
docker pull mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-EN20251022
docker run --rm -d --name cosmos-emulator -p 8081:8081 mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-EN20251022

# 3) Initialize Cosmos DB containers (required before first run)
uv run python scripts/cosmos_container_manager.py \
  --endpoint http://localhost:8081 \
  --key "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==" \
  --no-verify \
  --db gt-curator \
  --gt-container --assignments-container --tags-container

# 4) Optional: overlay additional env files (secrets/overrides)
#    By default, the app loads environments/.dev.env automatically.
#    You can overlay with local.env:
export GTC_ENV_FILE="environments/.dev.env,environments/local.env"

# 5) Run the API with reload on port 8000
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# In a second terminal, check health:
# curl http://localhost:8000/healthz

# 6) Run integration tests (uses the emulator env)
#    Prefer the VS Code task "Run integration tests (integration env)" or:
GTC_ENV_FILE="environments/integration-tests.env,environments/local.env" uv run pytest -q tests/integration
```

---

## Prerequisites

- macOS or Linux (Windows is similar with Docker Desktop)
- Python 3.11
- uv (virtualenv + package manager)
  - Install: see https://docs.astral.sh/uv
- Docker Desktop (for the Cosmos DB Emulator)

## Setup (Python + deps)

From `backend/`:

```bash
# Creates/updates a local .venv and installs all dependencies
uv sync
```

You’ll use `uv run <command>` to run tools (pytest, uvicorn, scripts) inside the venv.

## Run the Cosmos DB Emulator (Docker)

Minimal working commands:

```bash
docker pull mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview
docker run --rm -d --name cosmos-emulator -p 8081:8081 mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview
```

Notes:

- The repository’s env files are already set up to use the emulator over HTTP at `http://localhost:8081`.
- No HTTPS or certificate setup is required for local runs (HTTP endpoint is used).

## Environment configuration (GTC_ENV_FILE overlays)

The app uses pydantic-settings with the `GTC_` prefix. By default it auto-loads:

- `environments/.dev.env`
- If present, overlays (later overrides earlier):
  - `environments/.dev.local.env`
  - `environments/local.env`

You can explicitly set the env file(s) to load using the `GTC_ENV_FILE` environment variable. This supports a comma-separated list; later entries override earlier ones.

Examples:

```bash
# Explicitly load development + local overlays
export GTC_ENV_FILE="environments/.dev.env,environments/local.env"

# For tests, prefer the integration test env overlaid with local
export GTC_ENV_FILE="environments/integration-tests.env,environments/local.env"
```

Key values in the provided env files:

- `GTC_REPO_BACKEND=cosmos`
- `GTC_COSMOS_ENDPOINT=http://localhost:8081`
- `GTC_COSMOS_KEY` is the emulator's well-known primary key
- `GTC_COSMOS_CONNECTION_VERIFY=false` (emulator uses self-signed TLS; safe for local)
- `GTC_USE_COSMOS_EMULATOR=true`
- `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true` (workaround for emulator Unicode bug with multiturn data)

The primary key can be found here: <https://learn.microsoft.com/en-us/azure/cosmos-db/emulator?context=%2Fazure%2Fcosmos-db%2Fnosql%2Fcontext%2Fcontext>

### Cosmos Emulator Unicode Workaround

The Cosmos DB Emulator has a known issue parsing Unicode escape sequences (`\uXXXX`) in JSON payloads. When working with multiturn data containing special characters (e.g., é, 😀), you may encounter errors like "unsupported unicode escape sequences."

**Solution:** Set `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true` in your local environment file. This ensures that the backend sends real UTF-8 characters instead of escape sequences, avoiding the emulator's parsing bug.

**Note:** This setting should only be enabled for local development with the emulator. Production Cosmos DB does not have this issue.

### What goes into environments/local.env (secrets)

`environments/local.env` is git-ignored and intended for secrets and developer-specific overrides. In this repo it typically holds keys like:

```bash
# API keys and tokens (do not commit real values)
GTC_AZ_FOUNDRY_KEY=<your-azure-ai-foundry-key>
GTC_AZ_SEARCH_KEY=<your-azure-ai-search-key>
```

Notes:

- Keep real secrets only in `local.env` (never change committed env files to add keys).
- Local overlays take precedence when specified later in `GTC_ENV_FILE`.
- If you ever connect to a non-emulator Cosmos account (out of scope here), you would set `GTC_COSMOS_KEY` here as well.

## Run the API locally

Start FastAPI with uvicorn and live reload:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify health:

```bash
curl http://localhost:8000/healthz
```

You should see a JSON payload like:

```json
{
  "status": "ok",
  "repoBackend": "CosmosGroundTruthRepo",
  "cosmos": {
    "endpoint": "http://localhost:8081",
    "db": "gt-curator",
    "container": "ground_truth"
  }
}
```

## Optional: Seed sample data via API

Use the helper script to import a batch of synthetic ground-truth items and register default tags:

```bash
# Default base URL is http://localhost:8000 and API prefix is auto-resolved from settings
uv run python scripts/init_seed_data.py --dataset demo --count 50 --approve

# Or specify parameters explicitly
uv run python scripts/init_seed_data.py \
  --base-url http://localhost:8000 \
  --api-prefix /v1 \
  --dataset demo \
  --count 100 \
  --approve
```

## Scripts

This repository includes helper scripts under `scripts/`.

### Container Initialization (cosmos_container_manager.py)

Before running the application for the first time, you must create the Cosmos DB containers. The `cosmos_container_manager.py` script handles this for both the local emulator and Azure-deployed Cosmos DB.

**Local Emulator (key-based auth):**

```bash
uv run python scripts/cosmos_container_manager.py \
  --endpoint http://localhost:8081 \
  --key "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==" \
  --no-verify \
  --db gt-curator \
  --gt-container --assignments-container --tags-container
```

**Azure Cosmos DB (Azure AD auth):**

```bash
uv run python scripts/cosmos_container_manager.py \
  --endpoint https://myaccount.documents.azure.com:443/ \
  --use-aad \
  --db gt-curator \
  --gt-container --assignments-container --tags-container
```

**Options:**

| Option | Description |
|--------|-------------|
| `--endpoint` | Cosmos DB endpoint URL (required) |
| `--key` | Cosmos DB key for key-based auth |
| `--use-aad` | Use Azure AD authentication (DefaultAzureCredential) |
| `--no-verify` | Disable SSL verification (for emulator) |
| `--db` | Database name (required) |
| `--gt-container [NAME]` | Create ground truth container (default: ground_truth) |
| `--assignments-container [NAME]` | Create assignments container (default: assignments) |
| `--tags-container [NAME]` | Create tags container (default: tags) |
| `--container NAME` | Create a custom container |
| `--partition-key PATH` | Partition key for custom container |
| `--partition-paths PATH...` | Hierarchical partition key paths |
| `--indexing-policy FILE` | Custom indexing policy JSON file |

The script is idempotent — running it multiple times is safe; existing containers are not modified.

### Other Scripts

- KB CSV cleaning and import: see `scripts/README.md` for end-to-end steps to clean the CSV and bulk-import into the API (including bearer-token auth, dry-run, and error reporting).

## Run tests

You can use the built-in VS Code tasks (recommended) or run commands manually.

- Unit tests

  - VS Code task: “Run unit tests”
  - Command:
    ```bash
    uv run pytest -q tests/unit
    ```

- Integration tests (with emulator)

  - VS Code task: "Run integration tests (integration env)"
    - This task sets `GTC_ENV_FILE="environments/integration-tests.env, environments/local.env"` automatically
  - Command:
    ```bash
    GTC_ENV_FILE="environments/integration-tests.env,environments/local.env" uv run pytest -q tests/integration
    ```
  - **Note:** Some tests are skipped when using the Cosmos DB Emulator due to unsupported features (e.g., `ARRAY_CONTAINS` for tag filtering). See `docs/cosmos-emulator-limitations.md` for details.

- Full suite

  - VS Code task: “Run tests”
  - Command:
    ```bash
    uv run pytest -q
    ```

- Container smoke test (builds the Docker image and validates /healthz)
  - VS Code task: “Run container smoke test”
  - Command (optional alternative):
    ```bash
    GTC_RUN_DOCKER_TESTS=1 uv run pytest -vv tests/integration/test_container_smoke.py::test_healthz_ok_in_containerized_env
    ```

## Troubleshooting

- Emulator not ready yet: it can take a few seconds after `docker run` before it accepts connections. Retry.
- Connection issues: ensure the container is running (`docker ps`) and port `8081` is mapped.
- Self-signed TLS: keep `GTC_COSMOS_CONNECTION_VERIFY=false` (already set in the provided env files).
- Endpoint mismatch in containers: inside Docker, use `http://host.docker.internal:8081` to reach the host’s emulator. The smoke test sets this for you.
- Wrong env files: verify `GTC_ENV_FILE` or rely on the default auto-load described above.

## Cleanup (optional)

Delete all emulator databases to reset local state:

```bash
uv run python scripts/delete_cosmos_emulator_dbs.py
```

## Success criteria

- `GET /healthz` returns 200 with Cosmos details.
- Integration tests pass using the emulator env.
- Container smoke test passes.

## Links

- See `CODEBASE.md` for a top-level tour.
- More docs in the `docs/` folder.
- Tagging behavior: see `docs/tagging_plan.md` — tags must be `group:value` (normalized), unknown groups/values are allowed, and known-group rules (exclusivity and dependencies) are enforced.

## Deploy helpers: push env vars to Azure Container Apps

To push configuration keys from `environments/.dev.env` into an existing Azure Container App as plain environment variables, use the helper script:

```bash
# From backend/
scripts/aca-push-env.sh \
  --resource-group <rg-name> \
  --name <container-app-name> \
  --yes

# Options:
#   --env-file PATH     Use a different .env file (default: environments/.dev.env)
#   --prefix REGEX      Only include keys matching REGEX (default: ^GTC_)
#   --container NAME    Target a specific container within the app
#   --dry-run           Show what would be applied without updating Azure
```

Notes:

- This sets plain env vars with `az containerapp update --set-env-vars`. It does not manage secrets.
- Keep real secrets in a secure store (Key Vault) and wire them via `az containerapp secret set` + `secretref:` envs, not by committing them into env files.

## Observability (Telemetry)

This service emits structured logs to stdout. You can optionally enable OpenTelemetry export to Azure Monitor / Application Insights:

- Set either `GTC_AZ_MONITOR_CONNECTION_STRING` or the standard `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Optional: `GTC_AZ_MONITOR_ENABLED` (defaults to true) controls whether telemetry wiring runs.
- Optional: `GTC_SERVICE_NAME` customizes the service.name resource attribute (default: `gtc-backend`).

When no connection string is provided, telemetry initialization is a no-op and the app runs with console logs only.

### User identity in logs

Every log line now includes a `user=<id>` field derived per request:

- Easy Auth enabled (`GTC_EZAUTH_ENABLED=true`): prefers principal `email`, then `oid`, then `name`.
- Dev mode (Easy Auth disabled): uses the `X-User-Id` header if provided, otherwise `anonymous`.
- Tests can set `X-User-Id` to simulate multiple users.

If no user context is available (e.g., startup logs), the field is emitted as `user=` (empty) or `user=anonymous` in dev scenarios. This is implemented via a FastAPI middleware + a logging filter and `LogRecordFactory` that safely inject a `user_id` attribute into all records (including third‑party libraries) so the formatter is stable.
