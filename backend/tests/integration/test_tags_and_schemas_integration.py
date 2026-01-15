from __future__ import annotations

from typing import Any, cast

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_get_tags_schema(async_client: AsyncClient, user_headers: dict[str, str]):
    r = await async_client.get("/v1/tags/schema", headers=user_headers)
    assert r.status_code == 200
    body = cast(dict[str, Any], r.json())
    assert "groups" in body and isinstance(body["groups"], list)
    # Groups should have names and values
    if body["groups"]:
        g0 = cast(dict[str, Any], body["groups"][0])
        assert "name" in g0 and "values" in g0


@pytest.mark.anyio
async def test_schemas_endpoints(async_client: AsyncClient, user_headers: dict[str, str]):
    # list schemas
    r = await async_client.get("/v1/schemas", headers=user_headers)
    assert r.status_code == 200
    arr = cast(list[dict[str, Any]], r.json())
    assert isinstance(arr, list)
    assert any("name" in x for x in arr)

    # pick first schema name and fetch it
    if arr:
        name = cast(str, arr[0].get("name") or arr[0].get("title") or "")
        if name:
            r = await async_client.get(f"/v1/schemas/{name}", headers=user_headers)
            assert r.status_code == 200
            schema = cast(dict[str, Any], r.json())
            assert isinstance(schema, dict)
