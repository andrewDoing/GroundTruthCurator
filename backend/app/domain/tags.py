from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set, Tuple

from app.core.config import settings
from app.domain.manual_tags_provider import JsonFileManualTagProvider, ManualTagGroup


@dataclass(frozen=True)
class TagGroupSpec:
    name: str
    values: Set[str]
    exclusive: bool
    depends_on: Optional[list[Tuple[str, str]]] = None  # list of (group, value) dependencies


def _load_default_tag_groups() -> list[ManualTagGroup]:
    config_path = settings.MANUAL_TAGS_CONFIG_PATH
    if not config_path:
        return []
    path = Path(config_path)
    provider = JsonFileManualTagProvider(path)
    return provider.get_default_tag_groups()


def _build_schema(groups: list[ManualTagGroup]) -> dict[str, TagGroupSpec]:
    schema: dict[str, TagGroupSpec] = {}
    for group in groups:
        existing = schema.get(group.group)
        if existing:
            merged_values = set(existing.values) | set(group.tags)
            schema[group.group] = TagGroupSpec(
                name=group.group,
                values=merged_values,
                exclusive=existing.exclusive or group.mutually_exclusive,
                depends_on=existing.depends_on,
            )
            continue

        schema[group.group] = TagGroupSpec(
            name=group.group,
            values=set(group.tags),
            exclusive=group.mutually_exclusive,
        )

    return schema


# Global tag schema definition
# Schema is fetched dynamically by frontend via /v1/tags/schema endpoint
# Frontend validation will fail if schema is unavailable (fail-fast approach)
TAG_SCHEMA: dict[str, TagGroupSpec] = _build_schema(_load_default_tag_groups())


class RuleError(Exception):
    pass


class Rule:
    def check(self, tags: Set[str], schema: dict[str, TagGroupSpec]) -> list[str]:  # noqa: D401
        """Return list of error messages for violations."""
        raise NotImplementedError


class ExclusiveGroupRule(Rule):
    def check(self, tags: Set[str], schema: dict[str, TagGroupSpec]) -> list[str]:
        errors: list[str] = []
        by_group: dict[str, list[str]] = {}
        for t in tags:
            try:
                g, v = t.split(":", 1)
            except ValueError:
                continue
            by_group.setdefault(g, []).append(v)

        for g, spec in schema.items():
            if not spec.exclusive:
                continue
            values = by_group.get(g, [])
            if len(values) > 1:
                errors.append(
                    f"Group '{g}' is exclusive; only one value allowed, got: {sorted(values)}"
                )
        return errors


class DependencyRule(Rule):
    def check(self, tags: Set[str], schema: dict[str, TagGroupSpec]) -> list[str]:
        errors: list[str] = []
        present: Set[Tuple[str, str]] = set()
        for t in tags:
            try:
                g, v = t.split(":", 1)
            except ValueError:
                continue
            present.add((g, v))

        for g, spec in schema.items():
            if not spec.depends_on:
                continue
            # if any tag from this group present, ensure dependencies present
            any_present = any(gg == g for (gg, _vv) in present)
            if any_present:
                for dep in spec.depends_on:
                    if dep not in present:
                        errors.append(f"Tag group '{g}' requires '{dep[0]}:{dep[1]}' to be present")
        return errors


RULES: list[Rule] = [ExclusiveGroupRule(), DependencyRule()]
