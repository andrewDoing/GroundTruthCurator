from __future__ import annotations

from typing import Any

from pydantic import field_validator

from app.services.tagging_service import validate_tags


def coerce_tags(value: Any) -> list[str]:
    """Coerce various input types to a list of tag strings.

    Accepts:
    - None -> []
    - str (comma-separated) -> list of trimmed strings
    - list/tuple/set -> list of string-converted values
    """
    if value is None:
        return []
    if isinstance(value, str):
        # split on commas for convenience
        return [p for p in (v.strip() for v in value.split(",")) if p]
    if isinstance(value, (list, tuple, set)):
        collected: list[str] = []
        for v in value:
            if v is None:
                continue
            collected.append(str(v))
        return collected
    # unknown type
    raise TypeError("tags must be a list of strings or a comma-separated string")


class GroundTruthItemTagValidators:
    """Pydantic validators for tag fields on GroundTruthItem.

    Validates manualTags field (user-provided tags).
    computedTags are system-generated and don't need user validation.
    """

    @field_validator("manual_tags", mode="before")
    @classmethod
    def _coerce_manual_tags(_cls, v: Any) -> list[str]:
        return coerce_tags(v)

    @field_validator("manual_tags", mode="after")
    @classmethod
    def _validate_manual_tags(_cls, v: list[str]) -> list[str]:
        try:
            return validate_tags(v)
        except ValueError as e:
            raise ValueError(str(e))

    @field_validator("computed_tags", mode="before")
    @classmethod
    def _coerce_computed_tags(_cls, v: Any) -> list[str]:
        # Computed tags are system-generated, just coerce to list
        return coerce_tags(v)
