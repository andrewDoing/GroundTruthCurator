"""Phase 1 review rework regression tests.

Tests cover:
- IV-001: approve=true bulk import enforces generic approval validation
- IV-002: Assignment route history edits reset totalReferences
- IV-003: Invalid status values rejected with HTTP 400 on both routes
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fastapi import HTTPException

from app.domain.models import AgenticGroundTruthEntry, BulkImportResult, HistoryEntry
from app.domain.enums import GroundTruthStatus


class TestBulkImportApprovalValidation:
    """Test IV-001: approve=true bulk import enforces generic approval validation."""

    @pytest.mark.asyncio
    async def test_bulk_import_approve_rejects_items_without_history(self):
        """Bulk import with approve=true should reject items that lack conversation history."""
        from app.core.auth import UserContext
        from app.container import container

        # Prepare invalid item: no history, no question/answer
        invalid_item = AgenticGroundTruthEntry(
            id=str(uuid4()),
            datasetName="test-dataset",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
        )

        payload = [invalid_item]

        # Mock dependencies
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(return_value=BulkImportResult(imported=0, errors=[]))
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            mock_user = UserContext(user_id="test-user")

            # Import the bulk_import function directly
            from app.api.v1.ground_truths import import_bulk

            result = await import_bulk(
                items=payload,
                user=mock_user,
                buckets=1,
                approve=True,
            )

            # Should have errors for items that don't meet approval criteria
            errors = result.errors
            assert len(errors) > 0

            # Check that approval validation error was raised
            approval_errors = [e for e in errors if e.code == "APPROVAL_VALIDATION_FAILED"]
            assert len(approval_errors) > 0

            # Verify history requirement is in the error message
            error_messages = [e.message for e in approval_errors]
            assert any("history" in msg.lower() for msg in error_messages)

            # No items should have been imported
            assert result.imported == 0

        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_bulk_import_approve_accepts_valid_items(self):
        """Bulk import with approve=true should accept items that meet approval criteria."""
        from app.core.auth import UserContext
        from app.container import container

        # Prepare valid item with history
        valid_item = AgenticGroundTruthEntry(
            id=str(uuid4()),
            datasetName="test-dataset",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="What is the capital of France?"),
                HistoryEntry(role="assistant", msg="The capital of France is Paris."),
            ],
        )

        payload = [valid_item]

        # Mock dependencies
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(return_value=BulkImportResult(imported=1, errors=[]))
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            mock_user = UserContext(user_id="test-user")

            from app.api.v1.ground_truths import import_bulk

            result = await import_bulk(
                items=payload,
                user=mock_user,
                buckets=1,
                approve=True,
            )

            # Should succeed with no errors
            assert result.imported == 1
            assert len(result.errors) == 0

        finally:
            container.repo = original_repo


class TestAssignmentHistoryReset:
    """Test IV-002: Assignment route history edits reset totalReferences."""

    @pytest.mark.asyncio
    async def test_assignment_update_history_resets_total_references(self):
        """When history is updated via assignment route, totalReferences should be reset to 0."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.assignments import update_item

        dataset = "test-dataset"
        bucket = str(uuid4())
        item_id = str(uuid4())

        # Create existing item with stale totalReferences
        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName=dataset,
            bucket=bucket,
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Old question"),
                HistoryEntry(role="assistant", msg="Old answer"),
            ],
            totalReferences=5,  # Stale value
            _etag="test-etag",
        )

        # Mock dependencies
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)
        
        # Mock upsert to capture what gets saved
        saved_item = None
        async def mock_upsert(item):
            nonlocal saved_item
            saved_item = item
            return item
        
        container.repo.upsert_gt = AsyncMock(side_effect=mock_upsert)

        try:
            mock_user = UserContext(user_id="test-user")

            # Payload with updated history
            from app.api.v1.assignments import AssignmentUpdateRequest
            payload = AssignmentUpdateRequest(
                history=[
                    {"role": "user", "msg": "New question"},
                    {"role": "assistant", "msg": "New answer"},
                ],
                etag="test-etag",
            )

            result = await update_item(
                dataset=dataset,
                bucket=bucket,
                item_id=item_id,
                payload=payload,
                user=mock_user,
                if_match=None,
            )

            # Verify totalReferences was reset to 0
            assert saved_item is not None
            assert saved_item.totalReferences == 0

        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_assignment_clear_history_resets_total_references(self):
        """When history is cleared via assignment route, totalReferences should be reset to 0."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.assignments import update_item

        dataset = "test-dataset"
        bucket = str(uuid4())
        item_id = str(uuid4())

        # Create existing item with history and totalReferences
        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName=dataset,
            bucket=bucket,
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Question"),
                HistoryEntry(role="assistant", msg="Answer"),
            ],
            totalReferences=3,
            _etag="test-etag",
        )

        # Mock dependencies
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)
        
        saved_item = None
        async def mock_upsert(item):
            nonlocal saved_item
            saved_item = item
            return item
        
        container.repo.upsert_gt = AsyncMock(side_effect=mock_upsert)

        try:
            mock_user = UserContext(user_id="test-user")

            from app.api.v1.assignments import AssignmentUpdateRequest
            payload = AssignmentUpdateRequest(
                history=None,  # Clear history
                etag="test-etag",
            )

            result = await update_item(
                dataset=dataset,
                bucket=bucket,
                item_id=item_id,
                payload=payload,
                user=mock_user,
                if_match=None,
            )

            # Verify totalReferences was reset to 0
            assert saved_item is not None
            assert saved_item.totalReferences == 0

        finally:
            container.repo = original_repo


class TestInvalidStatusRejection:
    """Test IV-003: Invalid status values rejected with HTTP 400 on both routes."""

    @pytest.mark.asyncio
    async def test_ground_truths_route_rejects_invalid_status(self):
        """Ground truths update route should reject invalid status with HTTP 400."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import update_ground_truth

        dataset = "test-dataset"
        bucket = str(uuid4())
        item_id = str(uuid4())

        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName=dataset,
            bucket=bucket,
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            _etag="test-etag",
        )

        # Mock dependencies
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)

        try:
            mock_user = UserContext(user_id="test-user")

            from app.api.v1.ground_truths import GroundTruthUpdateRequest
            payload = GroundTruthUpdateRequest(
                status="invalid-status",  # Invalid status
                etag="test-etag",
            )

            # Should raise HTTPException with 400
            with pytest.raises(HTTPException) as exc_info:
                await update_ground_truth(
                    datasetName=dataset,
                    bucket=bucket,
                    item_id=item_id,
                    payload=payload,
                    user=mock_user,
                    if_match=None,
                )

            assert exc_info.value.status_code == 400
            assert "invalid status value" in exc_info.value.detail.lower()

        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_assignments_route_rejects_invalid_status(self):
        """Assignments update route should reject invalid status with HTTP 400."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.assignments import update_item

        dataset = "test-dataset"
        bucket = str(uuid4())
        item_id = str(uuid4())

        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName=dataset,
            bucket=bucket,
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            assignedTo="test-user",
            _etag="test-etag",
        )

        # Mock dependencies
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)

        try:
            mock_user = UserContext(user_id="test-user")

            from app.api.v1.assignments import AssignmentUpdateRequest
            payload = AssignmentUpdateRequest(
                status="bogus-status",  # Invalid status
                etag="test-etag",
            )

            # Should raise HTTPException with 400
            with pytest.raises(HTTPException) as exc_info:
                await update_item(
                    dataset=dataset,
                    bucket=bucket,
                    item_id=item_id,
                    payload=payload,
                    user=mock_user,
                    if_match=None,
                )

            assert exc_info.value.status_code == 400
            assert "invalid status value" in exc_info.value.detail.lower()

        finally:
            container.repo = original_repo
