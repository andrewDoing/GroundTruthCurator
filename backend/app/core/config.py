from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices, SecretStr, model_validator
from pathlib import Path
import os
import logging

logger = logging.getLogger("gtc.config")

# Module-level repo root to avoid Pydantic private attr behavior on class underscores
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Use environment variables with prefix GTC_ and load from repo-local .env file if present.
    # Resolve .env relative to the repo root so starting the app from any CWD still loads settings.
    model_config = SettingsConfigDict(
        env_prefix="GTC_",
        env_file=str(REPO_ROOT / "environments" / "sample.env"),
        env_file_encoding="utf-8",
        extra="forbid",  # surface unknown env vars as errors
    )

    ENV: str = "dev"  # dev|test|prod
    API_PREFIX: str = "/v1"
    LOG_LEVEL: str = "info"

    AUTH_MODE: str = "dev"  # dev|entra
    ENTRA_TENANT_ID: str | None = None
    ENTRA_AUDIENCE: str | None = None
    ENTRA_ISSUER: str | None = None

    # Repository backend selection
    REPO_BACKEND: str = "memory"  # memory|cosmos

    # Cosmos DB configuration (for cosmos backend)
    COSMOS_ENDPOINT: str | None = None
    COSMOS_KEY: SecretStr | None = (
        None  # Emulator key or account key (dev only; use DefaultAzureCredential in prod)
    )
    COSMOS_DB_NAME: str = "gt-curator"
    COSMOS_CONTAINER_GT: str = "ground_truth"
    COSMOS_CONTAINER_ASSIGNMENTS: str = "assignments"
    COSMOS_CONTAINER_TAGS: str = "tags"
    USE_COSMOS_EMULATOR: bool = False
    # Emulator uses a self-signed cert; allow disabling TLS verification locally
    COSMOS_CONNECTION_VERIFY: bool | str | None = False
    # Disable Unicode escape sequences (\uXXXX) when using Cosmos emulator locally
    # Set to True to send real UTF-8 characters instead of escape sequences (fixes emulator bug)
    COSMOS_DISABLE_UNICODE_ESCAPE: bool = False
    COSMOS_TEST_MODE: bool = False  # Use test mode for Cosmos repo (e.g. no sampling buckets)
    COSMOS_MAX_CONNECTION_POOL_SIZE: int = 200
    COSMOS_REQUEST_TIMEOUT: int = 30  # seconds
    COSMOS_RETRY_TOTAL_ATTEMPTS: int = 5
    COSMOS_RETRY_FIXED_INTERVAL: float = 1.0  # seconds
    COSMOS_ENABLE_ENDPOINT_DISCOVERY: bool = True

    # Azure AI Search configuration (read-only search endpoint)
    AZ_SEARCH_ENDPOINT: str | None = None
    AZ_SEARCH_INDEX: str | None = None
    AZ_SEARCH_KEY: SecretStr | None = (
        None  # Dev only; use DefaultAzureCredential in prod if not provided
    )
    AZ_SEARCH_API_VERSION: str = "2024-07-01"

    # Search result field mappings (configure source field names from search backend)
    SEARCH_FIELD_URL: str = "url"
    SEARCH_FIELD_TITLE: str = "title"
    SEARCH_FIELD_CHUNK: str = "chunk"

    # Agent chat settings (Azure AI Foundry Agent Service)
    CHAT_ENABLED: bool = True
    AZURE_AI_PROJECT_ENDPOINT: str | None = None
    AZURE_AI_AGENT_ID: str | None = None
    AGENT_TIMEOUT_SECONDS: int = 30
    STORE_AGENT_STEPS: bool = False

    # Retrieval service settings (for FunctionTool-based agent retrieval)
    RETRIEVAL_URL: str | None = None
    RETRIEVAL_PERMISSIONS_SCOPE: str | None = None
    RETRIEVAL_TIMEOUT_SECONDS: int = 30

    # Optional static frontend serving
    FRONTEND_DIR: str | None = None  # Absolute path inside container (e.g., /app/frontend)
    FRONTEND_INDEX: str = "index.html"
    FRONTEND_CACHE_SECONDS: int = 3600

    # Validation toggles (exposed to frontend via /v1/config endpoint)
    REQUIRE_REFERENCE_VISIT: bool = False  # Require all references to be visited before approval
    REQUIRE_KEY_PARAGRAPH: bool = False  # Require key paragraphs for relevant references

    # Frontend UI settings (exposed to frontend via /v1/config endpoint)
    SELF_SERVE_LIMIT: int = 10  # Default number of items to request from self-serve assignments

    # List of hostnames considered trusted for reference opening.
    # CSV (e.g. "docs.example.com,support.example.com").
    # If empty, every non-same-origin URL will prompt for confirmation.
    TRUSTED_REFERENCE_DOMAINS: str | None = None

    # Optional allowlist of manual tags (CSV of "group:value").
    # When set, the `/v1/tags` endpoint will return this allowlist instead of
    # reading from the tags registry store.
    ALLOWED_MANUAL_TAGS: str | None = None

    # Manual tag defaults configuration (JSON file with manualTagGroups)
    MANUAL_TAGS_CONFIG_PATH: str = str(REPO_ROOT / "app" / "domain" / "manual_tags.json")

    # Export pipeline settings
    EXPORT_PROCESSOR_ORDER: str | None = None
    EXPORT_STORAGE_BACKEND: str = "local"  # local|blob
    EXPORT_BLOB_ACCOUNT_URL: str | None = None
    EXPORT_BLOB_CONTAINER: str | None = None

    @model_validator(mode="after")
    def _validate_export_storage(self) -> "Settings":
        if self.EXPORT_STORAGE_BACKEND == "blob":
            if not self.EXPORT_BLOB_ACCOUNT_URL or not self.EXPORT_BLOB_CONTAINER:
                raise ValueError(
                    "EXPORT_BLOB_ACCOUNT_URL and EXPORT_BLOB_CONTAINER are required when "
                    "EXPORT_STORAGE_BACKEND is 'blob'"
                )
        return self

    # Sampling allocation config (CSV string). Example: "dataset1:50,dataset2:50"
    # Used by get_sampling_allocation(); kept as raw string for flexible parsing.
    SAMPLING_ALLOCATION: str | None = None

    # Pagination settings
    PAGINATION_MAX_LIMIT: int = Field(
        default=100, description="Maximum items per page for list queries"
    )
    PAGINATION_MIN_LIMIT: int = Field(default=1, description="Minimum items per page")
    PAGINATION_TAG_FETCH_MAX: int = Field(
        default=500,
        description="Maximum items to fetch for tag filtering queries (memory safeguard)",
    )

    # Duplicate detection settings
    DUPLICATE_DETECTION_ENABLED: bool = Field(
        default=True, description="Enable duplicate detection during bulk import (informational warnings only)"
    )

    # Observability / Telemetry
    # Toggle and connection string for Azure Monitor / App Insights via OpenTelemetry
    AZ_MONITOR_ENABLED: bool = True
    # Accept both our prefixed env var and the standard Azure variable name from platform
    AZ_MONITOR_CONNECTION_STRING: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GTC_AZ_MONITOR_CONNECTION_STRING", "APPLICATIONINSIGHTS_CONNECTION_STRING"
        ),
    )
    SERVICE_NAME: str = "gtc-backend"

    # Azure Container Apps Easy Auth (ACA) settings
    # When enabled, we expect ACA to inject identity headers (X-MS-CLIENT-PRINCIPAL, etc.).
    # We enforce allow rules by email domain and/or explicit object IDs.
    EZAUTH_ENABLED: bool = False
    # Paths excluded from Easy Auth at the ACA platform level (used by CD workflow)
    # and mirrored inside the app for middleware skip logic so both layers stay aligned.
    EZAUTH_ALLOW_ANONYMOUS_PATHS: str = "/healthz,/metrics"  # CSV of paths
    EZAUTH_ALLOWED_EMAIL_DOMAINS: str | None = None  # CSV domains
    EZAUTH_ALLOWED_OBJECT_IDS: str | None = None  # CSV GUIDs
    EZAUTH_HEADER_SOURCE: str = "aca"  # currently only "aca" is supported

    # Azure Identity (optional) — allow user-assigned identity selection via standard var
    # We don’t use this directly, but including it prevents extra-forbidden when present in env files
    AZURE_CLIENT_ID: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GTC_AZURE_CLIENT_ID", "AZURE_CLIENT_ID"),
    )
    # PII detection toggle
    PII_DETECTION_ENABLED: bool = True


def _resolve_env_files_from_override(repo_root: Path) -> str | tuple[str, ...] | None:
    """Resolve optional override for dotenv file(s) using GTC_ENV_FILE.

    Supports absolute or relative paths (relative to repo root) and
    comma-separated list for multiple env files (later items override earlier).
    """
    override = os.getenv("GTC_ENV_FILE")
    if not override:
        return None

    def to_abs(p: str) -> str:
        path = Path(p)
        if not path.is_absolute():
            path = repo_root / p
        return str(path)

    parts = [p.strip() for p in override.split(",") if p.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        return to_abs(parts[0])
    return tuple(to_abs(p) for p in parts)


_override_env_file = _resolve_env_files_from_override(REPO_ROOT)

# Ensure consistent type for settings across branches for type checkers
settings: Settings
if _override_env_file:
    # Recreate settings with runtime-provided env file(s) by updating model_config
    # Pydantic v2: model_config can be provided via class attribute; emulate by subclassing on the fly
    class _RuntimeSettings(Settings):
        model_config = SettingsConfigDict(
            env_prefix="GTC_",
            env_file=_override_env_file,  # type: ignore[arg-type]
            env_file_encoding="utf-8",
            extra="forbid",
        )

    settings = _RuntimeSettings()
else:
    # If no explicit override, auto-apply local overlays when present so secrets
    # can live in uncommitted files.
    # Order: default committed env -> overlays (later overrides earlier)
    default_env = REPO_ROOT / "environments" / "sample.env"
    overlay_candidates = [
        REPO_ROOT / "environments" / "development.local.env",
        REPO_ROOT / "environments" / "local.env",
    ]
    overlays: list[str] = [str(p) for p in overlay_candidates if p.exists()]

    if overlays:

        class _AutoOverlaySettings(Settings):
            model_config = SettingsConfigDict(
                env_prefix="GTC_",
                env_file=(str(default_env), *overlays),  # type: ignore[arg-type]
                env_file_encoding="utf-8",
                extra="forbid",
            )

        settings = _AutoOverlaySettings()
    else:
        settings = Settings()


def log_settings() -> None:
    """Log settings at startup. SecretStr fields are automatically masked."""
    logger.info("Configuration loaded: %s", settings)


# --- Sampling allocation helpers ---
def parse_sampling_allocation_env(value: str) -> dict[str, float]:
    """Parse CSV allocations like "dataset1:50,dataset2:50".

    Returns a raw mapping of dataset -> weight (float). Does not normalize.
    Invalid entries are ignored.
    """
    if not value:
        return {}
    res: dict[str, float] = {}
    parts = [p.strip() for p in value.split(",") if p.strip()]
    for part in parts:
        if ":" not in part:
            continue
        ds, w = part.split(":", 1)
        ds = ds.strip()
        try:
            weight = float(w.strip())
        except Exception:
            continue
        if not ds:
            continue
        res[ds] = weight
    return res


def normalize_allocation(weights: dict[str, float]) -> dict[str, float]:
    """Filter nonpositive entries and normalize to sum to 1.0.

    If inputs are empty or sum to <= 0 after filtering, return {}.
    """
    filtered: dict[str, float] = {k: float(v) for k, v in weights.items() if float(v) > 0}
    if not filtered:
        return {}
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in filtered.items()}


def get_sampling_allocation() -> dict[str, float]:
    """Read sampling allocation via Settings and return normalized weights.

    Primary source is settings.SAMPLING_ALLOCATION (mapped from GTC_SAMPLING_ALLOCATION).
    For compatibility in tests or ad-hoc runs where settings wasn't initialized with
    that value, we fall back to reading the environment directly.
    Supports only CSV form for now: "dsA:50,dsB:25,dsC:25". Returns {} if missing/invalid.
    """
    raw = settings.SAMPLING_ALLOCATION or os.getenv("GTC_SAMPLING_ALLOCATION", "")
    if raw is not None:
        raw = raw.strip()
    if not raw:
        return {}
    parsed = parse_sampling_allocation_env(raw)
    return normalize_allocation(parsed)


# IMPORTANT: Do not reassign `settings` again here. The instance above has
# already been created with respect to the optional GTC_ENV_FILE override.
