"""Tests for the /v1/tags/glossary endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_glossary_endpoint_returns_manual_tags_with_descriptions(client: TestClient) -> None:
    """Test that the glossary endpoint returns manual tags with descriptions."""
    response = client.get("/v1/tags/glossary")

    assert response.status_code == 200
    data = response.json()

    assert "version" in data
    assert data["version"] == "v1"

    assert "groups" in data
    groups = data["groups"]

    # Should have manual tag groups
    manual_groups = [g for g in groups if g["type"] == "manual"]
    assert len(manual_groups) > 0

    # Check that source group has descriptions
    source_group = next((g for g in manual_groups if g["name"] == "source"), None)
    assert source_group is not None
    assert source_group["description"] == "Origin of the ground truth content"

    # Check that tags have descriptions
    sme_tag = next((t for t in source_group["tags"] if t["key"] == "source:sme"), None)
    assert sme_tag is not None
    assert sme_tag["description"] == "Created by subject matter expert"


def test_glossary_endpoint_includes_computed_tags(client: TestClient) -> None:
    """Test that the glossary endpoint includes computed tags."""
    response = client.get("/v1/tags/glossary")

    assert response.status_code == 200
    data = response.json()

    groups = data["groups"]

    # Should have computed tag group
    computed_groups = [g for g in groups if g["type"] == "computed"]
    assert len(computed_groups) == 1

    computed_group = computed_groups[0]
    assert computed_group["name"] == "computed"
    assert computed_group["description"] == "Automatically computed tags based on item content"
    assert len(computed_group["tags"]) > 0


def test_glossary_schema_structure(client: TestClient) -> None:
    """Test that the glossary response has the expected structure."""
    response = client.get("/v1/tags/glossary")

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert isinstance(data["version"], str)
    assert isinstance(data["groups"], list)

    for group in data["groups"]:
        assert "name" in group
        assert "type" in group
        assert "tags" in group
        assert group["type"] in ["manual", "computed", "custom"]

        for tag in group["tags"]:
            assert "key" in tag
            # description is optional
