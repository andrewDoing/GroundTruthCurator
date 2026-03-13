from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.container import container
from app.core.config import settings


@pytest.mark.anyio
async def test_demo_mode_seeds_memory_backend_for_api_usage() -> None:
    from app.main import create_app

    lifespan = pytest.importorskip("asgi_lifespan")
    LifespanManager = lifespan.LifespanManager

    original_settings = {
        "REPO_BACKEND": settings.REPO_BACKEND,
        "DEMO_MODE": settings.DEMO_MODE,
        "DEMO_USER_ID": settings.DEMO_USER_ID,
    }
    original_container: dict[str, Any] = {
        "repo": getattr(container, "repo", None),
        "assignment_service": getattr(container, "assignment_service", None),
        "search_service": getattr(container, "search_service", None),
        "snapshot_service": getattr(container, "snapshot_service", None),
        "curation_service": getattr(container, "curation_service", None),
        "tag_registry_service": getattr(container, "tag_registry_service", None),
        "tags_repo": getattr(container, "tags_repo", None),
        "tag_definitions_repo": getattr(container, "tag_definitions_repo", None),
    }

    settings.REPO_BACKEND = "memory"
    settings.DEMO_MODE = True
    settings.DEMO_USER_ID = "anonymous"

    container.repo = None

    app = create_app()

    try:
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                assignments = await client.get("/v1/assignments/my")
                assert assignments.status_code == 200
                assignment_items = assignments.json()
                assert len(assignment_items) == 2
                assert {item["id"] for item in assignment_items} == {
                    "demo-data-overage",
                    "demo-hotspot-weekend",
                }

                search = await client.get("/v1/search", params={"q": "data", "top": 5})
                assert search.status_code == 200
                assert search.json()["results"]

                stats = await client.get("/v1/ground-truths/stats")
                assert stats.status_code == 200
                assert stats.json() == {"draft": 2, "approved": 1, "deleted": 1}

                datasets = await client.get("/v1/datasets")
                assert datasets.status_code == 200
                assert set(datasets.json()) == {"customer-feedback", "network-diagnostics"}

                instructions = await client.get(
                    "/v1/datasets/customer-feedback/curation-instructions"
                )
                assert instructions.status_code == 200
                assert "Customer Feedback Demo Instructions" in instructions.json()["instructions"]
    finally:
        settings.REPO_BACKEND = original_settings["REPO_BACKEND"]
        settings.DEMO_MODE = original_settings["DEMO_MODE"]
        settings.DEMO_USER_ID = original_settings["DEMO_USER_ID"]
        for attr, value in original_container.items():
            setattr(container, attr, value)
