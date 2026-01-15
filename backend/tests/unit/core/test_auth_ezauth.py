from __future__ import annotations

import base64
import json
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core.auth import (
    build_principal_from_claims,
    install_ezauth_middleware,
    is_identity_allowed,
    parse_ms_client_principal,
)
from app.core.config import settings


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def test_parse_ms_client_principal_decodes_base64_json(monkeypatch: pytest.MonkeyPatch):
    payload = {"claims": [{"typ": "oid", "val": "abc"}, {"typ": "name", "val": "n"}]}
    headers = {"X-MS-CLIENT-PRINCIPAL": b64(json.dumps(payload))}
    parsed = parse_ms_client_principal(headers)
    assert parsed == payload


def test_parse_ms_client_principal_handles_missing_header():
    assert parse_ms_client_principal({}) is None


def test_build_principal_from_claims_populates_core_fields():
    payload = {
        "claims": [
            {"typ": "oid", "val": "00000000-0000-0000-0000-000000000001"},
            {"typ": "name", "val": "Ada"},
            {"typ": "preferred_username", "val": "ada@example.com"},
            {"typ": "roles", "val": "curator"},
            {"typ": "roles", "val": "admin"},
        ]
    }
    p = build_principal_from_claims(payload)
    assert p.oid == "00000000-0000-0000-0000-000000000001"
    assert p.name == "Ada"
    assert p.email == "ada@example.com"
    assert set(p.roles) == {"curator", "admin"}


def test_is_identity_allowed_by_object_id(monkeypatch: pytest.MonkeyPatch):
    from app.core.auth import Principal

    p = Principal(oid="00000000-0000-0000-0000-000000000001", name=None, email=None, roles=[])
    monkeypatch.setattr(
        settings, "EZAUTH_ALLOWED_OBJECT_IDS", "A,B,C,00000000-0000-0000-0000-000000000001"
    )
    monkeypatch.setattr(settings, "EZAUTH_ALLOWED_EMAIL_DOMAINS", None, raising=False)
    assert is_identity_allowed(p)


def test_is_identity_allowed_by_email_domain(monkeypatch: pytest.MonkeyPatch):
    from app.core.auth import Principal

    p = Principal(oid=None, name=None, email="someone@example.com", roles=[])
    monkeypatch.setattr(settings, "EZAUTH_ALLOWED_OBJECT_IDS", None, raising=False)
    monkeypatch.setattr(settings, "EZAUTH_ALLOWED_EMAIL_DOMAINS", "example.com,contoso.com")
    assert is_identity_allowed(p)


def test_is_identity_allowed_denies_when_not_matched(monkeypatch: pytest.MonkeyPatch):
    from app.core.auth import Principal

    p = Principal(oid="Z", name=None, email="nobody@example.com", roles=[])
    monkeypatch.setattr(settings, "EZAUTH_ALLOWED_OBJECT_IDS", "A,B")
    monkeypatch.setattr(settings, "EZAUTH_ALLOWED_EMAIL_DOMAINS", "contoso.com")
    assert not is_identity_allowed(p)


def _app_with_mw(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    monkeypatch.setattr(settings, "EZAUTH_ENABLED", True)
    monkeypatch.setattr(settings, "EZAUTH_ALLOW_ANONYMOUS_PATHS", "/healthz")
    install_ezauth_middleware(app)

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.get("/protected")
    def protected():
        return {"ok": True}

    return TestClient(app)


def test_require_user_raises_401_when_missing(monkeypatch: pytest.MonkeyPatch):
    c = _app_with_mw(monkeypatch)
    r = c.get("/protected")
    assert r.status_code == 401


def test_require_user_raises_403_when_disallowed(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    monkeypatch.setattr(settings, "EZAUTH_ENABLED", True)
    monkeypatch.setattr(settings, "EZAUTH_ALLOWED_EMAIL_DOMAINS", "contoso.com")
    monkeypatch.setattr(settings, "EZAUTH_ALLOW_ANONYMOUS_PATHS", "/healthz")
    install_ezauth_middleware(app)

    @app.get("/protected")
    def protected():
        return {"ok": True}

    payload = {"claims": [{"typ": "emails", "val": "nobody@example.com"}]}
    headers = {"X-MS-CLIENT-PRINCIPAL": b64(json.dumps(payload))}
    c = TestClient(app)
    r = c.get("/protected", headers=headers)
    assert r.status_code == 403
