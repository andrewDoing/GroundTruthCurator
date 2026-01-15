import pytest


@pytest.mark.anyio
async def test_schema_endpoint_returns_expected_shape(async_client):
    r = await async_client.get("/v1/tags/schema")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "v1"
    groups = data["groups"]
    assert isinstance(groups, list)
    # basic shape for one group
    g0 = groups[0]
    assert set(g0.keys()) == {"name", "values", "exclusive", "depends_on"}
    # deterministic sorting by name
    names = [g["name"] for g in groups]
    assert names == sorted(names)
