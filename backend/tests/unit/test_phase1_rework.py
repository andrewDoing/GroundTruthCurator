"""Phase 1 review rework regression tests.

Tests cover:
- IV-001: approve=true bulk import enforces generic approval validation
- IV-002: Assignment route history edits reset totalReferences
- IV-003: Invalid status values rejected with HTTP 400 on both routes
- RR-001: Explicit status: null rejected with HTTP 400 on both update routes
- RR-002: Bulk import failed count reports unique failed items, not raw error count
- RR-003: Bulk import approval errors carry original request indices
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fastapi import HTTPException

from app.domain.models import (
    AgenticGroundTruthEntry,
    BulkImportPersistenceError,
    BulkImportResult,
    HistoryEntry,
)
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

    @pytest.mark.asyncio
    async def test_bulk_import_approve_enforces_plugin_pack_approval_hooks(self):
        """Plugin-pack approval errors must block bulk approve=true entries (R-001).

        Regression test: the bulk import approval path must run
        validate_item_for_approval() (which includes
        plugin_pack_registry.collect_approval_errors) rather than the
        generic-only collect_approval_validation_errors().
        """
        from app.core.auth import UserContext
        from app.container import container

        # A structurally valid item — generic core would approve it.
        valid_item = AgenticGroundTruthEntry(
            id=str(uuid4()),
            datasetName="test-dataset",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Which city is the capital of France?"),
                HistoryEntry(role="assistant", msg="Paris."),
            ],
        )

        original_repo = container.repo
        original_registry = container.plugin_pack_registry
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(
            return_value=BulkImportResult(imported=0, errors=[])
        )
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        # Inject a mock plugin-pack registry that returns a pack-level error.
        mock_registry = AsyncMock()
        mock_registry.collect_approval_errors = lambda _item: [
            "plugin-pack: retrieval reference is incomplete"
        ]
        container.plugin_pack_registry = mock_registry

        try:
            mock_user = UserContext(user_id="test-user")
            from app.api.v1.ground_truths import import_bulk

            result = await import_bulk(
                items=[valid_item],
                user=mock_user,
                buckets=1,
                approve=True,
            )

            # The plugin-pack error must surface as an APPROVAL_VALIDATION_FAILED entry.
            approval_errors = [e for e in result.errors if e.code == "APPROVAL_VALIDATION_FAILED"]
            assert len(approval_errors) >= 1, (
                "Expected at least one APPROVAL_VALIDATION_FAILED error from plugin-pack hook"
            )
            assert any(
                "plugin-pack" in e.message for e in approval_errors
            ), "Error message should contain plugin-pack content"

            # Original request index must be preserved (0 for a single-item request).
            assert all(e.index == 0 for e in approval_errors)

            # No items should have been imported.
            assert result.imported == 0

        finally:
            container.repo = original_repo
            container.plugin_pack_registry = original_registry


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


class TestNullStatusRejection:
    """RR-001: Explicit status: null must be rejected with HTTP 400 on both update routes."""

    @pytest.mark.asyncio
    async def test_ground_truth_route_rejects_null_status(self):
        """Ground truths PUT route must return HTTP 400 for explicit status: null."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import update_ground_truth, GroundTruthUpdateRequest

        item_id = str(uuid4())
        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            _etag="e1",
        )
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)

        try:
            payload = GroundTruthUpdateRequest.model_validate({"status": None, "etag": "e1"})
            with pytest.raises(HTTPException) as exc_info:
                await update_ground_truth(
                    datasetName="ds",
                    bucket=existing_item.bucket,
                    item_id=item_id,
                    payload=payload,
                    user=UserContext(user_id="u1"),
                    if_match=None,
                )
            assert exc_info.value.status_code == 400
            assert "null" in exc_info.value.detail.lower()
        finally:
            container.repo = original_repo


class TestNullExpectedToolsRejection:
    """RR-002: Explicit expectedTools: null must be rejected with HTTP 400 on both update routes."""

    @pytest.mark.asyncio
    async def test_ground_truth_route_rejects_null_expected_tools(self):
        """Ground truths PUT route must return HTTP 400 for explicit expectedTools: null."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import update_ground_truth, GroundTruthUpdateRequest

        item_id = str(uuid4())
        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            _etag="e1",
        )
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)

        try:
            payload = GroundTruthUpdateRequest.model_validate({"expectedTools": None, "etag": "e1"})
            with pytest.raises(HTTPException) as exc_info:
                await update_ground_truth(
                    datasetName="ds",
                    bucket=existing_item.bucket,
                    item_id=item_id,
                    payload=payload,
                    user=UserContext(user_id="u1"),
                    if_match=None,
                )
            assert exc_info.value.status_code == 400
            assert "expectedtools" in exc_info.value.detail.lower()
            assert "null" in exc_info.value.detail.lower()
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_assignments_route_rejects_null_expected_tools(self):
        """Assignments PUT route must return HTTP 400 for explicit expectedTools: null."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.assignments import update_item, AssignmentUpdateRequest

        item_id = str(uuid4())
        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            assignedTo="u1",
            _etag="e1",
        )
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)

        try:
            payload = AssignmentUpdateRequest.model_validate({"expectedTools": None, "etag": "e1"})
            with pytest.raises(HTTPException) as exc_info:
                await update_item(
                    dataset="ds",
                    bucket=existing_item.bucket,
                    item_id=item_id,
                    payload=payload,
                    user=UserContext(user_id="u1"),
                    if_match=None,
                )
            assert exc_info.value.status_code == 400
            assert "expectedtools" in exc_info.value.detail.lower()
            assert "null" in exc_info.value.detail.lower()
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_assignments_route_rejects_null_status(self):
        """Assignments PUT route must return HTTP 400 for explicit status: null."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.assignments import update_item, AssignmentUpdateRequest

        item_id = str(uuid4())
        existing_item = AgenticGroundTruthEntry(
            id=item_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            assignedTo="u1",
            _etag="e1",
        )
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.get_gt = AsyncMock(return_value=existing_item)

        try:
            payload = AssignmentUpdateRequest.model_validate({"status": None, "etag": "e1"})
            with pytest.raises(HTTPException) as exc_info:
                await update_item(
                    dataset="ds",
                    bucket=existing_item.bucket,
                    item_id=item_id,
                    payload=payload,
                    user=UserContext(user_id="u1"),
                    if_match=None,
                )
            assert exc_info.value.status_code == 400
            assert "null" in exc_info.value.detail.lower()
        finally:
            container.repo = original_repo

    def test_ground_truth_update_request_schema_non_nullable_status(self):
        """GroundTruthUpdateRequest must not advertise nullable status in OpenAPI schema."""
        from app.api.v1.ground_truths import GroundTruthUpdateRequest

        schema = GroundTruthUpdateRequest.model_json_schema()
        status_prop = schema.get("properties", {}).get("status", {})
        # status must NOT contain anyOf with null type
        any_of = status_prop.get("anyOf", [])
        null_entries = [e for e in any_of if e.get("type") == "null"]
        assert not null_entries, f"status field advertises nullable in schema: {status_prop}"

    def test_assignment_update_request_schema_non_nullable_status(self):
        """AssignmentUpdateRequest must not advertise nullable status in OpenAPI schema."""
        from app.api.v1.assignments import AssignmentUpdateRequest

        schema = AssignmentUpdateRequest.model_json_schema()
        status_prop = schema.get("properties", {}).get("status", {})
        any_of = status_prop.get("anyOf", [])
        null_entries = [e for e in any_of if e.get("type") == "null"]
        assert not null_entries, f"status field advertises nullable in schema: {status_prop}"


class TestBulkImportFailedCount:
    """RR-002/RR-003: Bulk import failed count = unique failed items; indices preserved."""

    @pytest.mark.asyncio
    async def test_failed_count_is_unique_item_count_not_error_count(self):
        """One item with multiple validation errors must count as 1 failed item."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk
        from app.domain.models import BulkImportError

        # Two invalid items; each produces at least one error via approval validation
        item1 = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
        )
        item2 = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
        )
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(return_value=BulkImportResult(imported=0, errors=[]))
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            result = await import_bulk(
                items=[item1, item2],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=True,
            )
            # Both items fail, but failed must equal 2 (unique items), not the raw error count
            assert result.failed == 2
            assert result.imported == 0
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_approval_errors_carry_original_request_index(self):
        """Approval errors must reference the original request index, not the filtered-list index."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk
        from app.domain.models import BulkImportError, HistoryEntry

        # First item is valid (passes tag validation), second is approval-invalid
        item_valid = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Q"),
                HistoryEntry(role="assistant", msg="A"),
            ],
        )
        item_invalid = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
            # no history → approval validation fails
        )
        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(return_value=BulkImportResult(imported=1, errors=[]))
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            # Payload: [valid_at_idx_0, invalid_at_idx_1]
            result = await import_bulk(
                items=[item_valid, item_invalid],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=True,
            )
            assert result.imported == 1
            assert result.failed == 1
            # Error must reference original request index 1 (not 0 from filtered list)
            approval_errors = [e for e in result.errors if e.code == "APPROVAL_VALIDATION_FAILED"]
            assert approval_errors, "Expected APPROVAL_VALIDATION_FAILED errors"
            assert all(e.index == 1 for e in approval_errors), (
                f"Expected all error indices to be 1 (original request position), "
                f"got: {[e.index for e in approval_errors]}"
            )
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_persistence_errors_recover_original_request_index_and_unique_failed_count(self):
        """Persistence errors should map back to request indices and count unique real item ids once."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk

        item0 = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
        )
        item1 = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
        )
        item2 = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
        )

        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(
            return_value=BulkImportResult(
                imported=0,
                errors=[
                    f"exists (article: article-1, id: {item1.id})",
                    f"create_failed (article: article-1, id: {item1.id}): boom",
                    f"create_failed (article: article-2, id: {item2.id}): boom",
                ],
            )
        )
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            result = await import_bulk(
                items=[item0, item1, item2],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=False,
            )

            assert result.imported == 0
            assert result.failed == 2
            assert [error.index for error in result.errors] == [1, 1, 2]
            assert [error.item_id for error in result.errors] == [item1.id, item1.id, item2.id]
            assert [error.code for error in result.errors] == [
                "DUPLICATE_ID",
                "CREATE_FAILED",
                "CREATE_FAILED",
            ]
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_persistence_errors_without_item_id_keep_safe_fallback(self):
        """Persistence errors without an id should still fall back to index=-1 and item_id=None."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk

        item = AgenticGroundTruthEntry(
            id=str(uuid4()), datasetName="ds", bucket=str(uuid4()),
            status=GroundTruthStatus.draft, docType="ground-truth", schemaVersion="agentic-v1",
        )

        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(
            return_value=BulkImportResult(
                imported=0,
                errors=["create_failed (article: article-1): boom"],
            )
        )
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            result = await import_bulk(
                items=[item],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=False,
            )

            assert result.imported == 0
            assert result.failed == 1
            assert len(result.errors) == 1
            assert result.errors[0].index == -1
            assert result.errors[0].item_id is None
            assert result.errors[0].code == "CREATE_FAILED"
        finally:
            container.repo = original_repo


class TestDuplicateIdBulkImport:
    """Step 1.8 — Duplicate IDs in a single bulk-import request must not collapse
    per-request-entry error attribution or undercount failed request entries.

    Covers the IQ-001 finding from the 2026-03-11 plan review.
    """

    @pytest.mark.asyncio
    async def test_duplicate_id_approval_error_uses_correct_request_index(self):
        """[invalid(id=X), valid(id=X)] approve=true → error index=0, failed=1, imported=1."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk
        from app.domain.models import HistoryEntry

        shared_id = str(uuid4())

        # Item at index 0: no history → fails approval validation
        item_invalid = AgenticGroundTruthEntry(
            id=shared_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            # no history → collect_approval_validation_errors will complain
        )
        # Item at index 1: has history → passes approval validation
        item_valid = AgenticGroundTruthEntry(
            id=shared_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Q"),
                HistoryEntry(role="assistant", msg="A"),
            ],
        )

        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(
            return_value=BulkImportResult(imported=1, errors=[])
        )
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            result = await import_bulk(
                items=[item_invalid, item_valid],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=True,
            )
            assert result.imported == 1, f"Expected 1 imported, got {result.imported}"
            assert result.failed == 1, f"Expected 1 failed, got {result.failed}"

            approval_errors = [e for e in result.errors if e.code == "APPROVAL_VALIDATION_FAILED"]
            assert approval_errors, "Expected APPROVAL_VALIDATION_FAILED errors"
            assert all(e.index == 0 for e in approval_errors), (
                f"Error must reference original request index 0 (the invalid entry), "
                f"got indices: {[e.index for e in approval_errors]}"
            )
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_duplicate_id_both_fail_approval_counts_two_failed(self):
        """[invalid(id=X), invalid(id=X)] approve=true → failed=2, errors at index 0 and 1."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk

        shared_id = str(uuid4())

        item0 = AgenticGroundTruthEntry(
            id=shared_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            # no history
        )
        item1 = AgenticGroundTruthEntry(
            id=shared_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            # no history
        )

        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(
            return_value=BulkImportResult(imported=0, errors=[])
        )
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            result = await import_bulk(
                items=[item0, item1],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=True,
            )
            assert result.imported == 0
            assert result.failed == 2, (
                f"Both request entries must be counted as failed, got {result.failed}"
            )
            approval_errors = [e for e in result.errors if e.code == "APPROVAL_VALIDATION_FAILED"]
            error_indices = sorted(e.index for e in approval_errors)
            assert 0 in error_indices, "Expected an error at index 0"
            assert 1 in error_indices, "Expected an error at index 1"
        finally:
            container.repo = original_repo

    @pytest.mark.asyncio
    async def test_duplicate_id_persistence_collision_uses_later_request_index(self):
        """[valid(id=X), valid(id=X)] repo duplicate on second item → error index=1."""
        from app.core.auth import UserContext
        from app.container import container
        from app.api.v1.ground_truths import import_bulk
        from app.domain.models import HistoryEntry

        shared_id = str(uuid4())

        item0 = AgenticGroundTruthEntry(
            id=shared_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Q0"),
                HistoryEntry(role="assistant", msg="A0"),
            ],
        )
        item1 = AgenticGroundTruthEntry(
            id=shared_id,
            datasetName="ds",
            bucket=str(uuid4()),
            status=GroundTruthStatus.draft,
            docType="ground-truth",
            schemaVersion="agentic-v1",
            history=[
                HistoryEntry(role="user", msg="Q1"),
                HistoryEntry(role="assistant", msg="A1"),
            ],
        )

        original_repo = container.repo
        container.repo = AsyncMock()
        container.repo.import_bulk_gt = AsyncMock(
            return_value=BulkImportResult(
                imported=1,
                errors=[f"exists (article: article-1, id: {shared_id})"],
                persistence_errors=[
                    BulkImportPersistenceError(
                        message=f"exists (article: article-1, id: {shared_id})",
                        item_id=shared_id,
                        persistence_index=1,
                    )
                ],
            )
        )
        container.repo.list_gt_paginated = AsyncMock(return_value=([], None))

        try:
            result = await import_bulk(
                items=[item0, item1],
                user=UserContext(user_id="u1"),
                buckets=1,
                approve=False,
            )

            assert result.imported == 1
            assert result.failed == 1
            assert len(result.errors) == 1
            assert result.errors[0].code == "DUPLICATE_ID"
            assert result.errors[0].item_id == shared_id
            assert result.errors[0].index == 1
        finally:
            container.repo = original_repo
