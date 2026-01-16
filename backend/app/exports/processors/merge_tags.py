from __future__ import annotations

from typing import Any

from app.exports.registry import ExportProcessor


class MergeTagsProcessor(ExportProcessor):
    @property
    def name(self) -> str:
        return "merge_tags"

    def process(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for doc in docs:
            manual = doc.get("manualTags") or doc.get("manual_tags") or []
            computed = doc.get("computedTags") or doc.get("computed_tags") or []
            merged = sorted({*map(str, manual), *map(str, computed)})
            updated = dict(doc)
            updated["tags"] = merged
            out.append(updated)
        return out
