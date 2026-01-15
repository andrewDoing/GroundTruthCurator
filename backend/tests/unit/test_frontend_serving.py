from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.anyio
async def test_frontend_disabled_no_static_mount(monkeypatch):
    # Ensure FRONTEND_DIR is not set
    monkeypatch.delenv("GTC_FRONTEND_DIR", raising=False)
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
        assert r.status_code in (404, 307, 308)  # may redirect to docs if enabled


@pytest.mark.anyio
async def test_frontend_enabled_serves_index_html(tmp_path: Path, monkeypatch):
    (tmp_path / "index.html").write_text("<html><body>Hello SPA</body></html>")
    monkeypatch.setenv("GTC_FRONTEND_DIR", str(tmp_path))
    from importlib import reload
    import app.core.config as config

    reload(config)
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
        assert r.status_code == 200
        assert "Hello SPA" in r.text


@pytest.mark.anyio
async def test_spa_fallback_for_deep_route(tmp_path: Path, monkeypatch):
    (tmp_path / "index.html").write_text("<html><body>Deep Route</body></html>")
    monkeypatch.setenv("GTC_FRONTEND_DIR", str(tmp_path))
    from importlib import reload
    import app.core.config as config

    reload(config)
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/foo/bar")
        assert r.status_code == 200
        assert "Deep Route" in r.text


@pytest.mark.anyio
async def test_api_routes_not_intercepted_by_frontend(tmp_path: Path, monkeypatch):
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setenv("GTC_FRONTEND_DIR", str(tmp_path))
    from importlib import reload
    import app.core.config as config

    reload(config)
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/v1/openapi.json")
        assert r.status_code == 200
        r2 = await ac.get("/v1/docs")
        assert r2.status_code in (200, 307, 308)
