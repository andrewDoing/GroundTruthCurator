"""
Tests for Cosmos DB query performance monitoring.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo


@pytest.mark.asyncio
async def test_execute_query_with_metrics_respects_slow_query_threshold():
    """Verify that slow query threshold is respected."""
    repo = CosmosGroundTruthRepo(
        endpoint="http://localhost:8081",
        key="test-key",
        db_name="test-db",
        gt_container_name="ground_truth",
        assignments_container_name="assignments",
        test_mode=True,
    )

    # Mock container with low RU charge
    mock_container = MagicMock()
    mock_iterator = MagicMock()
    mock_iterator._last_response_headers = {"x-ms-request-charge": "2.5"}

    async def mock_iter(self):
        yield {"id": "1"}

    mock_iterator.__aiter__ = lambda self: mock_iter(self)
    mock_container.query_items.return_value = mock_iterator

    # Enable metrics but only log slow queries (threshold = 10.0)
    with patch("app.core.config.settings.COSMOS_LOG_QUERY_METRICS", True):
        with patch("app.core.config.settings.COSMOS_LOG_SLOW_QUERIES_ONLY", True):
            with patch("app.core.config.settings.COSMOS_SLOW_QUERY_RU_THRESHOLD", 10.0):
                from unittest.mock import MagicMock as Mock

                mock_logger = Mock()
                repo._logger = mock_logger

                # Execute query with metrics
                results = await repo._execute_query_with_metrics(
                    container=mock_container,
                    query="SELECT * FROM c",
                    parameters=[],
                    operation_name="fast_query",
                    enable_scan_in_query=True,
                )

    # Verify logger was NOT called (query too fast)
    mock_logger.info.assert_not_called()


@pytest.mark.asyncio
async def test_execute_query_with_metrics_handles_missing_headers():
    """Verify graceful handling when RU headers are unavailable."""
    repo = CosmosGroundTruthRepo(
        endpoint="http://localhost:8081",
        key="test-key",
        db_name="test-db",
        gt_container_name="ground_truth",
        assignments_container_name="assignments",
        test_mode=True,
    )

    # Mock container without response headers
    mock_container = MagicMock()
    mock_iterator = MagicMock()
    # No _last_response_headers attribute

    async def mock_iter(self):
        yield {"id": "1"}

    mock_iterator.__aiter__ = lambda self: mock_iter(self)
    mock_container.query_items.return_value = mock_iterator

    with patch("app.core.config.settings.COSMOS_LOG_QUERY_METRICS", True):
        with patch("app.core.config.settings.COSMOS_LOG_SLOW_QUERIES_ONLY", False):
            # Should not raise exception even without headers
            results = await repo._execute_query_with_metrics(
                container=mock_container,
                query="SELECT * FROM c",
                parameters=[],
                operation_name="test_query",
                enable_scan_in_query=True,
            )

    # Verify query still executed successfully
    assert len(results) == 1
    assert results[0]["id"] == "1"


@pytest.mark.asyncio
async def test_execute_query_with_metrics_disabled_by_default():
    """Verify that metrics logging is disabled by default."""
    repo = CosmosGroundTruthRepo(
        endpoint="http://localhost:8081",
        key="test-key",
        db_name="test-db",
        gt_container_name="ground_truth",
        assignments_container_name="assignments",
        test_mode=True,
    )

    mock_container = MagicMock()
    mock_iterator = MagicMock()
    mock_iterator._last_response_headers = {"x-ms-request-charge": "12.5"}

    async def mock_iter(self):
        yield {"id": "1"}

    mock_iterator.__aiter__ = lambda self: mock_iter(self)
    mock_container.query_items.return_value = mock_iterator

    # Default setting (COSMOS_LOG_QUERY_METRICS = False)
    from unittest.mock import MagicMock as Mock

    mock_logger = Mock()
    repo._logger = mock_logger

    results = await repo._execute_query_with_metrics(
        container=mock_container,
        query="SELECT * FROM c",
        parameters=[],
        operation_name="test_query",
        enable_scan_in_query=True,
    )

    # Verify logger was NOT called (metrics disabled by default)
    mock_logger.info.assert_not_called()
