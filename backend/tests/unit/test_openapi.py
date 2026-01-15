import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_openapi_under_versioned_prefix(async_client: AsyncClient):
    # openapi.json should be served under /v1 per settings.API_PREFIX
    r = await async_client.get("/v1/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert data.get("openapi") is not None
    assert data.get("info", {}).get("title") == "Ground Truth Curator"


@pytest.mark.anyio
async def test_docs_routes_exist(async_client: AsyncClient):
    # Swagger and Redoc HTML should be served under /v1
    r1 = await async_client.get("/v1/docs")
    assert r1.status_code == 200
    assert "Swagger UI" in r1.text

    r2 = await async_client.get("/v1/redoc")
    assert r2.status_code == 200
    assert "ReDoc" in r2.text


@pytest.mark.anyio
async def test_list_component_schemas(async_client: AsyncClient):
    r = await async_client.get("/v1/schemas")
    assert r.status_code == 200
    schemas = r.json()
    assert isinstance(schemas, list)
    # Should contain some built-in validation error schemas
    assert any("HTTPValidationError" == s for s in schemas)


@pytest.mark.anyio
async def test_get_specific_schema(async_client: AsyncClient):
    r = await async_client.get("/v1/schemas/HTTPValidationError")
    assert r.status_code == 200
    schema = r.json()
    assert isinstance(schema, dict)
    assert schema.get("title") == "HTTPValidationError"

    # Unknown should 404
    r2 = await async_client.get("/v1/schemas/DOES_NOT_EXIST")
    assert r2.status_code == 404
