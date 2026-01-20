from __future__ import annotations

import json
from pathlib import Path

from app.domain.manual_tags_provider import (
    JsonFileManualTagProvider,
    ManualTagGroup,
    expand_manual_tags,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_provider_normalizes_groups_and_tags(tmp_path: Path) -> None:
    config = {
        "manualTagGroups": [
            {
                "group": " Priority ",
                "mutuallyExclusive": True,
                "tags": [" High ", "HIGH", "  ", 42],
            }
        ]
    }
    path = _write_json(tmp_path / "tags.json", config)

    groups = JsonFileManualTagProvider(path).get_default_tag_groups()

    assert groups == [ManualTagGroup(group="priority", tags=["high"], mutually_exclusive=True)]


def test_provider_ignores_invalid_entries(tmp_path: Path) -> None:
    config = {
        "manualTagGroups": [
            "not-a-dict",
            {"group": " ", "tags": ["ignored"]},
            {"group": 123, "tags": ["ignored"]},
            {"group": "valid", "tags": "not-a-list"},
            {"group": "valid", "tags": []},
        ]
    }
    path = _write_json(tmp_path / "tags.json", config)

    groups = JsonFileManualTagProvider(path).get_default_tag_groups()

    assert groups == []


def test_expand_manual_tags_dedupes_and_sorts() -> None:
    groups = [
        ManualTagGroup(group="priority", tags=["high", "low"], mutually_exclusive=True),
        ManualTagGroup(group="priority", tags=["low"], mutually_exclusive=True),
        ManualTagGroup(group="review", tags=["needs-review"], mutually_exclusive=False),
    ]

    assert expand_manual_tags(groups) == [
        "priority:high",
        "priority:low",
        "review:needs-review",
    ]
