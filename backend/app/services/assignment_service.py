from __future__ import annotations

from app.adapters.repos.base import GroundTruthRepo
from app.domain.models import GroundTruthItem, AssignmentDocument, Reference
from app.plugins import get_default_registry
from app.core.errors import AssignmentConflictError
from uuid import UUID
import random
import logging
import randomname  # type: ignore
from datetime import datetime, timezone
from app.domain.enums import GroundTruthStatus


logger = logging.getLogger(__name__)


class AssignmentService:
    def __init__(self, repo: GroundTruthRepo):
        self.repo = repo

    def _log_context(
        self, item_id: str | None = None, dataset: str | None = None
    ) -> dict[str, str]:
        """Create consistent logging context with available fields."""
        # NOTE:
        #   We intentionally do NOT include user_id in the returned context.
        #   The logging layer (see app.core.logging._install_log_record_factory) injects
        #   record.user_id automatically after LogRecord creation. Supplying a user_id via
        #   the "extra" parameter would attempt to add the attribute during Logger.makeRecord
        #   and raise KeyError ("Attempt to overwrite 'user_id' in LogRecord").
        #   If a log line needs to surface the actor explicitly for downstream processing,
        #   prefer a different key (e.g. actor, actor_user_id) to avoid clashing with the
        #   reserved field used by the formatter.
        context: dict[str, str] = {}
        if item_id:
            context["item_id"] = item_id
        if dataset:
            context["dataset"] = dataset
        return context

    async def get_assigned(self, user_id: str) -> list[GroundTruthItem]:
        return await self.repo.list_assigned(user_id)

    async def self_assign(self, user_id: str, limit: int) -> list[GroundTruthItem]:
        if limit <= 0:
            logger.debug(
                "self_assign.skip_non_positive_limit",
                extra={**self._log_context(), "limit": limit},
            )
            return []

        assigned_docs: list[AssignmentDocument] = []
        seen_ids: set[str] = set()

        async def _try_assign(candidates: list[GroundTruthItem], remaining: int) -> None:
            nonlocal assigned_docs, seen_ids
            if remaining <= 0:
                return
            # Shuffle to de-bias any ordering from Cosmos queries
            random.shuffle(candidates)
            logger.debug(
                "self_assign.try_assign_batch",
                extra={
                    **self._log_context(),
                    "remaining": remaining,
                    "candidate_count": len(candidates),
                },
            )
            for it in candidates:
                if it.id in seen_ids:
                    logger.debug(
                        "self_assign.skip_seen",
                        extra=self._log_context(it.id, it.datasetName),
                    )
                    continue
                seen_ids.add(it.id)

                # Attempt assignment - the repo layer enforces conditional logic
                # to prevent assigning items that are already assigned to other users
                success = await self.repo.assign_to(it.id, user_id)
                if success:
                    logger.info(
                        "self_assign.assigned",
                        extra=self._log_context(it.id, it.datasetName),
                    )
                    ad = await self.repo.upsert_assignment_doc(user_id, it)
                    assigned_docs.append(ad)
                else:
                    # If assignment already exists, include it
                    existing = await self.repo.get_assignment_by_gt(user_id, it.id)
                    if existing:
                        logger.debug(
                            "self_assign.already_assigned_doc",
                            extra=self._log_context(it.id, it.datasetName),
                        )
                        assigned_docs.append(existing)
                    # If the item is already assigned to this user but no assignment doc exists yet,
                    # create it to keep the assignment view consistent.
                    elif getattr(it, "assignedTo", None) == user_id:
                        logger.warning(
                            "self_assign.backfill_assignment_doc",
                            extra=self._log_context(it.id, it.datasetName),
                        )
                        ad = await self.repo.upsert_assignment_doc(user_id, it)
                        assigned_docs.append(ad)
                if len(assigned_docs) >= limit:
                    logger.debug(
                        "self_assign.reached_limit",
                        extra={**self._log_context(), "limit": limit},
                    )
                    break

        # First pass
        logger.info("self_assign.start", extra={**self._log_context(), "limit": limit})
        initial = await self.repo.sample_unassigned(user_id=user_id, limit=limit)
        logger.debug(
            "self_assign.initial_candidates",
            extra={**self._log_context(), "count": len(initial)},
        )
        await _try_assign(initial, limit)

        # Single retry if we still need more - exclude items we've already tried
        if len(assigned_docs) < limit:
            remaining = limit - len(assigned_docs)
            logger.debug(
                "self_assign.retry_excluding_seen",
                extra={
                    **self._log_context(),
                    "remaining": remaining,
                    "seen_count": len(seen_ids),
                },
            )
            retry = await self.repo.sample_unassigned(
                user_id=user_id, limit=remaining, exclude_ids=list(seen_ids)
            )
            logger.debug(
                "self_assign.retry_candidates",
                extra={
                    **self._log_context(),
                    "remaining": remaining,
                    "count": len(retry),
                },
            )
            await _try_assign(retry, remaining)

        # Return the underlying ground truth items in the order they were added
        ground_truth_items: list[GroundTruthItem] = []
        for ad in assigned_docs[:limit]:
            gt = await self.repo.get_gt(ad.datasetName, ad.bucket, ad.ground_truth_id)
            if gt:
                ground_truth_items.append(gt)
        logger.info(
            "self_assign.done",
            extra={
                **self._log_context(),
                "requested": limit,
                "assignedCount": len(ground_truth_items),
            },
        )
        return ground_truth_items

    # todo: look at this closer, seems insufficient
    async def delete(self, dataset: str, bucket: UUID, item_id: str) -> None:
        # This service method needs dataset and bucket to delete via repo.
        # If only id is available, look up the item first.
        it = await self.repo.get_gt(dataset, bucket, item_id)
        if it is None:
            return
        assert it.bucket is not None
        await self.repo.soft_delete_gt(it.datasetName, it.bucket, item_id)

    async def assign_single_item(
        self, dataset: str, bucket: UUID, item_id: str, user_id: str
    ) -> GroundTruthItem:
        """Assign a single ground truth item to a user.

        This method:
        - Fetches the ground truth item
        - Validates the item can be assigned (not already assigned to someone else in draft)
        - Assigns it to the user and sets status to draft
        - Creates an assignment document in the assignments container
        - Returns the updated ground truth item

        Raises:
        - ValueError if item not found or assignment fails
        """
        # Fetch the item first to verify it exists and check assignability
        item = await self.repo.get_gt(dataset, bucket, item_id)
        if not item:
            logger.error(
                f"assignment_service.assign_single_item.item_not_found - dataset={dataset}, bucket={bucket}, item_id={item_id}"
            )
            raise ValueError("Item not found")

        # Validate item can be assigned
        # Don't allow assignment of items already assigned to another user in draft state
        if (
            item.assignedTo
            and item.assignedTo != user_id
            and item.status == GroundTruthStatus.draft
        ):
            logger.warning(
                f"assignment_service.assign_single_item.already_assigned - dataset={dataset}, bucket={bucket}, item_id={item_id}, "
                f"current_assigned_to={item.assignedTo}, current_status={item.status.value}"
            )
            raise AssignmentConflictError(
                "Item is already assigned to another user",
                assigned_to=item.assignedTo,
                assigned_at=item.assigned_at,
            )

        # Assign to user (will set status to draft regardless of previous state)
        success = await self.repo.assign_to(item_id, user_id)

        if not success:
            # Item may have been deleted or other error occurred
            logger.error(
                f"assignment_service.assign_single_item.assignment_failed - dataset={dataset}, bucket={bucket}, item_id={item_id}"
            )
            raise ValueError("Item could not be assigned")

        # Create assignment document for materialized view
        logger.info(
            f"assignment_service.assign_single_item.creating_assignment_doc - dataset={dataset}, bucket={bucket}, item_id={item_id}"
        )

        await self.repo.upsert_assignment_doc(user_id, item)

        # Fetch and return the updated item
        updated = await self.repo.get_gt(dataset, bucket, item_id)
        if not updated:
            logger.error(
                f"assignment_service.assign_single_item.item_not_found_after_assignment - dataset={dataset}, bucket={bucket}, item_id={item_id}"
            )
            raise ValueError("Item not found after assignment")

        return updated

    async def duplicate_item(self, original: GroundTruthItem, user_id: str) -> GroundTruthItem:
        """Create a copy of a GroundTruth item for rephrasing.

        Rules:
        - Keep datasetName and bucket identical to the original
        - Generate a new id (uuid4 string)
        - Copy synthQuestion, editedQuestion, answer, refs, tags, comment, history and provenance fields
        - Ensure the `rephrase:{original.id}` tag is present exactly once
        - Set status=draft; clear reviewed_at and updatedBy
        - Assign to requesting user (assignedTo, assignedAt)
        - Persist via repo.upsert_gt and create an AssignmentDocument
        """
        # Build new tags with rephrase reference
        rephrase_tag = f"rephrase:{original.id}"
        new_tags = list(original.manual_tags or [])
        if rephrase_tag not in new_tags:
            new_tags.append(rephrase_tag)

        now = datetime.now(timezone.utc)
        new_item = GroundTruthItem(
            id=randomname.get_name(),
            datasetName=original.datasetName,
            bucket=original.bucket,
            status=GroundTruthStatus.draft,
            synthQuestion=original.synth_question,
            edited_question=original.edited_question,
            answer=original.answer,
            refs=[Reference.model_validate(r) for r in (original.refs or [])],
            manualTags=new_tags,
            comment=original.comment,
            history=original.history,
            contextUsedForGeneration=original.contextUsedForGeneration,
            contextSource=original.contextSource,
            modelUsedForGeneration=original.modelUsedForGeneration,
            semanticClusterNumber=original.semanticClusterNumber,
            weight=original.weight,
            samplingBucket=original.samplingBucket,
            questionLength=original.questionLength,
            assignedTo=user_id,
            assigned_at=now,
            updatedBy=None,
            reviewed_at=None,
        )

        # Apply computed tags based on the new item's properties
        registry = get_default_registry()
        computed_tags = registry.compute_all(new_item)
        new_item.computed_tags = computed_tags
        # Strip any computed tag keys from manual tags to prevent duplicates
        # Uses pattern-based matching for dynamic tags (e.g., dataset:*)
        new_item.manual_tags = registry.filter_manual_tags(new_item.manual_tags, computed_tags)

        # Persist new item
        saved = await self.repo.upsert_gt(new_item)
        # Maintain SME assignment materialized view
        await self.repo.upsert_assignment_doc(user_id, saved)
        return saved
