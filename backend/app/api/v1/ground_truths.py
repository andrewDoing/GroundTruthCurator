from __future__ import annotations

import time

from fastapi import APIRouter, Body, Depends, HTTPException, Header, Query
from typing import Any, cast
from datetime import datetime, timezone
from uuid import UUID

import randomname  # type: ignore

from pydantic import BaseModel, Field, ConfigDict
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user, UserContext
from app.core.config import settings
from app.domain.models import (
    GroundTruthItem,
    Reference,
    GroundTruthListResponse,
    HistoryItem,
    BulkImportError,
    ValidationSummary,
)
from app.domain.enums import GroundTruthStatus, SortField, SortOrder
from app.plugins import get_default_registry
from app.container import container
from app.exports.models import SnapshotExportRequest
from app.services.validation_service import validate_bulk_items
from app.services.pii_service import PIIWarning, scan_bulk_items_for_pii
import logging
from app.services.tagging_service import apply_computed_tags

logger = logging.getLogger("gtc.ground_truths")

router = APIRouter()


class ImportBulkResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    imported: int = Field(description="Number of items successfully imported.")
    failed: int = Field(default=0, description="Number of items that failed to import.")
    errors: list[BulkImportError] = Field(
        default_factory=list,
        description="Structured error objects for items that failed to import.",
    )
    uuids: list[str] = Field(
        default_factory=list,
        description=(
            "The item IDs in the same order as the request payload. Clients may send either 'id' or 'uuid' in each item; "
            "when missing or blank, the server generates a two-word, hyphenated string ID (e.g., 'sleek-voxel') via randomname."
        ),
    )
    pii_warnings: list[PIIWarning] = Field(
        default_factory=list,
        alias="piiWarnings",
        description=(
            "Warnings about potential personally identifiable information (PII) detected in imported items. "
            "These are informational only and do not block import. Review flagged content for remediation."
        ),
    )
    validation_summary: ValidationSummary = Field(
        alias="validationSummary",
        description="Summary statistics for the bulk import operation.",
    )


class RecomputeTagsResponse(BaseModel):
    """Response for bulk computed tag recomputation."""

    total: int = Field(description="Total items matching the filter criteria.")
    processed: int = Field(description="Number of items successfully processed.")
    updated: int = Field(description="Number of items with changed computed tags.")
    skipped: int = Field(description="Number of items with unchanged computed tags.")
    errors: list[str] = Field(default_factory=list, description="Error messages for failed items.")
    dry_run: bool = Field(description="Whether this was a dry run (no changes persisted).")
    duration_ms: int = Field(description="Operation duration in milliseconds.")


@router.post("", response_model=ImportBulkResponse)
async def import_bulk(
    items: list[GroundTruthItem],
    user: UserContext = Depends(get_current_user),
    buckets: int | None = Query(default=None, ge=1, le=50),
    approve: bool = Query(
        default=False,
        description="If true, mark all imported items as approved and set review metadata.",
    ),
) -> ImportBulkResponse:
    """Bulk import ground truth items.

    Behavior:
    - ID field: Each item may include 'id' (alias 'uuid'); missing/blank values are generated server-side using
      randomname to produce a two-word, hyphenated string (e.g., 'sleek-voxel').
    - Order preservation: Response `uuids` mirrors request order for easy correlation.
    - Duplicate handling: Existing items are not overwritten; per-item errors are returned in `errors`.
    - Optional approval: `approve=true` marks all items approved and sets review metadata.
    """
    errors: list[BulkImportError] = []
    uuids: list[str] = []
    gt_items: list[GroundTruthItem] = []

    # Ensure IDs in input order, preserving provided IDs when present
    for it in items:
        item_id = it.id.strip() if it.id else ""
        if not item_id:
            # Generate a two-word, hyphenated string id, e.g., "sleek-voxel"
            item_id = randomname.get_name()
        it.id = item_id
        uuids.append(item_id)

    # Validate all items before processing
    validation_errors = await validate_bulk_items(items)

    # If there are validation errors, filter out invalid items and collect errors
    if validation_errors:
        for item in items:
            if item.id in validation_errors:
                # Collect all validation errors for this item
                errors.extend(validation_errors[item.id])
            else:
                # Only include valid items
                gt_items.append(item)
    else:
        # All items are valid
        gt_items = items

    # Optionally set approval metadata
    if approve:
        now = datetime.now(timezone.utc)
        updater = getattr(user, "user_id", None)
        for it in gt_items:
            it.status = GroundTruthStatus.approved
            it.reviewed_at = now
            it.updatedBy = updater

    # Persist only validated items
    if gt_items:
        # Apply computed tags to each item before persisting
        # Fetch registry once for performance (avoids O(n) singleton lookups)
        registry = get_default_registry()
        for it in gt_items:
            apply_computed_tags(it, registry)

        result = await container.repo.import_bulk_gt(gt_items, buckets=buckets)

        # Convert repository errors (plain strings) to structured errors
        # Repository doesn't provide index, so we can't map back to original position
        # These are persistence errors after validation passed
        for error_msg in result.errors:
            errors.append(
                BulkImportError(
                    index=-1,  # Index unknown for persistence errors
                    item_id=None,  # Parse from error message if needed
                    field=None,
                    code="CREATE_FAILED"
                    if "create_failed" in error_msg.lower()
                    else "DUPLICATE_ID",
                    message=error_msg,
                )
            )
        imported_count = result.imported
    else:
        imported_count = 0

    # Scan for PII (informational warnings only, does not block import)
    pii_warnings: list[PIIWarning] = []
    if settings.PII_DETECTION_ENABLED:
        pii_warnings = scan_bulk_items_for_pii(items)
        if pii_warnings:
            logger.info(
                f"api.import_bulk.pii_detected - items={len(items)}, warnings={len(pii_warnings)}"
            )

    # Build validation summary
    total_items = len(items)
    failed_count = len(errors)
    validation_summary = ValidationSummary(
        total=total_items,
        succeeded=imported_count,
        failed=failed_count,
    )

    return ImportBulkResponse(  # type: ignore[call-arg]
        imported=imported_count,
        failed=failed_count,
        errors=errors,
        uuids=uuids,
        pii_warnings=pii_warnings,
        validation_summary=validation_summary,
    )


@router.post("/snapshot")
async def snapshot(
    body: SnapshotExportRequest = Body(default_factory=SnapshotExportRequest),
    user: UserContext = Depends(get_current_user),
) -> Any:
    try:
        response = await container.snapshot_service.export_snapshot(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if isinstance(response, dict):
        return {"status": "ok", **response}
    return response


@router.get("/snapshot")
async def download_snapshot(user: UserContext = Depends(get_current_user)) -> JSONResponse:
    """Return approved items as a downloadable JSON attachment.

    Response headers include Content-Disposition so browsers download the file.
    """
    payload = await container.snapshot_service.build_snapshot_payload()
    ts = cast(str, payload.get("snapshotAt", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    filename = f"ground-truth-snapshot-{ts}.json"
    return JSONResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=GroundTruthListResponse)
async def list_all_ground_truths(
    status: str | None = Query(default=None),
    dataset: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    item_id: str | None = Query(
        default=None,
        alias="itemId",
        description="Search for items by ID (case-sensitive partial match)",
    ),
    ref_url: str | None = Query(
        default=None,
        alias="refUrl",
        description="Search for items by reference URL (case-sensitive partial match)",
    ),
    keyword: str | None = Query(
        default=None,
        description="Search for items by keyword (case-insensitive text search across questions, answers, and history)",
    ),
    sort_by: SortField = Query(default=SortField.reviewed_at.value, alias="sortBy"),
    sort_order: SortOrder = Query(default=SortOrder.desc.value, alias="sortOrder"),
    page: int = Query(default=1),
    limit: int = Query(default=25),
    user: UserContext = Depends(get_current_user),
) -> GroundTruthListResponse:
    try:
        status_enum = GroundTruthStatus(status) if status is not None else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status value")

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be at least 1")

    # ID search validation
    item_id_search = None
    if item_id is not None:
        item_id = item_id.strip()
        if not item_id:
            # Empty after trim - treat as if parameter not provided
            item_id = None
        elif len(item_id) > 200:
            raise HTTPException(status_code=400, detail="itemId must be 200 characters or less")
        else:
            item_id_search = item_id

    # Reference URL search validation
    ref_url_search = None
    if ref_url is not None:
        ref_url = ref_url.strip()
        if not ref_url:
            # Empty after trim - treat as if parameter not provided
            ref_url = None
        elif len(ref_url) > 500:
            raise HTTPException(status_code=400, detail="refUrl must be 500 characters or less")
        else:
            ref_url_search = ref_url

    # Keyword search validation
    keyword_search = None
    if keyword is not None:
        keyword = keyword.strip()
        if not keyword:
            # Empty after trim - treat as if parameter not provided
            keyword = None
        elif len(keyword) > 200:
            raise HTTPException(status_code=400, detail="keyword must be 200 characters or less")
        else:
            keyword_search = keyword

    # Tag validation constants
    MAX_TAGS_PER_QUERY = 10
    MAX_TAG_LENGTH = 100

    tag_list = None
    if tags is not None:
        raw_tags = [tag.strip() for tag in tags.split(",")]
        cleaned = [tag for tag in raw_tags if tag]

        # Validate tag count
        if len(cleaned) > MAX_TAGS_PER_QUERY:
            raise HTTPException(
                status_code=400,
                detail=f"Too many tags specified. Maximum allowed is {MAX_TAGS_PER_QUERY}.",
            )

        # Validate individual tag lengths
        for tag in cleaned:
            if len(tag) > MAX_TAG_LENGTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tag '{tag[:50]}...' exceeds maximum length of {MAX_TAG_LENGTH} characters.",
                )

        tag_list = cleaned if cleaned else None

    items, pagination = await container.repo.list_gt_paginated(
        status=status_enum,
        dataset=dataset,
        tags=tag_list,
        item_id=item_id_search,
        ref_url=ref_url_search,
        keyword=keyword_search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )
    return GroundTruthListResponse(items=items, pagination=pagination)


@router.get("/{datasetName}")
async def list_ground_truths(
    datasetName: str,
    status: GroundTruthStatus | None = None,
    user: UserContext = Depends(get_current_user),
) -> list[GroundTruthItem]:
    try:
        items = await container.repo.list_gt_by_dataset(datasetName, status)
    except ValueError as e:
        if str(e) == "not_found":
            raise HTTPException(status_code=404, detail="Dataset not found")
        raise
    return items


@router.get("/{datasetName}/{bucket}/{item_id}")
async def get_ground_truth(
    datasetName: str,
    bucket: UUID,
    item_id: str,
    user: UserContext = Depends(get_current_user),
) -> GroundTruthItem:
    item = await container.repo.get_gt(datasetName, bucket, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{datasetName}/{bucket}/{item_id}")
async def update_ground_truth(
    datasetName: str,
    bucket: UUID,
    item_id: str,
    payload: dict[str, Any],
    user: UserContext = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> GroundTruthItem:
    it = await container.repo.get_gt(datasetName, bucket, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    # Apply updates including references
    for k in ["edited_question", "answer", "status"]:
        if k in payload:
            if k == "status":
                # Coerce string status to GroundTruthStatus enum to keep the
                # model consistent and avoid Pydantic serializer warnings.
                try:
                    val = payload[k]
                    if isinstance(val, GroundTruthStatus):
                        status_val = val
                    else:
                        status_val = GroundTruthStatus(val)
                    setattr(it, "status", status_val)
                except Exception:
                    # Let Pydantic / API validation handle invalid values
                    setattr(it, "status", payload[k])
            else:
                setattr(it, k, payload[k])
    if "comment" in payload:
        it.comment = payload["comment"]
    if "refs" in payload and isinstance(payload["refs"], list):
        # Validate minimal Reference structure; rely on Pydantic validation when saving
        refs_payload = cast(list[Reference | dict[str, Any]], payload["refs"])
        it.refs = [r if isinstance(r, Reference) else Reference(**r) for r in refs_payload]

    # Tags handling: Only accept 'manualTags' in payload
    # computedTags are system-generated and cannot be set by clients
    # Explicitly reject 'computedTags' and legacy 'tags' fields
    if "computedTags" in payload:
        raise HTTPException(
            status_code=400,
            detail="computedTags cannot be set directly; they are system-generated",
        )
    if "tags" in payload:
        raise HTTPException(
            status_code=400,
            detail="'tags' field is deprecated; use 'manualTags' instead",
        )
    if "manualTags" in payload:
        try:
            it.manual_tags = payload["manualTags"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # History (with refs in agent messages)
    if "history" in payload:
        if payload["history"] is None:
            it.history = None
        elif isinstance(payload["history"], list):
            try:
                # Convert dict representations to HistoryItem models
                history_items = []
                for h in payload["history"]:
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
    # Concurrency: use If-Match header or etag field in body
    provided_etag: str | None = cast(str | None, payload.get("etag"))
    if not if_match and not provided_etag:
        # Require ETag to perform update
        raise HTTPException(status_code=412, detail="ETag required")
    if if_match:
        it.etag = if_match
    elif provided_etag:
        it.etag = provided_etag
    try:
        # Apply computed tags before saving
        apply_computed_tags(it)
        await container.repo.upsert_gt(it)
    except ValueError as e:
        if str(e) == "etag_mismatch":
            raise HTTPException(status_code=412, detail="ETag mismatch")
        raise
    # Fetch and return the updated item so the response includes the fresh ETag
    # and any server-populated fields (mirrors assignments API behavior).
    latest = await container.repo.get_gt(datasetName, bucket, item_id)
    if not latest:
        # Should not happen, but guard to avoid returning stale data
        return it
    return latest


@router.delete("/{datasetName}/{bucket}/{item_id}")
async def delete_item(
    datasetName: str, bucket: UUID, item_id: str, user: UserContext = Depends(get_current_user)
) -> dict[str, str]:
    """
    Soft-delete a ground truth item.
    """
    await container.repo.soft_delete_gt(datasetName, bucket, item_id)
    return {"status": "deleted"}


@router.post("/recompute-tags", response_model=RecomputeTagsResponse)
async def recompute_computed_tags(
    user: UserContext = Depends(get_current_user),
    dataset: str | None = Query(
        default=None,
        description="Filter to items in a specific dataset. If not provided, processes all datasets.",
    ),
    status: GroundTruthStatus | None = Query(
        default=None,
        description="Filter to items with a specific status (draft, approved, etc.).",
    ),
    dry_run: bool = Query(
        default=True,
        description="If true, preview changes without persisting. Defaults to true for safety.",
    ),
) -> RecomputeTagsResponse:
    """Recompute computed tags for all matching ground truth items.

    This endpoint recalculates the `computedTags` field for all items matching
    the optional filter criteria. Use this when:
    - A new computed tag plugin has been added
    - An existing plugin's logic has been modified
    - Data needs to be reprocessed after a bug fix

    The operation is idempotent - running it multiple times with the same
    data produces the same result.

    **Important**: By default, `dry_run=true` for safety. Set `dry_run=false`
    to actually persist changes.
    """
    start_time = time.perf_counter()

    # Get computed tag registry
    registry = get_default_registry()

    errors: list[str] = []
    processed = 0
    updated = 0
    skipped = 0

    # Fetch items based on filters
    try:
        if dataset:
            items = await container.repo.list_gt_by_dataset(dataset, status)
        else:
            items = await container.repo.list_all_gt(status)
    except ValueError as e:
        if str(e) == "not_found":
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' not found")
        raise

    total = len(items)

    for item in items:
        try:
            # Capture original computed tags for comparison
            original_computed_tags = set(item.computed_tags or [])

            # Apply computed tags (mutates item in place)
            apply_computed_tags(item, registry)

            # Check if computed tags changed
            new_computed_tags = set(item.computed_tags or [])

            if original_computed_tags != new_computed_tags:
                if not dry_run:
                    # Bypass ETag for bulk recomputation
                    item.etag = None
                    await container.repo.upsert_gt(item)
                updated += 1
            else:
                skipped += 1

            processed += 1

        except Exception as e:
            errors.append(f"{item.id}: {str(e)}")
            logger.error(f"api.recompute_tags.error - item_id={item.id}, error='{str(e)}'")

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    logger.info(
        f"api.recompute_tags.complete - "
        f"total={total}, processed={processed}, updated={updated}, "
        f"skipped={skipped}, errors={len(errors)}, dry_run={dry_run}, "
        f"duration_ms={duration_ms}"
    )

    return RecomputeTagsResponse(
        total=total,
        processed=processed,
        updated=updated,
        skipped=skipped,
        errors=errors,
        dry_run=dry_run,
        duration_ms=duration_ms,
    )
