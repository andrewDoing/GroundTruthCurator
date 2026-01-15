"""Validation service for ground truth items during bulk import."""

from __future__ import annotations

import asyncio

from app.container import container
from app.domain.models import GroundTruthItem
import logging
from app.services.tagging_service import validate_tags_with_cache

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails for a ground truth item."""

    def __init__(self, item_id: str, field: str, message: str):
        self.item_id = item_id
        self.field = field
        self.message = message
        super().__init__(f"Item '{item_id}': {field} - {message}")


async def validate_ground_truth_item(
    item: GroundTruthItem, valid_tags_cache: set[str] | None = None
) -> list[str]:
    """Validate a ground truth item for bulk import.

    Returns a list of validation error messages. Empty list means valid.
    Used instead of pydantic as tag validation require an async call for the cache

    Validates:
    - Manual tag values against the tag registry
    - this can be extended to validate other field if needed

    Args:
        item: The ground truth item to validate
        valid_tags_cache: Optional pre-fetched set of valid tags to avoid repeated lookups
    """
    errors: list[str] = []
    item_id = item.id or "(no ID)"

    # Validate manual tags values (computed tags are system-generated and don't need validation)
    if item.manual_tags:
        # Fetch tags if not cached
        if valid_tags_cache is None:
            valid_tags_cache = set(await container.tag_registry_service.list_tags())
        try:
            # Use cached tags
            validate_tags_with_cache(item.manual_tags, valid_tags_cache)
            logger.debug(
                f"Tag validation passed | item_id: {item_id} | manualTags: {item.manual_tags}"
            )

        except ValueError as e:
            errors.append(f"Item '{item_id}': Error {str(e)}")
            logger.warning(
                f"Tag validation failed during bulk import | ID: {item_id} | Dataset: {item.datasetName} | ManualTags: {item.manual_tags} | Error: {str(e)}"
            )

    return errors


async def validate_bulk_items(items: list[GroundTruthItem]) -> dict[str, list[str]]:
    """Validate a list of ground truth items for bulk import.

    Returns a dict mapping item ID to list of validation errors.
    Items with no errors are not included in the result.
    """
    validation_results: dict[str, list[str]] = {}

    # Fetch tag registry once for all items with manual tags
    valid_tags_cache: set[str] | None = None
    has_items_with_tags = any(item.manual_tags for item in items)
    if has_items_with_tags:
        valid_tags_cache = set(await container.tag_registry_service.list_tags())

    # Validate all items concurrently
    validation_tasks = [validate_ground_truth_item(item, valid_tags_cache) for item in items]

    results = await asyncio.gather(*validation_tasks, return_exceptions=False)

    # Collect errors
    for item, errors in zip(items, results):
        if errors:
            validation_results[item.id] = errors

    return validation_results
