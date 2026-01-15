import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.domain.models import GroundTruthItem, BulkImportResult
from app.core.auth import UserContext


@pytest.fixture
def mock_container():
    container = MagicMock()
    container.tag_registry_service = AsyncMock()
    container.repo = AsyncMock()
    return container


@pytest.fixture
def mock_user():
    user = MagicMock(spec=UserContext)
    user.user_id = "test-user"
    return user


@pytest.mark.anyio
async def test_bulk_import_validates_tags(mock_container, mock_user):
    """Test that bulk import validates tags against registry."""
    # Setup
    mock_container.tag_registry_service.list_tags = AsyncMock(
        return_value=["source:synthetic", "topic:general"]
    )
    mock_container.repo.import_bulk_gt = AsyncMock(
        return_value=BulkImportResult(imported=1, errors=[])
    )

    items = [
        GroundTruthItem(
            id="test-1",
            datasetName="test",
            synthQuestion="What is Q?",
            manualTags=["source:synthetic"],
        )
    ]

    # Execute with patched container (patch both ground_truths and validation_service)
    with (
        patch("app.api.v1.ground_truths.container", mock_container),
        patch("app.services.validation_service.container", mock_container),
    ):
        from app.api.v1.ground_truths import import_bulk

        result = await import_bulk(items, user=mock_user, buckets=None, approve=False)

    # Assert
    assert result.imported == 1
    assert len(result.errors) == 0
    mock_container.tag_registry_service.list_tags.assert_called_once()
    mock_container.repo.import_bulk_gt.assert_called_once()


@pytest.mark.anyio
async def test_bulk_import_rejects_invalid_tags(mock_container, mock_user):
    """Test that invalid tags are rejected."""
    mock_container.tag_registry_service.list_tags = AsyncMock(return_value=["source:synthetic"])
    # Should return 0 imported when called with empty list
    mock_container.repo.import_bulk_gt = AsyncMock(
        return_value=BulkImportResult(imported=0, errors=[])
    )

    items = [
        GroundTruthItem(
            id="test-1", datasetName="test", synthQuestion="What is Q?", manualTags=["invalid:tag"]
        )
    ]

    # Execute with patched container (patch both ground_truths and validation_service)
    with (
        patch("app.api.v1.ground_truths.container", mock_container),
        patch("app.services.validation_service.container", mock_container),
    ):
        from app.api.v1.ground_truths import import_bulk

        result = await import_bulk(items, user=mock_user, buckets=None, approve=False)

    # Assert
    assert result.imported == 0
    assert len(result.errors) == 1
    assert "invalid:tag" in result.errors[0]
    mock_container.tag_registry_service.list_tags.assert_called_once()
    # Repo should be called with empty list since no valid items
    mock_container.repo.import_bulk_gt.assert_not_called()


@pytest.mark.anyio
async def test_bulk_import_mixed_valid_invalid_tags(mock_container, mock_user):
    """Test that only items with valid tags are imported."""
    mock_container.tag_registry_service.list_tags = AsyncMock(
        return_value=["source:synthetic", "topic:general"]
    )
    mock_container.repo.import_bulk_gt = AsyncMock(
        return_value=BulkImportResult(imported=1, errors=[])
    )

    items = [
        GroundTruthItem(
            id="test-1",
            datasetName="test",
            synthQuestion="Q1?",
            manualTags=["source:synthetic"],  # valid
        ),
        GroundTruthItem(
            id="test-2",
            datasetName="test",
            synthQuestion="Q2?",
            manualTags=["invalid:tag"],  # invalid
        ),
    ]

    # Execute with patched container (patch both ground_truths and validation_service)
    with (
        patch("app.api.v1.ground_truths.container", mock_container),
        patch("app.services.validation_service.container", mock_container),
    ):
        from app.api.v1.ground_truths import import_bulk

        result = await import_bulk(items, user=mock_user, buckets=None, approve=False)

    # Assert
    assert result.imported == 1
    assert len(result.errors) == 1
    assert "invalid:tag" in result.errors[0]
    assert "test-2" in result.errors[0]
    mock_container.repo.import_bulk_gt.assert_called_once()

    # Check that only the valid item was passed to the repo
    called_args = mock_container.repo.import_bulk_gt.call_args[0][0]
    assert len(called_args) == 1
    assert called_args[0].id == "test-1"


@pytest.mark.anyio
async def test_bulk_import_no_tags(mock_container, mock_user):
    """Test that items with no tags are imported successfully."""
    mock_container.repo.import_bulk_gt = AsyncMock(
        return_value=BulkImportResult(imported=1, errors=[])
    )

    items = [
        GroundTruthItem(
            id="test-1",
            datasetName="test",
            synthQuestion="What is Q?",
            manualTags=[],  # no tags
        )
    ]

    # Execute with patched container (patch both ground_truths and validation_service)
    with (
        patch("app.api.v1.ground_truths.container", mock_container),
        patch("app.services.validation_service.container", mock_container),
    ):
        from app.api.v1.ground_truths import import_bulk

        result = await import_bulk(items, user=mock_user, buckets=None, approve=False)

    # Assert
    assert result.imported == 1
    assert len(result.errors) == 0
    # tag_registry_service should not be called for items without tags
    mock_container.tag_registry_service.list_tags.assert_not_called()
    mock_container.repo.import_bulk_gt.assert_called_once()


@pytest.mark.anyio
async def test_bulk_import_tag_validation_single_registry_fetch(mock_container, mock_user):
    """Verify tag registry is fetched only once for multiple items."""
    mock_container.tag_registry_service.list_tags = AsyncMock(return_value=["source:synthetic"])
    mock_container.repo.import_bulk_gt = AsyncMock(
        return_value=BulkImportResult(imported=10, errors=[])
    )

    items = [
        GroundTruthItem(
            id=f"test-{i}",
            datasetName="test",
            synthQuestion=f"Q{i}?",
            manualTags=["source:synthetic"],
        )
        for i in range(10)
    ]

    with (
        patch("app.api.v1.ground_truths.container", mock_container),
        patch("app.services.validation_service.container", mock_container),
    ):
        from app.api.v1.ground_truths import import_bulk

        await import_bulk(items, user=mock_user, buckets=None, approve=False)

    # Assert: Should call list_tags only ONCE, not 10 times
    assert mock_container.tag_registry_service.list_tags.call_count == 1
