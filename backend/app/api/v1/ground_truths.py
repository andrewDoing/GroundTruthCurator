from __future__ import annotations

import re
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Header, Query
from typing import Any, cast
from datetime import datetime, timezone
from uuid import UUID

import randomname  # type: ignore

from pydantic import BaseModel, Field, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user, UserContext
from app.core.config import settings
from app.domain.models import (
    AgenticGroundTruthEntry,
    ContextEntry,
    ExpectedTools,
    FeedbackEntry,
    GroundTruthListResponse,
    HistoryItem,
    PluginPayload,
    ToolCallRecord,
    BulkImportError,
    BulkImportPersistenceError,
    ValidationSummary,
)
from app.domain.enums import GroundTruthStatus, SortField, SortOrder
from app.plugins import get_default_registry
from app.container import container
from app.exports.models import SnapshotExportRequest
from app.api.v1.update_models import HistoryEntryPatch
from app.services.ground_truth_update_service import (
    ETagMismatchError,
    ETagRequiredError,
    apply_shared_update,
    persist_shared_update,
    read_legacy_compat_update,
)
from app.services.validation_service import (
    ApprovalValidationError,
    ValidationError,
    validate_bulk_items,
    validate_item_for_approval,
)
from app.services.pii_service import PIIWarning, scan_bulk_items_for_pii
from app.services.duplicate_detection_service import (
    DuplicateWarning,
    detect_duplicates_for_bulk_items,
)
import logging
from app.services.tagging_service import apply_computed_tags

logger = logging.getLogger("gtc.ground_truths")

router = APIRouter()
_PERSISTENCE_ERROR_ITEM_ID_RE = re.compile(r"\bid:\s*([^)]+?)\)")


def _extract_persistence_error_item_id(error_msg: str) -> str | None:
    match = _PERSISTENCE_ERROR_ITEM_ID_RE.search(error_msg)
    if match is None:
        return None
    item_id = match.group(1).strip()
    return item_id or None


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
    duplicate_warnings: list[DuplicateWarning] = Field(
        default_factory=list,
        alias="duplicateWarnings",
        description=(
            "Warnings about draft items that appear to be duplicates of approved items. "
            "These are informational only and do not block import. Review for potential duplicates."
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


class GroundTruthUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    status: GroundTruthStatus | str | SkipJsonSchema[None] = None
    comment: str | None = None
    history: list[HistoryEntryPatch] | None = None
    context_entries: list[ContextEntry] | None = Field(default=None, alias="contextEntries")
    tool_calls: list[ToolCallRecord] | None = Field(default=None, alias="toolCalls")
    expected_tools: ExpectedTools | SkipJsonSchema[None] = Field(
        default=None, alias="expectedTools"
    )
    feedback: list[FeedbackEntry] | None = None
    metadata: dict[str, Any] | None = None
    plugins: dict[str, PluginPayload] | None = None
    manual_tags: list[str] | None = Field(default=None, alias="manualTags")
    trace_ids: dict[str, str] | None = Field(default=None, alias="traceIds")
    trace_payload: dict[str, Any] | None = Field(default=None, alias="tracePayload")
    scenario_id: str | None = Field(default=None, alias="scenarioId")
    etag: str | None = Field(default=None, alias="etag")


def _coerce_history_for_internal_use(item: AgenticGroundTruthEntry) -> None:
    if not item.history:
        return
    item.history = [
        entry
        if isinstance(entry, HistoryItem)
        else HistoryItem.model_validate(entry.model_dump(by_alias=True))
        for entry in item.history
    ]


@router.post("", response_model=ImportBulkResponse)
async def import_bulk(
    items: list[AgenticGroundTruthEntry],
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
    gt_items: list[AgenticGroundTruthEntry] = []
    unknown_persistence_failures: int = 0

    # Ensure IDs in input order, preserving provided IDs when present
    for it in items:
        item_id = it.id.strip() if it.id else ""
        if not item_id:
            # Generate a two-word, hyphenated string id, e.g., "sleek-voxel"
            item_id = randomname.get_name()
        it.id = item_id
        uuids.append(item_id)

    # Track failed request-entry positions for accurate per-entry failed counting.
    # Using a set[int] of original request indices avoids undercounting when
    # duplicate IDs appear in the same request.
    failed_request_indices: set[int] = set()
    # Parallel list of original request indices for items that reach gt_items;
    # maintains a 1-to-1 correspondence with gt_items throughout the pipeline.
    gt_item_orig_indices: list[int] = []

    # Validate all items before processing
    # validate_bulk_items is keyed by request-position index (not item.id) so
    # duplicate IDs in one request do not collapse per-entry error attribution.
    validation_errors = await validate_bulk_items(items)

    # If there are validation errors, filter out invalid items and collect errors
    if validation_errors:
        for req_idx, item in enumerate(items):
            if req_idx in validation_errors:
                # Collect all validation errors for this request entry
                errors.extend(validation_errors[req_idx])
                failed_request_indices.add(req_idx)
            else:
                # Only include valid items
                gt_items.append(item)
                gt_item_orig_indices.append(req_idx)
    else:
        # All items are valid
        gt_items = list(items)
        gt_item_orig_indices = list(range(len(items)))

    # Optionally set approval metadata
    if approve:
        now = datetime.now(timezone.utc)
        updater = getattr(user, "user_id", None)
        for it in gt_items:
            it.status = GroundTruthStatus.approved
            it.reviewed_at = now
            it.updatedBy = updater

        # Enforce generic approval validation for approved items.
        # validate_bulk_items returns results keyed by position within gt_items here
        # (not by item.id) so duplicate IDs in the filtered list remain distinct.
        approval_validation_errors = await validate_bulk_items(gt_items)

        # Check generic approval invariants plus plugin-pack hooks for each item
        approval_ready_items: list[AgenticGroundTruthEntry] = []
        approval_ready_orig_indices: list[int] = []
        for gt_pos, item in enumerate(gt_items):
            orig_idx = gt_item_orig_indices[gt_pos]
            item_errors = []

            # Add tag validation errors if present; fix index to original request position
            if gt_pos in approval_validation_errors:
                for err in approval_validation_errors[gt_pos]:
                    err.index = orig_idx
                item_errors.extend(approval_validation_errors[gt_pos])

            # Run the shared approval path (generic core + plugin-pack hooks).
            # validate_item_for_approval combines collect_approval_validation_errors
            # with container.plugin_pack_registry.collect_approval_errors so that
            # plugin-owned constraints (e.g. RagCompatPack) are enforced here too.
            try:
                validate_item_for_approval(item)
            except ApprovalValidationError as exc:
                for err_msg in exc.errors:
                    item_errors.append(
                        BulkImportError(
                            index=orig_idx,
                            item_id=item.id,
                            field="approval",
                            code="APPROVAL_VALIDATION_FAILED",
                            message=err_msg,
                        )
                    )

            if item_errors:
                errors.extend(item_errors)
                failed_request_indices.add(orig_idx)
            else:
                approval_ready_items.append(item)
                approval_ready_orig_indices.append(orig_idx)

        gt_items = approval_ready_items
        gt_item_orig_indices = approval_ready_orig_indices

    # Persist only validated items
    if gt_items:
        # Apply computed tags to each item before persisting
        # Fetch registry once for performance (avoids O(n) singleton lookups)
        registry = get_default_registry()
        for it in gt_items:
            _coerce_history_for_internal_use(it)
            apply_computed_tags(it, registry)

        result = await container.repo.import_bulk_gt(gt_items, buckets=buckets)

        # Convert repository errors (plain strings) to structured errors.
        # Cosmos error messages include the item id when available, so recover it
        # to preserve original request indices and per-entry failed-item counting.
        # Build a per-id ordered list of original indices from the items submitted
        # to persistence so duplicate IDs get distinct request positions.
        id_to_orig_indices: dict[str, list[int]] = {}
        for orig_idx, it in zip(gt_item_orig_indices, gt_items):
            id_to_orig_indices.setdefault(it.id, []).append(orig_idx)
        id_consumed: dict[str, int] = {}  # tracks how many errors per id we've consumed
        unknown_persistence_failures = 0
        persistence_errors = result.persistence_errors or [
            BulkImportPersistenceError(
                message=error_msg,
                item_id=_extract_persistence_error_item_id(error_msg),
            )
            for error_msg in result.errors
        ]
        for persistence_error in persistence_errors:
            error_msg = persistence_error.message
            item_id = persistence_error.item_id or _extract_persistence_error_item_id(error_msg)
            error_code = "CREATE_FAILED" if "create_failed" in error_msg.lower() else "DUPLICATE_ID"
            if (
                persistence_error.persistence_index is not None
                and 0 <= persistence_error.persistence_index < len(gt_item_orig_indices)
            ):
                error_index = gt_item_orig_indices[persistence_error.persistence_index]
                failed_request_indices.add(error_index)
            elif item_id and item_id in id_to_orig_indices:
                consumed = id_consumed.get(item_id, 0)
                indices = id_to_orig_indices[item_id]
                # Use the consumed-th matching index; clamp to last for extra errors.
                error_index = indices[consumed] if consumed < len(indices) else indices[-1]
                id_consumed[item_id] = consumed + 1
                failed_request_indices.add(error_index)
            elif item_id:
                # item_id was in the error but not in our submission set; use -1
                error_index = -1
                failed_request_indices.add(-1)
            else:
                error_index = -1
                unknown_persistence_failures += 1
            errors.append(
                BulkImportError(
                    index=error_index,
                    item_id=item_id,
                    field=None,
                    code=error_code,
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

    # Detect duplicates (informational warnings only, does not block import)
    duplicate_warnings: list[DuplicateWarning] = []
    if settings.DUPLICATE_DETECTION_ENABLED:
        try:
            # Fetch all approved items from the same dataset(s) to check against
            datasets = {item.datasetName for item in items}
            existing_approved_items: list[AgenticGroundTruthEntry] = []
            for dataset in datasets:
                # Fetch approved items from this dataset
                items_list, _ = await container.repo.list_gt_paginated(
                    dataset=dataset,
                    status=GroundTruthStatus.approved,
                    page=1,
                    limit=1000,  # Reasonable limit for duplicate detection
                    sort_by=SortField.updated_at,
                    sort_order=SortOrder.desc,
                )
                existing_approved_items.extend(items_list)

            duplicate_warnings = detect_duplicates_for_bulk_items(items, existing_approved_items)
            if duplicate_warnings:
                logger.info(
                    f"api.import_bulk.duplicates_detected - "
                    f"items={len(items)}, warnings={len(duplicate_warnings)}"
                )
        except (NotImplementedError, Exception) as e:
            # If repo doesn't support list_gt_paginated (e.g., in unit tests), skip duplicate detection
            logger.debug(
                f"api.import_bulk.duplicate_detection_skipped - error_type={type(e).__name__}, error='{str(e)}'"
            )

    # Build validation summary
    total_items = len(items)
    # Count unique failed request entries (not raw error count — one item may produce
    # multiple errors, and duplicate IDs in one request each count independently).
    # unknown_persistence_failures counts errors with no recoverable item id.
    failed_count = len(failed_request_indices) + unknown_persistence_failures
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
        piiWarnings=pii_warnings,
        duplicateWarnings=duplicate_warnings,
        validationSummary=validation_summary,
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
    exclude_tags: str | None = Query(
        default=None,
        alias="excludeTags",
        description="Comma-separated list of tags to exclude (items with ANY excluded tag will be filtered out)",
    ),
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

    exclude_tag_list = None
    if exclude_tags is not None:
        raw_exclude_tags = [tag.strip() for tag in exclude_tags.split(",")]
        cleaned_exclude = [tag for tag in raw_exclude_tags if tag]

        # Validate exclude tag count
        if len(cleaned_exclude) > MAX_TAGS_PER_QUERY:
            raise HTTPException(
                status_code=400,
                detail=f"Too many exclude tags specified. Maximum allowed is {MAX_TAGS_PER_QUERY}.",
            )

        # Validate individual exclude tag lengths
        for tag in cleaned_exclude:
            if len(tag) > MAX_TAG_LENGTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"Exclude tag '{tag[:50]}...' exceeds maximum length of {MAX_TAG_LENGTH} characters.",
                )

        exclude_tag_list = cleaned_exclude if cleaned_exclude else None

    items, pagination = await container.repo.list_gt_paginated(
        status=status_enum,
        dataset=dataset,
        tags=tag_list,
        exclude_tags=exclude_tag_list,
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
) -> list[AgenticGroundTruthEntry]:
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
) -> AgenticGroundTruthEntry:
    item = await container.repo.get_gt(datasetName, bucket, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{datasetName}/{bucket}/{item_id}")
async def update_ground_truth(
    datasetName: str,
    bucket: UUID,
    item_id: str,
    payload: GroundTruthUpdateRequest,
    user: UserContext = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> AgenticGroundTruthEntry:
    it = await container.repo.get_gt(datasetName, bucket, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    provided_fields = set(payload.model_fields_set)
    payload_extras = payload.model_extra or {}

    # Tags handling: Only accept 'manualTags' in the generic contract
    if "computedTags" in payload_extras:
        raise HTTPException(
            status_code=400,
            detail="computedTags cannot be set directly; they are system-generated",
        )
    if "tags" in payload_extras:
        raise HTTPException(
            status_code=400,
            detail="'tags' field is deprecated; use 'manualTags' instead",
        )
    try:
        apply_shared_update(
            it,
            provided_fields=provided_fields,
            comment=payload.comment,
            history_entries=payload.history,
            context_entries=payload.context_entries,
            tool_calls=payload.tool_calls,
            expected_tools=payload.expected_tools,
            feedback=payload.feedback,
            metadata=payload.metadata,
            plugins=payload.plugins,
            trace_ids=payload.trace_ids,
            trace_payload=payload.trace_payload,
            scenario_id=payload.scenario_id,
            manual_tags=payload.manual_tags,
            status=payload.status,
            actor_user_id=user.user_id,
            legacy_update=read_legacy_compat_update(payload_extras),
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    try:
        await persist_shared_update(
            container.repo,
            it,
            if_match=if_match,
            payload_etag=payload.etag,
        )
    except ApprovalValidationError as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_APPROVAL", "errors": e.errors}
        )
    except ETagRequiredError:
        raise HTTPException(status_code=412, detail="ETag required")
    except ETagMismatchError:
        raise HTTPException(status_code=412, detail="ETag mismatch")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
