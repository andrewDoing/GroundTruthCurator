from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable, Tuple

from app.domain.tags import RULES, TAG_SCHEMA, TagGroupSpec
from app.plugins import get_default_registry, TagPluginRegistry

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem
import logging

logger = logging.getLogger(__name__)

_SEP_PATTERN = re.compile(r"\s*:\s*")


def normalize_tag(tag: str) -> str:
    s = (tag or "").strip().lower()
    s = _SEP_PATTERN.sub(":", s)
    # collapse internal whitespace around group and value
    if ":" not in s:
        raise ValueError(f"Invalid tag format (expected group:value): '{tag}'")
    group, value = s.split(":", 1)
    group = " ".join(group.split())
    value = " ".join(value.split())
    if not group or not value:
        raise ValueError(f"Invalid tag format (empty group or value): '{tag}'")
    return f"{group}:{value}"


def parse_tag(tag: str) -> Tuple[str, str]:
    s = normalize_tag(tag)
    g, v = s.split(":", 1)
    return g, v


def allowed_tag_groups() -> dict[str, set[str]]:
    return {k: set(spec.values) for k, spec in TAG_SCHEMA.items()}


def is_exclusive_group(group: str) -> bool:
    spec: TagGroupSpec | None = TAG_SCHEMA.get(group)
    return bool(spec and spec.exclusive)


def _validate_known(tags: set[str]) -> list[str]:
    # Relaxed validation: allow unknown groups and values.
    # We still rely on normalize_tag to enforce format and on RULES for
    # exclusivity/dependency checks for known groups.
    errors: list[str] = []
    for t in tags:
        # Ensure basic format only; normalize_tag already validates, but keep
        # a defensive check here to accumulate errors across all tags.
        if ":" not in t:
            errors.append(f"Invalid tag format (expected group:value): '{t}'")
    return errors


def validate_tags(tags: Iterable[str]) -> list[str]:
    # normalize, dedupe, sort
    normalized = [normalize_tag(t) for t in tags]
    unique: set[str] = set(normalized)

    errors = _validate_known(unique)
    # rule checks
    for rule in RULES:
        errors.extend(rule.check(unique, TAG_SCHEMA))

    if errors:
        raise ValueError("; ".join(sorted(set(errors))))

    return sorted(unique)


def upsert_tag(tags: Iterable[str], group: str, value: str) -> list[str]:
    group = group.strip().lower()
    value = value.strip().lower()
    tag = normalize_tag(f"{group}:{value}")

    current = [normalize_tag(t) for t in tags]
    if is_exclusive_group(group):
        # remove any existing tag from this group
        current = [t for t in current if not t.startswith(f"{group}:")]
        current.append(tag)
    else:
        # append only if not present
        if tag not in current:
            current.append(tag)

    return validate_tags(current)


def remove_group(tags: Iterable[str], group: str) -> list[str]:
    group = group.strip().lower()
    remaining = [normalize_tag(t) for t in tags if not normalize_tag(t).startswith(f"{group}:")]
    # remaining must still be valid
    return validate_tags(remaining)


def validate_tags_with_cache(tags: Iterable[str], valid_tags: set[str] | None) -> list[str]:
    """Validate tags against a pre-fetched set (internal use)."""

    if not valid_tags:
        raise ValueError("Valid tags set must be provided for cached validation.")

    normalized = [normalize_tag(t) for t in tags]
    unique: set[str] = set(normalized)

    errors = []
    for tag in unique:
        if tag not in valid_tags:
            errors.append(f"Unknown tag '{tag}'.")

    # Apply existing rules
    for rule in RULES:
        errors.extend(rule.check(unique, TAG_SCHEMA))

    if errors:
        raise ValueError("; ".join(sorted(set(errors))))

    return sorted(unique)


def apply_computed_tags(item: GroundTruthItem, registry: TagPluginRegistry | None = None) -> None:
    """Compute and set the computed tags for an item.

    This mutates the item in place, setting:
    - computed_tags: system-generated tags based on item properties
    - manual_tags: cleaned to remove any tags that are computed tag keys

    Args:
        item: The GroundTruthItem to compute tags for.
        registry: Optional pre-fetched registry. If None, fetches default.
    """
    if registry is None:
        registry = get_default_registry()

    # Compute all applicable tags
    computed_tags = registry.compute_all(item)

    # Check for and log any stripped tags (security audit trail)
    # Uses pattern-based matching for dynamic tags (e.g., dataset:*)
    original_manual_tags = set(item.manual_tags or [])
    cleaned_manual_tags = registry.filter_manual_tags(item.manual_tags, computed_tags)
    stripped_tags = original_manual_tags - set(cleaned_manual_tags)
    if stripped_tags:
        logger.warning(
            f"Stripped computed tag keys from manual tags | "
            f"item_id={item.id} | stripped_tags={stripped_tags}"
        )

    # Update the item with cleaned manual tags and computed tags
    item.manual_tags = cleaned_manual_tags
    item.computed_tags = computed_tags

    # Validate exclusive group rules before returning
    all_tags = set(item.manual_tags) | set(item.computed_tags)
    for rule in RULES:
        errors = rule.check(all_tags, TAG_SCHEMA)
        if errors:
            raise ValueError("; ".join(errors))
