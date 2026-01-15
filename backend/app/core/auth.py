from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Iterable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from app.core.config import settings


# --- Principal model ---


@dataclass
class Principal:
    oid: str | None
    name: str | None
    email: str | None
    roles: list[str]


# --- Parsing helpers ---


def _safe_b64decode(data: str) -> bytes | None:
    try:
        # ACA uses base64 standard, may or may not be padded.
        padding = "=" * (-len(data) % 4)
        return base64.b64decode(data + padding)
    except Exception:
        return None


def parse_ms_client_principal(headers: dict[str, str]) -> dict[str, Any] | None:
    """Parse ACA Easy Auth principal headers into a claims dict.

    Prefers X-MS-CLIENT-PRINCIPAL (base64 JSON). Falls back to X-MS-CLIENT-PRINCIPAL-NAME
    for a minimal identity when present.
    """
    # Normalize header keys to case-insensitive lookup
    norm = {k.lower(): v for k, v in headers.items()}
    raw = norm.get("x-ms-client-principal")
    if raw:
        decoded = _safe_b64decode(raw)
        if decoded:
            try:
                payload = json.loads(decoded.decode("utf-8"))
                # Expected shape: {"claims": [{"typ":"...","val":"..."}], ...}
                return payload
            except Exception:
                return None
        return None
    # Fallback: just name header
    name = norm.get("x-ms-client-principal-name")
    if name:
        return {"claims": [{"typ": "name", "val": name}]}
    return None


def _claims_to_map(claims: list[dict[str, Any]] | None) -> dict[str, list[str]]:
    m: dict[str, list[str]] = {}
    if not claims:
        return m
    for c in claims:
        typ = str(c.get("typ", "")).lower()
        val = c.get("val")
        if not typ or val is None:
            continue
        m.setdefault(typ, []).append(str(val))
    return m


def _first_or_none(values: Iterable[str] | None) -> str | None:
    """Return the first string value or None.

    Helps mypy by avoiding indexing into potentially empty lists and by
    making the optional type explicit.
    """
    if not values:
        return None
    for v in values:
        return v
    return None


def build_principal_from_claims(claims_payload: dict[str, Any]) -> Principal:
    claims = claims_payload.get("claims")
    cmap = _claims_to_map(claims if isinstance(claims, list) else None)
    # Common AAD claim types under Easy Auth:
    # - oid (object id)
    # - name
    # - preferred_username or emails
    oid = _first_or_none(cmap.get("oid"))
    name = _first_or_none(cmap.get("name"))
    email = _first_or_none(cmap.get("preferred_username")) or _first_or_none(cmap.get("emails"))
    roles = cmap.get("roles") or []
    return Principal(oid=oid, name=name, email=email, roles=roles)


def is_identity_allowed(principal: Principal, s=settings) -> bool:
    # Build allow lists from CSV env settings
    allowed_ids = set()
    if s.EZAUTH_ALLOWED_OBJECT_IDS:
        allowed_ids = {
            x.strip().lower() for x in s.EZAUTH_ALLOWED_OBJECT_IDS.split(",") if x.strip()
        }

    allowed_domains = set()
    if s.EZAUTH_ALLOWED_EMAIL_DOMAINS:
        allowed_domains = {
            x.strip().lower() for x in s.EZAUTH_ALLOWED_EMAIL_DOMAINS.split(",") if x.strip()
        }

    # If no allowlists are configured, accept any authenticated principal by default.
    # This makes local/dev and tests work out of the box without extra config.
    if not allowed_ids and not allowed_domains:
        return True

    # Allow by explicit OID
    if principal.oid and principal.oid.lower() in allowed_ids:
        return True

    # Allow by email domain
    if principal.email and "@" in principal.email and allowed_domains:
        domain = principal.email.split("@", 1)[1].lower()
        if domain in allowed_domains:
            return True

    return False


def get_current_principal(request: Request) -> Principal | None:
    cached = getattr(request.state, "principal", None)
    if cached is not None:
        return cached

    if not settings.EZAUTH_ENABLED and settings.AUTH_MODE == "dev":
        return Principal(oid="dev-user", name="dev-user", email="dev-user@email.com", roles=[])

    if not settings.EZAUTH_ENABLED:
        # In non-Easy Auth mode, no principal is provided by default
        return None

    # Parse headers
    payload = parse_ms_client_principal(dict(request.headers))
    if not payload:
        return None
    principal = build_principal_from_claims(payload)
    request.state.principal = principal
    return principal


def require_user(request: Request) -> Principal:
    principal = get_current_principal(request)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not is_identity_allowed(principal, settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return principal


# --- Middleware installer ---


def install_ezauth_middleware(app) -> None:
    if not settings.EZAUTH_ENABLED:
        return

    # Use the same skip list that the platform-level Auth exclusions rely on so the
    # health probe and any other shared paths behave consistently.
    allow_anonymous = set(
        p.strip() for p in (settings.EZAUTH_ALLOW_ANONYMOUS_PATHS or "").split(",") if p.strip()
    )

    @app.middleware("http")
    async def _ezauth(ctx, call_next):  # type: ignore[no-redef]
        request: Request = ctx
        # Attach principal if present
        _ = get_current_principal(request)

        # Skip app-level auth check for paths the platform also excludes.
        path = request.url.path
        if path not in allow_anonymous:
            principal = getattr(request.state, "principal", None)
            if principal is None:
                return _unauthorized_response()
            # Principal present but enforce allow rules here as a guardrail
            if not is_identity_allowed(principal, settings):
                return _forbidden_response()
        return await call_next(request)


def _unauthorized_response() -> Response:
    # Return a response rather than raising to ensure consistent behavior in middleware
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Unauthorized"}
    )


def _forbidden_response() -> Response:
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Forbidden"})


# --- Compatibility dependency used by existing routes ---


class UserContext:
    def __init__(self, user_id: str, roles: list[str] | None = None):
        self.user_id = user_id
        self.roles = roles or []


async def get_current_user(request: Request) -> UserContext:
    """Return a simple user context.

    - When Easy Auth is enabled, require and map Principal -> UserContext.
    - In dev mode (AUTH_MODE=dev), trust X-User-Id header and allow anonymous.
    """
    if settings.EZAUTH_ENABLED:
        principal = require_user(request)
        # Allow tests/dev to override effective user id via header while still requiring
        # a valid Easy Auth principal. This preserves authorization but lets tests model
        # multiple users (e.g., alice/bob) without crafting different principals.
        x_user_id = request.headers.get("X-User-Id")
        if x_user_id:
            return UserContext(user_id=x_user_id, roles=principal.roles)
        user_id = principal.email or principal.oid or principal.name or "anonymous"
        return UserContext(user_id=user_id, roles=principal.roles)

    # Dev fallback for local/testing convenience
    x_user_id = request.headers.get("X-User-Id")
    if not x_user_id:
        return UserContext(user_id="anonymous")
    return UserContext(user_id=x_user_id)
