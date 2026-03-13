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


@pytest.mark.anyio
async def test_ground_truth_openapi_uses_agentic_schema(async_client: AsyncClient):
    r = await async_client.get("/v1/openapi.json")
    assert r.status_code == 200

    data = r.json()
    import_request = data["paths"]["/v1/ground-truths"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["items"]["$ref"]
    update_response = data["paths"]["/v1/ground-truths/{datasetName}/{bucket}/{item_id}"]["put"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]["$ref"]

    assert "AgenticGroundTruthEntry" in import_request
    assert "AgenticGroundTruthEntry" in update_response
    assert "GroundTruthItem" not in import_request


@pytest.mark.anyio
async def test_update_requests_do_not_advertise_nullable_expected_tools(async_client: AsyncClient):
    r = await async_client.get("/v1/openapi.json")
    assert r.status_code == 200

    data = r.json()
    schemas = data["components"]["schemas"]

    assignment_expected_tools = schemas["AssignmentUpdateRequest"]["properties"]["expectedTools"]
    ground_truth_expected_tools = schemas["GroundTruthUpdateRequest"]["properties"]["expectedTools"]

    assert assignment_expected_tools["$ref"] == "#/components/schemas/ExpectedTools"
    assert ground_truth_expected_tools["$ref"] == "#/components/schemas/ExpectedTools"
    assert "anyOf" not in assignment_expected_tools
    assert "anyOf" not in ground_truth_expected_tools


@pytest.mark.anyio
async def test_update_requests_share_stable_history_patch_schema(async_client: AsyncClient):
    r = await async_client.get("/v1/openapi.json")
    assert r.status_code == 200

    data = r.json()
    schemas = data["components"]["schemas"]

    assignment_history = schemas["AssignmentUpdateRequest"]["properties"]["history"]["anyOf"][0][
        "items"
    ]["$ref"]
    ground_truth_history = schemas["GroundTruthUpdateRequest"]["properties"]["history"]["anyOf"][0][
        "items"
    ]["$ref"]

    assert assignment_history == "#/components/schemas/HistoryEntryPatch"
    assert ground_truth_history == "#/components/schemas/HistoryEntryPatch"
    assert "HistoryEntryPatch" in schemas
