"""Unit tests for TagDefinitionsRepo."""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.repos.tag_definitions_repo import CosmosTagDefinitionsRepo
from app.domain.models import TagDefinition


@pytest.fixture
def mock_container():
    """Create a mock Cosmos container."""
    container = AsyncMock()
    container.read = AsyncMock()
    container.query_items = AsyncMock()
    container.read_item = AsyncMock()
    container.upsert_item = AsyncMock()
    container.delete_item = AsyncMock()
    return container


@pytest.fixture
def mock_client(mock_container):
    """Create a mock Cosmos client."""
    client = AsyncMock()
    db = AsyncMock()
    db.get_container_client = MagicMock(return_value=mock_container)
    db.read = AsyncMock()
    client.get_database_client = MagicMock(return_value=db)
    return client


@pytest_asyncio.fixture
async def repo(mock_client):
    """Create a TagDefinitionsRepo instance with mocked client."""
    repo = CosmosTagDefinitionsRepo(
        endpoint="https://test.documents.azure.com:443/",
        key="test_key",
        db_name="test_db",
        container_name="tag_definitions",
    )
    with patch.object(CosmosTagDefinitionsRepo, "_init", new_callable=AsyncMock):
        repo._client = mock_client
        repo._db = mock_client.get_database_client("test_db")
        repo._container = repo._db.get_container_client("tag_definitions")
        yield repo


@pytest.mark.asyncio
async def test_get_definition_found(repo, mock_container):
    """Test retrieving an existing tag definition."""
    tag_key = "source:custom"
    mock_doc = {
        "id": tag_key,
        "tag_key": tag_key,
        "description": "Custom tag for testing",
        "created_by": "test@example.com",
        "createdAt": "2026-01-23T00:00:00Z",
        "updatedAt": "2026-01-23T00:00:00Z",
        "docType": "tag-definition",
    }
    mock_container.read_item.return_value = mock_doc

    result = await repo.get_definition(tag_key)

    assert result is not None
    assert result.tag_key == tag_key
    assert result.description == "Custom tag for testing"
    assert result.created_by == "test@example.com"
    mock_container.read_item.assert_called_once_with(item=tag_key, partition_key=tag_key)


@pytest.mark.asyncio
async def test_get_definition_not_found(repo, mock_container):
    """Test retrieving a non-existent tag definition returns None."""
    from azure.cosmos.exceptions import CosmosHttpResponseError

    tag_key = "source:nonexistent"
    error = CosmosHttpResponseError(status_code=404, message="Not found")
    mock_container.read_item.side_effect = error

    result = await repo.get_definition(tag_key)

    assert result is None
    mock_container.read_item.assert_called_once_with(item=tag_key, partition_key=tag_key)


@pytest.mark.asyncio
async def test_list_all(repo, mock_container):
    """Test listing all tag definitions."""
    mock_docs = [
        {
            "id": "source:custom1",
            "tag_key": "source:custom1",
            "description": "First custom tag",
            "created_by": "user1@example.com",
            "createdAt": "2026-01-23T00:00:00Z",
            "updatedAt": "2026-01-23T00:00:00Z",
            "docType": "tag-definition",
        },
        {
            "id": "quality:reviewed",
            "tag_key": "quality:reviewed",
            "description": "Reviewed by SME",
            "created_by": "user2@example.com",
            "createdAt": "2026-01-23T01:00:00Z",
            "updatedAt": "2026-01-23T01:00:00Z",
            "docType": "tag-definition",
        },
    ]

    # Create async generator for query results
    async def async_gen():
        for doc in mock_docs:
            yield doc

    # Make query_items a regular function that returns async generator
    mock_container.query_items = lambda **kwargs: async_gen()

    result = await repo.list_all()

    assert len(result) == 2
    assert result[0].tag_key == "source:custom1"
    assert result[1].tag_key == "quality:reviewed"


@pytest.mark.asyncio
async def test_upsert_new_definition(repo, mock_container):
    """Test creating a new tag definition."""
    definition = TagDefinition(
        id="source:new",
        tag_key="source:new",
        description="New custom tag",
        created_by="test@example.com",
    )

    # Mock the upsert response
    mock_response = {
        "id": definition.tag_key,
        "tag_key": definition.tag_key,
        "description": definition.description,
        "created_by": definition.created_by,
        "createdAt": definition.created_at.isoformat(),
        "updatedAt": definition.updated_at.isoformat(),
        "docType": "tag-definition",
    }
    mock_container.upsert_item.return_value = mock_response

    result = await repo.upsert(definition)

    assert result.tag_key == "source:new"
    assert result.description == "New custom tag"
    mock_container.upsert_item.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_updates_timestamp(repo, mock_container):
    """Test that upsert updates the updated_at timestamp."""
    original_time = datetime(2026, 1, 23, 0, 0, 0, tzinfo=timezone.utc)
    definition = TagDefinition(
        id="source:existing",
        tag_key="source:existing",
        description="Existing tag",
        created_by="test@example.com",
        created_at=original_time,
        updated_at=original_time,
    )

    mock_response = {
        "id": definition.tag_key,
        "tag_key": definition.tag_key,
        "description": definition.description,
        "created_by": definition.created_by,
        "createdAt": original_time.isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "docType": "tag-definition",
    }
    mock_container.upsert_item.return_value = mock_response

    result = await repo.upsert(definition)

    # updated_at should be more recent than created_at
    assert result.updated_at >= result.created_at


@pytest.mark.asyncio
async def test_delete(repo, mock_container):
    """Test deleting a tag definition."""
    tag_key = "source:obsolete"
    mock_container.delete_item.return_value = None

    await repo.delete(tag_key)

    mock_container.delete_item.assert_called_once_with(item=tag_key, partition_key=tag_key)


@pytest.mark.asyncio
async def test_list_all_skips_malformed_items(repo, mock_container):
    """Test that list_all skips malformed items gracefully."""
    mock_docs = [
        {
            "id": "source:good",
            "tag_key": "source:good",
            "description": "Valid tag",
            "created_by": "user@example.com",
            "createdAt": "2026-01-23T00:00:00Z",
            "updatedAt": "2026-01-23T00:00:00Z",
            "docType": "tag-definition",
        },
        {
            # Missing required fields - should be skipped
            "id": "source:bad",
            "tag_key": "source:bad",
        },
    ]

    async def async_gen():
        for doc in mock_docs:
            yield doc

    mock_container.query_items = lambda **kwargs: async_gen()

    result = await repo.list_all()

    # Only the valid item should be returned
    assert len(result) == 1
    assert result[0].tag_key == "source:good"
