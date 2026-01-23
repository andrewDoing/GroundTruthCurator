from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ManualTagValue:
    value: str
    description: str | None = None


@dataclass(frozen=True)
class ManualTagGroup:
    group: str
    tags: List[str]  # Tag values only (for backward compatibility)
    mutually_exclusive: bool
    description: str | None = None
    tag_definitions: List[ManualTagValue] | None = None  # Full tag definitions with descriptions


class ManualTagProvider(ABC):
    @abstractmethod
    def get_default_tag_groups(self) -> List[ManualTagGroup]:
        """Returns default/suggested manual tags for UX defaults, organized by group."""
        raise NotImplementedError


class JsonFileManualTagProvider(ManualTagProvider):
    def __init__(self, json_path: Path) -> None:
        self._json_path = json_path

    def get_default_tag_groups(self) -> List[ManualTagGroup]:
        if not self._json_path.exists():
            logger.warning("Manual tag defaults file not found: %s", self._json_path)
            return []

        try:
            data = json.loads(self._json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive for malformed config
            logger.error("Failed to parse manual tag defaults file %s: %s", self._json_path, exc)
            return []

        groups = data.get("manualTagGroups", [])
        if not isinstance(groups, list):
            return []

        result: List[ManualTagGroup] = []
        for group_data in groups:
            if not isinstance(group_data, dict):
                continue

            group = group_data.get("group")
            tags_raw = group_data.get("tags", [])
            mutually_exclusive = bool(group_data.get("mutuallyExclusive", False))
            group_description = group_data.get("description")

            if not isinstance(group, str):
                continue
            group = group.strip().lower()
            if not group:
                continue

            # Handle both formats: list of strings (old) or list of objects (new)
            normalized_tags: List[str] = []
            tag_definitions: List[ManualTagValue] = []

            if not isinstance(tags_raw, list):
                tags_raw = []

            for tag_item in tags_raw:
                # Old format: string
                if isinstance(tag_item, str):
                    tag_val = tag_item.strip().lower()
                    if tag_val:
                        normalized_tags.append(tag_val)
                        tag_definitions.append(ManualTagValue(value=tag_val, description=None))
                # New format: object with value and description
                elif isinstance(tag_item, dict):
                    tag_val = tag_item.get("value", "").strip().lower()
                    tag_desc = tag_item.get("description")
                    if tag_val:
                        normalized_tags.append(tag_val)
                        tag_definitions.append(ManualTagValue(value=tag_val, description=tag_desc))

            if not normalized_tags:
                continue

            # Deduplicate while preserving descriptions
            seen_values: set[str] = set()
            deduped_tags: List[str] = []
            deduped_definitions: List[ManualTagValue] = []

            for tag_val, tag_def in zip(normalized_tags, tag_definitions):
                if tag_val not in seen_values:
                    seen_values.add(tag_val)
                    deduped_tags.append(tag_val)
                    deduped_definitions.append(tag_def)

            deduped_tags.sort()
            deduped_definitions.sort(key=lambda x: x.value)

            result.append(
                ManualTagGroup(
                    group=group,
                    tags=deduped_tags,
                    mutually_exclusive=mutually_exclusive,
                    description=group_description,
                    tag_definitions=deduped_definitions,
                )
            )

        return result


def expand_manual_tags(groups: Iterable[ManualTagGroup]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for tag in group.tags:
            value = f"{group.group}:{tag}"
            if value in seen:
                continue
            seen.add(value)
            tags.append(value)
    return sorted(tags)
