from __future__ import annotations

from typing import Any, cast

import pytest
from httpx import AsyncClient

from app.plugins import get_default_registry
from app.core.config import settings
from app.main import create_app


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_get_tags_empty_on_fresh_store(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    r = await async_client.get("/v1/tags", headers=user_headers)
    assert r.status_code == 200
    data = cast(dict[str, Any], r.json())
    assert data["tags"] == []
    # computedTags should still be present from plugins
    assert "computedTags" in data
    assert isinstance(data["computedTags"], list)


@pytest.mark.anyio
async def test_create_app_rejects_manual_allowlist_overlap_with_computed_tags(
    async_client: AsyncClient,
    user_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    # Choose a computed tag key and inject it into the manual allowlist.
    computed_key = next(iter(get_default_registry().get_static_keys()))
    monkeypatch.setattr(settings, "ALLOWED_MANUAL_TAGS", f"topic:general,{computed_key}")

    # Trigger startup; the lifespan validation should reject the overlap.
    with pytest.raises(RuntimeError, match="overlaps computed tag keys"):
        async with create_app().router.lifespan_context(None):
            pass


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_get_tags_uses_allowed_manual_tags_env(
    async_client: AsyncClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "ALLOWED_MANUAL_TAGS", "topic:general,source:sme")
    r = await async_client.get("/v1/tags", headers=user_headers)
    assert r.status_code == 200
    data = cast(dict[str, Any], r.json())
    assert data["tags"] == ["source:sme", "topic:general"]
    assert "computedTags" in data


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_get_tags_returns_separate_fields(
    async_client: AsyncClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    """GET /v1/tags returns manual tags in 'tags' and computed tags in 'computedTags'."""
    # Ensure allowlist isn't set for this flow
    monkeypatch.setattr(settings, "ALLOWED_MANUAL_TAGS", None)

    # Add a manual tag
    await async_client.post("/v1/tags", headers=user_headers, json={"tags": ["source:sme"]})
    r = await async_client.get("/v1/tags", headers=user_headers)
    assert r.status_code == 200
    data = r.json()

    # Response should have both fields
    assert "tags" in data
    assert "computedTags" in data

    # Manual tag should be in 'tags' field only
    assert "source:sme" in data["tags"]

    # Computed tags should be in 'computedTags' field
    registry = get_default_registry()
    computed_keys = registry.get_static_keys()

    # All computed tags should be present in computedTags
    for computed_tag in computed_keys:
        assert computed_tag in data["computedTags"]
        # Computed tags should NOT be in manual tags field
        assert computed_tag not in data["tags"]


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_get_tags_computed_tags_sorted(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """computedTags field is sorted alphabetically."""
    r = await async_client.get("/v1/tags", headers=user_headers)
    assert r.status_code == 200
    data = r.json()
    computed_tags = data["computedTags"]
    assert computed_tags == sorted(computed_tags)


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_post_adds_and_returns_updated_list(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    r = await async_client.post("/v1/tags", headers=user_headers, json={"tags": [" source : SME "]})
    assert r.status_code == 200
    data = r.json()
    assert data["tags"] == ["source:sme"]
    # computedTags should also be in response
    assert "computedTags" in data
    assert isinstance(data["computedTags"], list)
    # GET reflects
    r2 = await async_client.get("/v1/tags", headers=user_headers)
    assert r2.status_code == 200
    assert r2.json()["tags"] == ["source:sme"]
    assert "computedTags" in r2.json()


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_delete_removes_and_returns_updated_list(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    await async_client.post(
        "/v1/tags", headers=user_headers, json={"tags": ["topic:science", "source:sme"]}
    )
    r = await async_client.request(
        "DELETE", "/v1/tags", headers=user_headers, json={"tags": ["topic:science"]}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tags"] == ["source:sme"]
    # computedTags should also be in response
    assert "computedTags" in data
    assert isinstance(data["computedTags"], list)


@pytest.mark.anyio
async def test_post_rejects_invalid_format_with_400(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    r = await async_client.post(
        "/v1/tags", headers=user_headers, json={"tags": ["invalid-no-colon"]}
    )
    assert r.status_code == 400


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_idempotency_add_remove_sequences(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    await async_client.post(
        "/v1/tags", headers=user_headers, json={"tags": ["source:sme", "source:sme"]}
    )
    await async_client.post("/v1/tags", headers=user_headers, json={"tags": ["topic:science"]})
    r = await async_client.get("/v1/tags", headers=user_headers)
    assert r.json()["tags"] == ["source:sme", "topic:science"]
    # Remove twice
    await async_client.request(
        "DELETE", "/v1/tags", headers=user_headers, json={"tags": ["topic:science"]}
    )
    r2 = await async_client.request(
        "DELETE", "/v1/tags", headers=user_headers, json={"tags": ["topic:science"]}
    )
    assert r2.status_code == 200
    assert r2.json()["tags"] == ["source:sme"]
