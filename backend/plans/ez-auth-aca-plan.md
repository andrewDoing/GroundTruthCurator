## Overview

Goal: Add first-cut support for Azure Container Apps (ACA) Easy Auth in our FastAPI backend. We will rely on ACA’s built-in Authentication/Authorization to handle sign-in and inject identity headers. In the app, we’ll read those headers, create a minimal user principal, and enforce simple allow rules on protected routes. Keep it simple; no legacy or non-ACA auth fallback.

What we’ll implement now
- Assume ACA is configured with Easy Auth enabled.
- Parse identity from injected headers on each request.
- Provide a lightweight dependency to require an authenticated user on protected endpoints.
- Allow anonymous access only for health/metrics or explicitly whitelisted routes.
- Minimal authorization rule: allow by email domain and/or explicit object IDs from config.

Out of scope (later)
- Multi-provider mapping beyond Microsoft (AAD) details.
- Role-based access control, groups sync, or token validation against JWKS.
- Session management, refresh tokens, logout UX.


## ACA configuration (infrastructure expectations)

We will configure ACA Easy Auth and route behavior outside the app:
- Enable Easy Auth and set unauthenticated behavior to one of:
  - Require authentication (best for browser clients, redirects unauthenticated).
  - Allow anonymous + enforce in code (best for API clients). For now, we’ll prefer AllowAnonymous and enforce per-route in the app.
- Exclude health probe paths: "/healthz,/metrics".
- Microsoft Entra (AAD) provider configured with client credentials; secrets stored on the Container App.

Example (CLI) – reference only; not executed by the app code:
- Enable Easy Auth and allow anonymous (we’ll gatekeep in code):
  - az containerapp auth update --enabled true --require-https true \
    --unauthenticated-client-action AllowAnonymous --excluded-paths "/healthz,/metrics"
- Configure Microsoft provider:
  - az containerapp auth microsoft update --client-id <APP_CLIENT_ID> --client-secret-setting-name ENTRA_CLIENT_SECRET
  - az containerapp secret set --secrets ENTRA_CLIENT_SECRET=<secret_value>


## Files to change

- app/core/config.py
  - Add settings controlling Easy Auth behavior and allowed identities:
    - EZAUTH_ENABLED (bool), EZAUTH_ALLOW_ANONYMOUS_PATHS (list of paths), EZAUTH_ALLOWED_EMAIL_DOMAINS (list), EZAUTH_ALLOWED_OBJECT_IDS (list), EZAUTH_HEADER_SOURCE (string: "aca").
- app/core/auth.py
  - Implement minimal Easy Auth helpers: parse ACA identity headers, build a principal model, and dependency for FastAPI routes.
- app/main.py
  - Wire a small middleware/dependency strategy: attach principal to request state; optionally apply a global dependency for protected routers.
- app/api/v1/*
  - Apply dependency (e.g., Depends(require_user)) to protected endpoints; leave healthz/metrics unprotected.
- docs/ez-auth-notes.md (optional)
  - Link to this plan and capture any operator guidance.
- environments/*
  - Add placeholders for new config variables.


## Function contracts (names and purpose)

In app/core/auth.py
- parse_ms_client_principal(headers: dict) -> dict | None
  - Reads ACA’s X-MS-CLIENT-PRINCIPAL (base64 JSON) and returns a dict of claims or None if missing/invalid. Falls back to X-MS-CLIENT-PRINCIPAL-NAME for username when present.
- build_principal_from_claims(claims: dict) -> "Principal"
  - Converts claims into a minimal Principal object with id (oid), name, email, and roles (if present). Handles absent fields gracefully.
- is_identity_allowed(principal: "Principal", settings) -> bool
  - Returns True if the principal’s oid is in allowed IDs or the email domain is in allowed domains from settings.
- get_current_principal(request) -> "Principal | None"
  - Extracts and caches Principal on request.state if available; returns None when headers are missing.
- require_user(request) -> "Principal"
  - FastAPI dependency for protected routes. Raises 401 if no principal; raises 403 if principal exists but is not allowed by settings.

In app/main.py
- install_ezauth_middleware(app)
  - Registers a lightweight middleware to parse and attach Principal to request.state early in the pipeline when EZAUTH_ENABLED is true.


## Test plan (names and behaviors)

Unit tests (tests/unit/core/test_auth_ezauth.py)
- test_parse_ms_client_principal_decodes_base64_json
  - Decodes header and returns expected claims map.
- test_parse_ms_client_principal_handles_missing_header
  - Missing header returns None without raising.
- test_build_principal_from_claims_populates_core_fields
  - oid, name, email resolved from claims if present.
- test_is_identity_allowed_by_object_id
  - Allowed when principal.oid is in allowlist.
- test_is_identity_allowed_by_email_domain
  - Allowed when email domain matches allowed domains.
- test_is_identity_allowed_denies_when_not_matched
  - Denied if neither allow rule matches.
- test_require_user_raises_401_when_missing
  - No principal present yields 401 Unauthorized.
- test_require_user_raises_403_when_disallowed
  - Principal present but not allowed yields 403 Forbidden.

Integration tests (tests/integration/test_auth_ezauth.py)
- test_healthz_allows_anonymous
  - /healthz reachable without identity headers.
- test_protected_route_requires_identity
  - Protected route returns 401 without Easy Auth headers.
- test_protected_route_allows_valid_domain
  - Returns 200 when email domain allowed.
- test_protected_route_allows_allowlisted_oid
  - Returns 200 when oid allowlisted regardless of domain.
- test_protected_route_denies_invalid_identity
  - Returns 403 for identities failing allow rules.


## Configuration

New environment variables (documented and added to environments/*.env):
- EZAUTH_ENABLED=true|false
- EZAUTH_ALLOW_ANONYMOUS_PATHS=/healthz,/metrics (comma-separated)
- EZAUTH_ALLOWED_EMAIL_DOMAINS=example.com (comma-separated)
- EZAUTH_ALLOWED_OBJECT_IDS=00000000-0000-0000-0000-000000000000 (comma-separated)
- EZAUTH_HEADER_SOURCE=aca (default "aca" to clarify semantics)

Default posture
- Enabled in integration and production ACA environments.
- Anonymous allowed only for health/metrics by default.


## Minimal change steps

1) Config
- Add settings to app/core/config.py with sensible defaults.
- Update environments/integration-tests.env to include placeholders.

2) Identity parsing and dependency
- Add helpers and Principal model to app/core/auth.py.
- Add require_user dependency and use on protected routers.

3) Wiring
- In app/main.py, install_ezauth_middleware when EZAUTH_ENABLED.
- Ensure /healthz and /metrics remain public.

4) Tests
- Add unit tests for parsing and allow logic.
- Add small integration tests that simulate ACA headers on requests.

5) Docs
- Cross-link docs/ez-auth-notes.md with a brief reference to this plan.


## Acceptance criteria

- When EZAUTH_ENABLED=true, protected routes return 401 without identity headers, 403 for disallowed identities, and 200 for allowed identities.
- Health/metrics endpoints remain accessible without identity.
- No legacy or non-ACA authentication code is introduced.
- All new unit tests pass locally and in CI; integration tests pass in emulator/integration runs with simulated headers.


## Risks and edges (not over-engineered)

- Header shape variations: prioritize X-MS-CLIENT-PRINCIPAL; fall back to X-MS-CLIENT-PRINCIPAL-NAME for name/email if needed.
- Missing or malformed base64: treat as unauthenticated; do not crash.
- Email-less principals: rely on OID allowlist in that case.
- Redirect vs. allow-anonymous: we default to code-enforced protection; infra may switch to RedirectToLogin without code change.
