from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Any, cast, Optional, Set
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
import logging

from app.core.auth import get_current_user, UserContext
from app.domain.models import GroundTruthItem, Reference, AssignmentDocument, HistoryItem
from app.domain.enums import GroundTruthStatus
from app.container import container
from datetime import datetime, timezone
from app.services.tagging_service import apply_computed_tags


router = APIRouter()
logger = logging.getLogger(__name__)


class SelfServeResponse(BaseModel):
    assigned: list[GroundTruthItem]
    requested: int
    assignedCount: int


class AssignmentUpdateRequest(BaseModel):
    """Payload for SME update (save draft / approve / skip / delete).

    Using a Pydantic model allows camelCase -> snake_case alias handling. All fields optional; we
    only mutate those explicitly provided (tracked via model_fields_set).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    edited_question: Optional[str] = Field(default=None, alias="editedQuestion")
    answer: Optional[str] = None
    comment: Optional[str] = None
    status: Optional[GroundTruthStatus | str] = None
    refs: Optional[list[Reference]] = None
    manual_tags: Optional[list[str]] = Field(default=None, alias="manualTags")
    approve: Optional[bool] = None
    etag: Optional[str] = Field(default=None, alias="etag")
    history: Optional[list[dict[str, Any]]] = None


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
) -> list[GroundTruthItem]:
    # Fetch assignment documents (materialized view), then fetch underlying GroundTruth items.
    assignments: list[AssignmentDocument] = await container.repo.list_assignments_by_user(
        user.user_id
    )
    results: list[GroundTruthItem] = []
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
) -> GroundTruthItem:
    # Fold soft delete into PUT via status=deleted
    it = await container.repo.get_gt(dataset, bucket, item_id)
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

    # Apply updates conditionally
    if "edited_question" in provided_fields:
        it.edited_question = payload.edited_question  # type: ignore[assignment]
    if "answer" in provided_fields:
        it.answer = payload.answer  # type: ignore[assignment]
    if "comment" in provided_fields:
        it.comment = payload.comment  # type: ignore[assignment]

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
        try:
            val = payload.status
            if isinstance(val, GroundTruthStatus) or val is None:
                it.status = val  # type: ignore[assignment]
            else:
                it.status = GroundTruthStatus(str(val))
        except Exception:
            it.status = cast(Any, payload.status)  # type: ignore[assignment]
        if it.status in {GroundTruthStatus.approved, GroundTruthStatus.deleted}:
            # Clear assignment when moving out of draft (keep for skipped so another SME can pick it up)
            it.assignedTo = None
            it.assigned_at = None
            should_delete_assignment = True
        if it.status == GroundTruthStatus.approved:
            it.reviewed_at = now
            it.updatedBy = user.user_id
    if "refs" in provided_fields and payload.refs is not None:
        it.refs = payload.refs  # already validated
    # Tags (validated by model validators)
    if "manual_tags" in provided_fields:
        try:
            it.manual_tags = payload.manual_tags or []
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    # History (with refs in agent messages)
    if "history" in provided_fields and payload.history is not None:
        try:
            # Convert dict representations to HistoryItem models
            history_items = []
            for h in payload.history:
                # Parse refs if present in the history item
                refs_data = h.get("refs")
                refs_list = None
                if refs_data is not None:
                    refs_list = [
                        r if isinstance(r, Reference) else Reference(**r) for r in refs_data
                    ]
                # Parse expected_behavior if present in the history item
                expected_behavior_data = h.get("expected_behavior") or h.get("expectedBehavior")
                history_items.append(
                    HistoryItem(
                        role=h["role"],
                        msg=h.get("msg")
                        or h.get("content", ""),  # Support both 'msg' and 'content'
                        refs=refs_list,
                        expected_behavior=expected_behavior_data
                        if isinstance(expected_behavior_data, list)
                        else None,
                    )
                )
            it.history = history_items
        except (KeyError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid history format: {str(e)}")
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
        apply_computed_tags(it)
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


@router.post("/{dataset}/{bucket}/{item_id}/assign", status_code=200)
async def assign_item(
    dataset: str,
    bucket: UUID,
    item_id: str,
    user: UserContext = Depends(get_current_user),
) -> GroundTruthItem:
    """Assign a specific ground truth item to the current user.

    This endpoint:
    - Assigns the item to the current user
    - Sets the item status to draft (even if previously approved/deleted/skipped)
    - Creates an assignment document in the assignments container
    - Returns the updated ground truth item
    """
    try:
        assigned = await container.assignment_service.assign_single_item(
            dataset, bucket, item_id, user.user_id
        )

        return assigned
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
) -> GroundTruthItem:
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
