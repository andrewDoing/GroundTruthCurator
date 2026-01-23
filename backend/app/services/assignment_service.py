from __future__ import annotations

import re
from app.adapters.repos.base import GroundTruthRepo
from app.domain.models import GroundTruthItem, AssignmentDocument, Reference
from app.plugins import get_default_registry
from app.core.errors import AssignmentConflictError
from app.core.config import get_sampling_allocation
from uuid import UUID
import random
import logging
import randomname  # type: ignore
from datetime import datetime, timezone
from app.domain.enums import GroundTruthStatus


logger = logging.getLogger(__name__)

# Regex pattern for valid user IDs (alphanumeric, @, ., -, _)
# Used to prevent SQL injection in user_id values
USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9@.\-_]+$")


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

    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """Validate user_id format for safe use in database queries.

        Allows alphanumeric characters, @, ., -, and _ (common in email addresses and user IDs).
        Returns False if user_id contains invalid characters.
        """
        if not user_id:
            return False
        return bool(USER_ID_PATTERN.match(user_id))

    @staticmethod
    def compute_quotas(weights: dict[str, float], k: int) -> dict[str, int]:
        """Largest remainder method to convert weights to integer quotas summing to k.

        This is a pure business logic function that distributes a total count (k)
        across multiple categories based on their relative weights.

        Args:
            weights: Dict of category -> weight (e.g., {"dsA": 0.5, "dsB": 0.3, "dsC": 0.2})
            k: Total count to distribute

        Returns:
            Dict of category -> integer quota that sums to k
        """
        if k <= 0 or not weights:
            return {ds: 0 for ds in weights}
        # Normalize weights just in case
        total = sum(w for w in weights.values() if w > 0)
        if total <= 0:
            return {ds: 0 for ds in weights}
        normalized = {ds: (w / total) for ds, w in weights.items() if w > 0}
        # Floor allocations and track remainders
        floors: dict[str, int] = {}
        remainders: list[tuple[str, float]] = []
        allocated = 0
        for ds, w in normalized.items():
            raw = w * k
            fl = int(raw // 1)
            floors[ds] = fl
            allocated += fl
            remainders.append((ds, raw - fl))
        remaining = max(0, k - allocated)
        if remaining > 0:
            # Distribute remaining to largest remainders; stable sort by remainder desc then name
            remainders.sort(key=lambda t: (t[1], t[0]), reverse=True)
            for i in range(remaining):
                ds = remainders[i % len(remainders)][0]
                floors[ds] += 1
        return floors

    def can_assign_item(
        self,
        item: GroundTruthItem,
        user_id: str,
        force: bool = False,
        user_roles: list[str] | None = None,
    ) -> tuple[bool, str | None]:
        """Check if an item can be assigned to a user.

        Business rules for assignment:
        - Item must not be already assigned to another user in draft state (unless force=True)
        - Force assignment requires admin or team-lead role

        Args:
            item: The ground truth item to check
            user_id: The user attempting to claim the item
            force: Whether to allow force takeover
            user_roles: User roles for permission checking

        Returns:
            Tuple of (can_assign, rejection_reason)
        """
        # Check if already assigned to another user in draft state
        if (
            item.assignedTo
            and item.assignedTo != user_id
            and item.status == GroundTruthStatus.draft
        ):
            if not force:
                return False, "already_assigned"

            # Force assignment - validate permission
            roles = user_roles or []
            if not self._has_takeover_permission(roles):
                return False, "permission_denied"

        return True, None

    async def get_assigned(self, user_id: str) -> list[GroundTruthItem]:
        return await self.repo.list_assigned(user_id)

    async def sample_candidates(
        self, user_id: str, limit: int, exclude_ids: list[str] | None = None
    ) -> list[GroundTruthItem]:
        """Sample unassigned items with weighted allocation across datasets.

        This method implements the business logic for sampling candidates:
        1. Include items already assigned to the user first
        2. Apply weighted allocation from GTC_SAMPLING_ALLOCATION config
        3. Round-robin interleave by weight order
        4. Fill any remaining quota from global pool

        Args:
            user_id: The user requesting candidates
            limit: Maximum number of items to return
            exclude_ids: Item IDs to exclude from sampling

        Returns:
            List of candidate items up to limit
        """
        if limit <= 0:
            logger.warning(
                "service.sample_candidates.invalid_limit",
                extra={"limit": limit},
            )
            return []

        # 1) Include already assigned items first
        logger.debug(
            "service.sample_candidates.start",
            extra={
                "limit": limit,
                "exclude_count": len(exclude_ids) if exclude_ids else 0,
            },
        )
        results: list[GroundTruthItem] = await self.repo.list_assigned(user_id)
        seen_ids: set[str] = {it.id for it in results}
        # Add caller-provided excludes
        if exclude_ids:
            seen_ids.update(exclude_ids)
        logger.debug(
            "service.sample_candidates.already_assigned",
            extra={"count": len(results)},
        )
        if len(results) >= limit:
            logger.debug(
                "service.sample_candidates.already_assigned_satisfies",
                extra={"count": len(results), "limit": limit},
            )
            return results[:limit]

        remaining = limit - len(results)

        # 2) Read allocation config
        weights = get_sampling_allocation()
        logger.debug(
            "service.sample_candidates.weights_config",
            extra={"weights": weights, "has_weights": bool(weights)},
        )
        if not weights:
            # No allocation configured -> simple global fill of unassigned/skipped
            logger.debug(
                "service.sample_candidates.no_weights_global_query",
                extra={"remaining": remaining},
            )
            more = await self.repo.query_unassigned_global(
                user_id, remaining, exclude_ids=list(seen_ids)
            )
            logger.debug(
                "service.sample_candidates.global_fill",
                extra={"remaining": remaining, "candidates": len(more)},
            )
            # Shuffle to reduce any cross-partition bias from Cosmos
            random.shuffle(more)
            for it in more:
                if it.id not in seen_ids:
                    results.append(it)
                    seen_ids.add(it.id)
                    if len(results) >= limit:
                        break
            logger.debug(
                "service.sample_candidates.global_fill_complete",
                extra={"final_count": len(results), "limit": limit},
            )
            return results[:limit]

        # 3) Compute quotas using largest remainder method
        quotas = self.compute_quotas(weights, remaining)
        logger.debug(
            "service.sample_candidates.quotas",
            extra={"remaining": remaining, "quotas": quotas},
        )

        # 4) Query each dataset up to its quota (single pass)
        per_dataset_results: dict[str, list[GroundTruthItem]] = {}
        for ds, q in quotas.items():
            if q <= 0:
                logger.debug(
                    "service.sample_candidates.skip_zero_quota",
                    extra={"dataset": ds, "quota": q},
                )
                continue
            items = await self.repo.query_unassigned_by_dataset_prefix(
                ds, user_id, q, exclude_ids=list(seen_ids)
            )
            logger.debug(
                "service.sample_candidates.dataset_candidates",
                extra={"dataset": ds, "quota": q, "candidates": len(items)},
            )
            # Shuffle each bucket to de-bias ordering
            random.shuffle(items)
            per_dataset_results[ds] = items

        # 5) Round-robin interleave by weight order until limit reached or supply exhausted
        order = [ds for ds, _w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)]
        to_take = limit - len(results)
        logger.debug(
            "service.sample_candidates.round_robin_start",
            extra={"to_take": to_take, "dataset_order": order},
        )
        while to_take > 0:
            progressed = False
            for ds in order:
                if to_take <= 0:
                    break
                lst = per_dataset_results.get(ds, [])
                while lst and lst[0].id in seen_ids:
                    lst.pop(0)
                if lst:
                    it = lst.pop(0)
                    results.append(it)
                    seen_ids.add(it.id)
                    to_take -= 1
                    progressed = True
            if not progressed:
                logger.debug(
                    "service.sample_candidates.round_robin_exhausted",
                    extra={"collected": len(results), "limit": limit},
                )
                break

        logger.debug(
            "service.sample_candidates.round_robin_complete",
            extra={"collected": len(results), "limit": limit},
        )
        if len(results) >= limit:
            return results[:limit]

        # 6) Final global fill if still short (single pass)
        remaining_needed = max(0, limit - len(results))
        if remaining_needed > 0:
            logger.debug(
                "service.sample_candidates.global_fill_tail_start",
                extra={"remaining_needed": remaining_needed},
            )
            more = await self.repo.query_unassigned_global(
                user_id, remaining_needed, exclude_ids=list(seen_ids)
            )
            logger.debug(
                "service.sample_candidates.global_fill_tail",
                extra={"remaining": remaining_needed, "candidates": len(more)},
            )
            random.shuffle(more)
            for it in more:
                if it.id not in seen_ids:
                    results.append(it)
                    seen_ids.add(it.id)
                    if len(results) >= limit:
                        break

        final = results[:limit]
        logger.debug(
            "service.sample_candidates.done",
            extra={"limit": limit, "return_count": len(final)},
        )
        return final

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

        # First pass - use sample_candidates which includes weighted allocation logic
        logger.info("self_assign.start", extra={**self._log_context(), "limit": limit})
        initial = await self.sample_candidates(user_id=user_id, limit=limit)
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
            retry = await self.sample_candidates(
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

    def _has_takeover_permission(self, roles: list[str]) -> bool:
        """Check if user has permission to force-assign items.

        Args:
            roles: List of user roles from authentication context

        Returns:
            True if user has admin or team-lead role, False otherwise
        """
        return "admin" in roles or "team-lead" in roles

    async def assign_single_item(
        self,
        dataset: str,
        bucket: UUID,
        item_id: str,
        user_id: str,
        force: bool = False,
        user_roles: list[str] | None = None,
    ) -> GroundTruthItem:
        """Assign a single ground truth item to a user.

        This method:
        - Fetches the ground truth item
        - Validates the item can be assigned (not already assigned to someone else in draft)
        - Assigns it to the user and sets status to draft
        - Creates an assignment document in the assignments container
        - Returns the updated ground truth item

        With force=True:
        - Requires admin or team-lead role (raises PermissionError if not)
        - Allows taking over items assigned to other users
        - Cleans up the previous user's assignment document

        Args:
            dataset: Dataset name
            bucket: Bucket UUID
            item_id: Ground truth item ID
            user_id: User ID to assign to
            force: Whether to force assignment even if already assigned
            user_roles: User roles for permission checking

        Raises:
        - ValueError if item not found or assignment fails
        - PermissionError if force=True without proper role
        - AssignmentConflictError if already assigned and force=False
        """
        # Fetch the item first to verify it exists and check assignability
        item = await self.repo.get_gt(dataset, bucket, item_id)
        if not item:
            logger.error(
                f"assignment_service.assign_single_item.item_not_found - dataset={dataset}, bucket={bucket}, item_id={item_id}"
            )
            raise ValueError("Item not found")

        # Track the previous assignee for cleanup and logging
        previous_assignee = None

        # Validate item can be assigned
        # Don't allow assignment of items already assigned to another user in draft state
        if (
            item.assignedTo
            and item.assignedTo != user_id
            and item.status == GroundTruthStatus.draft
        ):
            if not force:
                # Normal assignment blocked by existing assignment
                logger.warning(
                    f"assignment_service.assign_single_item.already_assigned - dataset={dataset}, bucket={bucket}, item_id={item_id}, "
                    f"current_assigned_to={item.assignedTo}, current_status={item.status.value}"
                )
                raise AssignmentConflictError(
                    "Item is already assigned to another user",
                    assigned_to=item.assignedTo,
                    assigned_at=item.assigned_at,
                )

            # Force assignment - validate user has permission
            roles = user_roles or []
            if not self._has_takeover_permission(roles):
                logger.warning(
                    f"assignment_service.assign_single_item.force_denied - dataset={dataset}, bucket={bucket}, item_id={item_id}, "
                    f"roles={roles}"
                )
                raise PermissionError("Force assignment requires admin or team-lead role")

            # Store previous assignee for cleanup
            previous_assignee = item.assignedTo

            # For force takeover, clear the assignment using efficient patch operation
            # instead of full document replace via upsert_gt
            success = await self.repo.clear_assignment(item_id)
            if not success:
                logger.error(
                    f"assignment_service.assign_single_item.clear_assignment_failed - dataset={dataset}, bucket={bucket}, item_id={item_id}"
                )
                raise ValueError("Failed to clear assignment for force takeover")

            logger.info(
                f"assignment_service.assign_single_item.force_takeover - dataset={dataset}, bucket={bucket}, item_id={item_id}, "
                f"from={previous_assignee}, to={user_id}"
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

        # Clean up previous assignment document if this was a force takeover
        if previous_assignee:
            try:
                deleted = await self.repo.delete_assignment_doc(
                    user_id=previous_assignee,
                    dataset=dataset,
                    bucket=bucket,
                    ground_truth_id=item_id,
                )
                if deleted:
                    logger.info(
                        f"assignment_service.assign_single_item.previous_assignment_cleaned - "
                        f"dataset={dataset}, bucket={bucket}, item_id={item_id}, previous_assignee={previous_assignee}"
                    )
                else:
                    logger.warning(
                        f"assignment_service.assign_single_item.previous_assignment_not_found - "
                        f"dataset={dataset}, bucket={bucket}, item_id={item_id}, previous_assignee={previous_assignee}"
                    )
            except Exception as e:
                # Log error but don't fail the request - the assignment itself succeeded
                logger.error(
                    f"assignment_service.assign_single_item.cleanup_failed - "
                    f"dataset={dataset}, bucket={bucket}, item_id={item_id}, previous_assignee={previous_assignee}, "
                    f"error_type={type(e).__name__}, error={str(e)}"
                )

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
