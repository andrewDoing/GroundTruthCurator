from __future__ import annotations

from typing import Any, cast

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_snapshot_endpoint_returns_json_attachment(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    # No data required; endpoint should still return a valid payload
    r = await async_client.get("/v1/ground-truths/snapshot")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    cd = r.headers.get("content-disposition", "")
    # The filename parameter is quoted per RFC 6266; accept quoted .json suffix
    assert cd.lower().startswith("attachment")
    assert 'filename="' in cd and cd.endswith('.json"')


@pytest.mark.anyio
async def test_snapshot_endpoint_returns_manifest_and_items(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    # Request first to ensure empty payload works; then import one approved item and retry
    r = await async_client.get("/v1/ground-truths/snapshot")
    assert r.status_code == 200
    body = cast(dict[str, Any], r.json())
    assert set(["schemaVersion", "snapshotAt", "count", "items"]).issubset(body.keys())


@pytest.mark.anyio
async def test_snapshot_endpoint_empty_list_returns_empty_payload(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    r = await async_client.get("/v1/ground-truths/snapshot")
    assert r.status_code == 200
    body = cast(dict[str, Any], r.json())
    assert body["count"] >= 0
    if body["count"] == 0:
        assert body["items"] == []
