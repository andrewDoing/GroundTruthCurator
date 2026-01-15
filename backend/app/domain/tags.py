from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set, Tuple, Type

from app.domain import enums as E


@dataclass(frozen=True)
class TagGroupSpec:
    name: str
    values: Set[str]
    exclusive: bool
    depends_on: Optional[list[Tuple[str, str]]] = None  # list of (group, value) dependencies


def _values(enum_cls: Type[E.Enum]) -> Set[str]:
    return {m.value for m in enum_cls}


# Global tag schema definition
# Schema is fetched dynamically by frontend via /v1/tags/schema endpoint
# Frontend validation will fail if schema is unavailable (fail-fast approach)
TAG_SCHEMA: dict[str, TagGroupSpec] = {
    "source": TagGroupSpec("source", _values(E.SourceTag), exclusive=True),
    "answerability": TagGroupSpec("answerability", _values(E.AnswerabilityTag), exclusive=True),
    "topic": TagGroupSpec("topic", _values(E.TopicTag), exclusive=False),
    "intent": TagGroupSpec("intent", _values(E.IntentTypeTag), exclusive=False),
    "expertise": TagGroupSpec("expertise", _values(E.QueryExpertiseVariationTag), exclusive=True),
    "difficulty": TagGroupSpec("difficulty", _values(E.DifficultyTag), exclusive=True),
}


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
