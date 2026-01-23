"""Tests for the /v1/tags/glossary endpoint."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_tag_definitions_repo():
    """Mock the tag_definitions_repo to avoid database dependency."""
    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])  # Return empty list by default
    return repo


@pytest.fixture(autouse=True)
def patch_tag_definitions_repo(mock_tag_definitions_repo):
    """Auto-patch tag_definitions_repo for all tests in this module."""
    with patch("app.container.container.tag_definitions_repo", mock_tag_definitions_repo):
        yield


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


def test_glossary_includes_custom_definitions(
    client: TestClient, mock_tag_definitions_repo
) -> None:
    """Test that the glossary endpoint includes custom tag definitions from the database."""
    from app.domain.models import TagDefinition
    from datetime import datetime, timezone

    # Mock custom definitions
    custom_defs = [
        TagDefinition(
            id="priority:urgent",
            tag_key="priority:urgent",
            description="Requires immediate attention",
            created_by="test@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        TagDefinition(
            id="category:marketing",
            tag_key="category:marketing",
            description="Marketing-related content",
            created_by="test@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    ]
    mock_tag_definitions_repo.list_all.return_value = custom_defs

    response = client.get("/v1/tags/glossary")

    assert response.status_code == 200
    data = response.json()

    # Find custom group
    custom_groups = [g for g in data["groups"] if g["type"] == "custom"]
    assert len(custom_groups) == 1

    custom_group = custom_groups[0]
    assert custom_group["name"] == "custom"
    assert custom_group["description"] == "Custom tags created by subject matter experts"
    assert len(custom_group["tags"]) == 2

    # Verify custom tags
    priority_tag = next((t for t in custom_group["tags"] if t["key"] == "priority:urgent"), None)
    assert priority_tag is not None
    assert priority_tag["description"] == "Requires immediate attention"

    category_tag = next((t for t in custom_group["tags"] if t["key"] == "category:marketing"), None)
    assert category_tag is not None
    assert category_tag["description"] == "Marketing-related content"
