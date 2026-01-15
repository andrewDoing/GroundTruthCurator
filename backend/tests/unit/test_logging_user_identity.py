import logging
from fastapi.testclient import TestClient

# NOTE: Do NOT import the global `app` from app.main here. In CI, environment
# variables may enable Easy Auth (EZAUTH_ENABLED=true) which would cause the
# globally-created app (with auth middleware installed) to return 401 for this
# test route. Instead we rely on the `live_app` fixture defined in
# `tests/unit/conftest.py` which force-disables Easy Auth before creating a
# fresh FastAPI instance. This keeps the test deterministic across local and CI.


def _ensure_test_route(app):  # type: ignore[no-untyped-def]
    """Idempotently register a lightweight route that emits a log event.

    We check for the path first so multiple tests (or re-imports) don't
    register duplicate routes.
    """
    if any(getattr(r, "path", None) == "/_test_log" for r in app.router.routes):
        return

    @app.get("/_test_log")
    def _test_log_route():  # type: ignore[no-untyped-def]
        logging.getLogger("app.test").info("test log event")
        return {"ok": True}


def _extract_user_ids(caplog):
    return [getattr(r, "user_id", None) for r in caplog.records]


def test_logs_include_user_identity(caplog, live_app):
    _ensure_test_route(live_app)
    client = TestClient(live_app)
    test_user = "test_user_123"
    with caplog.at_level(logging.INFO):
        resp = client.get("/_test_log", headers={"X-User-Id": test_user})
        assert resp.status_code == 200
    user_ids = _extract_user_ids(caplog)
    assert test_user in user_ids


def test_logs_include_anonymous_when_no_header(caplog, live_app):
    _ensure_test_route(live_app)
    client = TestClient(live_app)
    with caplog.at_level(logging.INFO):
        resp = client.get("/_test_log")
        assert resp.status_code == 200
    user_ids = _extract_user_ids(caplog)
    assert "anonymous" in user_ids
