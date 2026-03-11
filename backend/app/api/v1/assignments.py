from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Any, cast, Optional, Set
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
from pydantic.json_schema import SkipJsonSchema
import logging

from app.core.auth import get_current_user, UserContext
from app.core.errors import AssignmentConflictError
from app.domain.models import (
    AgenticGroundTruthEntry,
    AssignmentDocument,
    ContextEntry,
    ExpectedTools,
    FeedbackEntry,
    GroundTruthItem,
    PluginPayload,
    ToolCallRecord,
)
from app.domain.enums import GroundTruthStatus
from app.container import container
from app.api.v1._legacy_compat import apply_legacy_compat_fields, coerce_history_item
from datetime import datetime, timezone
from app.services.tagging_service import apply_computed_tags
from app.services.validation_service import (
    ApprovalValidationError,
    ValidationError,
    validate_item_for_approval,
)


router = APIRouter()
logger = logging.getLogger(__name__)


class SelfServeResponse(BaseModel):
    assigned: list[AgenticGroundTruthEntry]
    requested: int
    assignedCount: int


class HistoryEntryPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    role: str
    msg: str | None = None


class AssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    comment: Optional[str] = None
    status: GroundTruthStatus | str | SkipJsonSchema[None] = None
    manual_tags: Optional[list[str]] = Field(default=None, alias="manualTags")
    approve: Optional[bool] = None
    etag: Optional[str] = Field(default=None, alias="etag")
    history: Optional[list[HistoryEntryPatch]] = None
    context_entries: Optional[list[ContextEntry]] = Field(default=None, alias="contextEntries")
    tool_calls: Optional[list[ToolCallRecord]] = Field(default=None, alias="toolCalls")
    expected_tools: ExpectedTools | SkipJsonSchema[None] = Field(default=None, alias="expectedTools")
    feedback: Optional[list[FeedbackEntry]] = None
    metadata: Optional[dict[str, Any]] = None
    plugins: Optional[dict[str, PluginPayload]] = None
    trace_ids: Optional[dict[str, str]] = Field(default=None, alias="traceIds")
    trace_payload: Optional[dict[str, Any]] = Field(default=None, alias="tracePayload")
    scenario_id: Optional[str] = Field(default=None, alias="scenarioId")


@router.post("/self-serve")
async def self_serve_assignments(
    body: dict[str, Any], user: UserContext = Depends(get_current_user)
) -> SelfServeResponse:
    # Expect body: { limit: int }
    limit_val = cast(int | str | None, body.get("limit", 0))
    try:
        limit = int(limit_val) if limit_val is not None else 0
    except (TypeError, ValueError):
        limit = 0
    logger.info("api.self_serve.start", extra={"requested": limit})
    assigned = await container.assignment_service.self_assign(user.user_id, limit)
    resp = SelfServeResponse(
        assigned=assigned,
        requested=limit,
        assignedCount=len(assigned),
    )
    logger.info(
        "api.self_serve.done",
        extra={"requested": limit, "assignedCount": resp.assignedCount},
    )
    return resp


@router.get("/my")
async def list_my_assignments(
    user: UserContext = Depends(get_current_user),
) -> list[AgenticGroundTruthEntry]:
    # Fetch assignment documents (materialized view), then fetch underlying GroundTruth items.
    assignments: list[AssignmentDocument] = await container.repo.list_assignments_by_user(
        user.user_id
    )
    results: list[AgenticGroundTruthEntry] = []
    for ad in assignments:
        gt = await container.repo.get_gt(ad.datasetName, ad.bucket, ad.ground_truth_id)
        if not gt:
            continue
        # Only return items still assigned to the user and in draft state
        if gt.assignedTo != user.user_id:
            continue
        if gt.status != GroundTruthStatus.draft:
            continue
        results.append(gt)
    return results


@router.put("/{dataset}/{bucket}/{item_id}")
async def update_item(
    dataset: str,
    bucket: UUID,
    item_id: str,
    payload: AssignmentUpdateRequest,
    user: UserContext = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> AgenticGroundTruthEntry:
    # Fold soft delete into PUT via status=deleted
    it = cast(GroundTruthItem | None, await container.repo.get_gt(dataset, bucket, item_id))
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    # Only allow updates to fields permitted for SME
    # Enforce ownership: only assigned user may mutate via SME route
    # If assignedTo is set and doesn't match, forbid
    if it.assignedTo and it.assignedTo != user.user_id:
        raise HTTPException(status_code=403, detail="ASSIGNMENT_OWNERSHIP")

    # Capture original assignedTo before clearing (needed for assignment doc deletion)
    original_assigned_to = it.assignedTo

    provided_fields: Set[str] = set(payload.model_fields_set)
    payload_extras = payload.model_extra or {}

    if "comment" in provided_fields:
        it.comment = payload.comment or ""
    if "history" in provided_fields:
        if payload.history is None:
            it.history = None
            it.totalReferences = 0
        else:
            try:
                it.history = [coerce_history_item(entry) for entry in payload.history]
                it.totalReferences = 0
            except (TypeError, ValueError, ValidationError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid history format: {str(e)}")
    if "context_entries" in provided_fields:
        it.context_entries = payload.context_entries or []
    if "tool_calls" in provided_fields:
        it.tool_calls = payload.tool_calls or []
    if "expected_tools" in provided_fields:
        if payload.expected_tools is None:
            raise HTTPException(
                status_code=400,
                detail="expectedTools cannot be null; omit the field to leave it unchanged",
            )
        it.expected_tools = payload.expected_tools
    if "feedback" in provided_fields:
        it.feedback = payload.feedback or []
    if "metadata" in provided_fields:
        it.metadata = payload.metadata or {}
    if "plugins" in provided_fields:
        it.plugins = payload.plugins or {}
    if "trace_ids" in provided_fields:
        it.trace_ids = payload.trace_ids
    if "trace_payload" in provided_fields:
        it.trace_payload = payload.trace_payload or {}
    if "scenario_id" in provided_fields:
        it.scenario_id = payload.scenario_id or ""

    try:
        apply_legacy_compat_fields(it, payload_extras)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)

    now = datetime.now(timezone.utc)

    # Track whether we need to delete the assignment document
    should_delete_assignment = False

    # Approve convenience flag
    if bool(payload.approve):
        it.status = GroundTruthStatus.approved
        it.reviewed_at = now
        it.updatedBy = user.user_id
        # Clear assignment fields on completion
        it.assignedTo = None
        it.assigned_at = None
        should_delete_assignment = True

    # Status update handling (skip/delete/approved explicitly)
    if "status" in provided_fields:
        if payload.status is None:
            raise HTTPException(
                status_code=400,
                detail="status cannot be null; omit the field to leave it unchanged",
            )
        try:
            val = payload.status
            if isinstance(val, GroundTruthStatus):
                it.status = val
            else:
                it.status = GroundTruthStatus(str(val))
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status value: {payload.status}. Must be one of: draft, approved, skipped, deleted"
            )
        if it.status in {GroundTruthStatus.approved, GroundTruthStatus.deleted}:
            # Clear assignment when moving out of draft (keep for skipped so another SME can pick it up)
            it.assignedTo = None
            it.assigned_at = None
            should_delete_assignment = True
        if it.status == GroundTruthStatus.approved:
            it.reviewed_at = now
            it.updatedBy = user.user_id
    # Tags (validated by model validators)
    if "manual_tags" in provided_fields:
        try:
            it.manual_tags = payload.manual_tags or []
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    # ETag handling: require an ETag for all SME updates (approve/skip/delete)
    provided_etag = payload.etag
    if not if_match and not provided_etag:
        raise HTTPException(status_code=412, detail="ETag required")
    if if_match:
        it.etag = if_match
    elif provided_etag:
        it.etag = provided_etag

    # Apply computed tags before saving
    try:
        if it.status == GroundTruthStatus.approved:
            validate_item_for_approval(it)
        apply_computed_tags(it)
    except ApprovalValidationError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_APPROVAL", "errors": e.errors})
    except ValueError as e:
        # Convert ValueError from validation to HTTP 400
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await container.repo.upsert_gt(it)
    except ValueError as e:
        if str(e) == "etag_mismatch":
            raise HTTPException(status_code=412, detail="ETag mismatch")
        raise

    # Delete assignment document after successful GT update
    if should_delete_assignment and original_assigned_to:
        try:
            deleted = await container.repo.delete_assignment_doc(
                user_id=original_assigned_to,
                dataset=dataset,
                bucket=bucket,
                ground_truth_id=item_id,
            )
            if deleted:
                logger.debug(
                    "api.update_item.assignment_deleted",
                    extra={"item_id": item_id, "assigned_user": original_assigned_to},
                )
            else:
                logger.info(
                    "api.update_item.assignment_not_found",
                    extra={"item_id": item_id, "assigned_user": original_assigned_to},
                )
        except Exception as e:
            # Log as error for alerting, but don't fail the request - GT update already succeeded
            logger.error(
                "api.update_item.assignment_delete_failed",
                extra={
                    "item_id": item_id,
                    "assigned_user": original_assigned_to,
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
            )

    res_item = await container.repo.get_gt(dataset, bucket, item_id)
    if not res_item:
        raise HTTPException(status_code=404, detail="Item not found")
    # Include updated etag explicitly in response body for consistency
    return res_item


class AssignItemRequest(BaseModel):
    """Request body for assignment endpoint."""

    force: bool = Field(
        default=False,
        description="Force assignment even if item is assigned to another user (requires admin or team-lead role)",
    )


@router.post("/{dataset}/{bucket}/{item_id}/assign", status_code=200, response_model=None)
async def assign_item(
    dataset: str,
    bucket: UUID,
    item_id: str,
    body: AssignItemRequest | None = None,
    user: UserContext = Depends(get_current_user),
) -> AgenticGroundTruthEntry | JSONResponse:
    """Assign a specific ground truth item to the current user.

    This endpoint:
    - Assigns the item to the current user
    - Sets the item status to draft (even if previously approved/deleted/skipped)
    - Creates an assignment document in the assignments container
    - Returns the updated ground truth item

    With force=true:
    - Requires admin or team-lead role
    - Allows taking over items assigned to other users
    - Cleans up the previous user's assignment document
    """
    force = body.force if body else False

    try:
        assigned = await container.assignment_service.assign_single_item(
            dataset, bucket, item_id, user.user_id, force=force, user_roles=user.roles
        )

        return assigned
    except PermissionError as e:
        # Force assignment attempted without proper role
        logger.warning(
            f"api.assign_item.permission_denied - dataset={dataset}, bucket={bucket}, item_id={item_id}, "
            f"error='{str(e)}'"
        )
        raise HTTPException(status_code=403, detail=str(e))
    except AssignmentConflictError as e:
        # Return structured 409 response with assignment details
        payload = {
            "detail": str(e),
            "assignedTo": e.assigned_to,
        }
        if e.assigned_at:
            payload["assignedAt"] = e.assigned_at.isoformat()

        logger.warning(
            f"api.assign_item.conflict - dataset={dataset}, bucket={bucket}, item_id={item_id}, "
            f"assigned_to={e.assigned_to}"
        )
        return JSONResponse(status_code=409, content=payload)
    except ValueError as e:
        error_msg = str(e)
        # Log original error for debugging
        # Note: user_id is automatically injected by logging middleware, don't pass in extra
        logger.error(
            f"api.assign_item.error - dataset={dataset}, bucket={bucket}, item_id={item_id}, error='{error_msg}'"
        )
        # Provide sanitized, user-friendly error messages to clients
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=404,
                detail="The requested item could not be found or has been deleted.",
            )
        elif "already assigned" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail="This item is already assigned to another user.",
            )
        # Generic error for other validation failures
        raise HTTPException(
            status_code=400,
            detail="Unable to assign this item. Please check the item status and try again.",
        )


@router.post("/{dataset}/{bucket}/{item_id}/duplicate", status_code=201)
async def duplicate_assignment_item(
    dataset: str,
    bucket: UUID,
    item_id: str,
    user: UserContext = Depends(get_current_user),
) -> AgenticGroundTruthEntry:
    """Duplicate an existing item as a draft rephrase, assign to caller, and return the new item."""
    original = await container.repo.get_gt(dataset, bucket, item_id)
    if not original:
        raise HTTPException(status_code=404, detail="Item not found")
    # Only allow duplication by the assigned user if the item is currently assigned
    if original.assignedTo and original.assignedTo != user.user_id:
        raise HTTPException(status_code=403, detail="ASSIGNMENT_OWNERSHIP")
    # Authorization: allow duplication if user can see/assign original; keeping simple for now
    try:
        created = await container.assignment_service.duplicate_item(original, user.user_id)
    except ValueError as e:
        # Validation errors on tags, etc.
        raise HTTPException(status_code=400, detail=str(e))
    return created
