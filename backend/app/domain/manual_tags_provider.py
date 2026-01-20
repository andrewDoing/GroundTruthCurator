from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ManualTagGroup:
    group: str
    tags: List[str]
    mutually_exclusive: bool


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
            tags = group_data.get("tags", [])
            mutually_exclusive = bool(group_data.get("mutuallyExclusive", False))

            if not isinstance(group, str):
                continue
            group = group.strip().lower()
            if not group:
                continue

            if not isinstance(tags, list):
                tags = []
            normalized_tags = [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]
            if not normalized_tags:
                continue

            deduped = sorted(set(normalized_tags))
            result.append(
                ManualTagGroup(
                    group=group,
                    tags=deduped,
                    mutually_exclusive=mutually_exclusive,
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
