import os
import logging
import tomllib  # Python 3.11 stdlib for TOML parsing
from fastapi import FastAPI, Depends
from importlib.metadata import PackageNotFoundError, version as pkg_version
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse
from pathlib import Path
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.core.config as config
from app.core.config import log_settings
from app.core.telemetry import init_telemetry
from app.core.auth import install_ezauth_middleware, require_user
from app.core.logging import setup_logging, user_logging_middleware, attach_trace_log_filter
from app.api.v1.router import api_router
from app.container import container
from app.domain.tags import TAG_SCHEMA
from app.domain.manual_tags_provider import JsonFileManualTagProvider, expand_manual_tags
from app.plugins import get_default_registry

logger = logging.getLogger("gtc.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log configuration at startup (SecretStr fields are masked)
    log_settings()

    registry = get_default_registry()
    computed = set(registry.get_static_keys())

    # Validate configuration-derived tag allowlist doesn't collide
    # with computed tags; collisions make it impossible to interpret
    # whether a tag was manually set or computed.
    if config.settings.ALLOWED_MANUAL_TAGS:
        manual = {
            t.strip() for t in config.settings.ALLOWED_MANUAL_TAGS.split(",") if t and t.strip()
        }
        overlap = sorted(manual.intersection(computed))
        if overlap:
            raise RuntimeError(
                "GTC_ALLOWED_MANUAL_TAGS overlaps computed tag keys: " + ", ".join(overlap)
            )

    # Validate manual tag defaults do not overlap computed tags.
    manual_defaults = expand_manual_tags(
        JsonFileManualTagProvider(
            Path(config.settings.MANUAL_TAGS_CONFIG_PATH)
        ).get_default_tag_groups()
    )
    if manual_defaults:
        overlap = sorted(set(manual_defaults).intersection(computed))
        if overlap:
            raise RuntimeError(
                "Manual tag defaults overlap computed tag keys: " + ", ".join(overlap)
            )

    # Lazily initialize repo (creates Cosmos DB/container if configured)
    try:
        # In test mode, fixtures configure the repo/tags repo and we must not
        # re-initialize here (it can rebind clients to a different event loop
        # and overwrite per-test DB names). Only initialize in non-test mode.
        if not config.settings.COSMOS_TEST_MODE:
            # Wire repository and services based on configured backend
            if config.settings.REPO_BACKEND.lower() == "cosmos":
                await container.startup_cosmos()
            # Seed built-in tags into global tag registry (idempotent add)
            try:
                defaults = sorted(
                    f"{group}:{value}"
                    for group, spec in TAG_SCHEMA.items()
                    for value in sorted(spec.values)
                )
                await container.tag_registry_service.add_tags(defaults)
            except Exception:
                # Do not block startup on tag registry failures
                pass
    except Exception:
        # Don't block startup; emulator may not be ready yet
        pass
    yield
    # Shutdown cleanup is handled in tests by fixtures when running under pytest.


PKG_NAME = "backend"


def resolve_version() -> str:
    """Resolve application version.

    Resolution order:
    1. Installed distribution metadata (importlib.metadata)
    2. pyproject.toml [project].version (when running from source tree w/out install)
    3. APP_VERSION env var
    4. Ultimate hardcoded fallback
    """
    try:
        return pkg_version(PKG_NAME)
    except PackageNotFoundError:
        pass

    # Attempt to read pyproject.toml directly (source checkout / dev mode)
    try:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject_path.is_file():
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            ver = project.get("version")
            if isinstance(ver, str) and ver.strip():
                return ver.strip()
    except Exception:
        # Silent: fall through to environment fallback
        pass

    return os.getenv("APP_VERSION", "0.0.0+unknown")


APP_VERSION = resolve_version()
print(APP_VERSION)


def create_app() -> FastAPI:
    setup_logging(config.settings.LOG_LEVEL)
    # Ensure trace/user filters are attached early so any startup logs include context fields
    try:
        attach_trace_log_filter()
    except Exception:
        pass
    app = FastAPI(
        title="Ground Truth Curator",
        version=APP_VERSION,
        lifespan=lifespan,
        # Serve OpenAPI and docs under the versioned API prefix so the frontend
        # can fetch definitions from a stable, namespaced path.
        openapi_url=f"{config.settings.API_PREFIX}/openapi.json",
        docs_url=f"{config.settings.API_PREFIX}/docs",
        redoc_url=f"{config.settings.API_PREFIX}/redoc",
    )

    # NOTE: CORS middleware is intentionally NOT installed here. Runtime CORS
    # policy is enforced via the Azure Container Apps platform configuration.
    # This avoids duplicate/conflicting policy definitions in code vs infra.

    @app.get("/healthz")
    async def _healthz() -> dict[str, str]:
        """Health check endpoint for ACA liveness/readiness probes."""
        return {"status": "ok"}

    # Install Easy Auth middleware if enabled
    try:
        install_ezauth_middleware(app)
    except Exception:
        # Never block app creation due to auth middleware
        pass

    # Inject user identity into logging for every request (after auth middleware)
    try:
        user_logging_middleware(app)
    except Exception:
        pass

    # Mount versioned API (protection enforced by middleware and per-route deps)
    app.include_router(api_router, prefix=config.settings.API_PREFIX)
    # Initialize search wiring (no-op if not configured)
    try:
        container.init_search()
    except Exception:
        # Don't block app creation if search isn't configured
        pass
    try:
        container.init_chat()
    except Exception:
        # Chat wiring is optional and should not block startup
        pass

    # Convenience aliases at the root for Swagger UI
    # Root convenience redirects for docs should also enforce auth (same as /v1/docs)
    @app.get("/docs", include_in_schema=False, dependencies=[Depends(require_user)])
    def _root_docs_redirect() -> RedirectResponse:
        return RedirectResponse(url=app.docs_url or "/")

    @app.get("/swagger", include_in_schema=False, dependencies=[Depends(require_user)])
    def _root_swagger_redirect() -> RedirectResponse:
        return RedirectResponse(url=app.docs_url or "/")

    # Optional static frontend serving
    def _get_frontend_dir() -> Path | None:
        if not config.settings.FRONTEND_DIR:
            return None
        d = Path(config.settings.FRONTEND_DIR)
        try:
            if d.is_dir() and (d / config.settings.FRONTEND_INDEX).is_file():
                return d
        except Exception:
            return None
        return None

    frontend_dir = _get_frontend_dir()
    if frontend_dir:

        class SPAStaticFiles(StaticFiles):
            # Serve index.html for any 404 to support client-side routing
            async def get_response(self, path: str, scope):  # type: ignore[override]
                try:
                    return await super().get_response(path, scope)
                except (
                    StarletteHTTPException
                ) as exc:  # pragma: no cover - behavior tested via requests
                    if exc.status_code == 404:
                        return await super().get_response(config.settings.FRONTEND_INDEX, scope)
                    raise

        app.mount("/", SPAStaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        app.state.spa_enabled = True
        app.state.frontend_dir = str(frontend_dir)
    else:
        app.state.spa_enabled = False

    # Reference route functions so static analyzers mark them as used. FastAPI
    # registers these via decorators, but tools may not recognize that usage.
    _ = (_healthz, _root_docs_redirect, _root_swagger_redirect)

    # Initialize telemetry (no-op if disabled or not configured)
    try:
        init_telemetry(app, config.settings)
    except Exception:
        # Never block app creation on telemetry issues
        pass

    return app


app = create_app()
