from __future__ import annotations

import json
from typing import Any

from app.exports.registry import ExportFormatter


class JsonItemsFormatter(ExportFormatter):
    @property
    def format_name(self) -> str:
        return "json_items"

    def format(self, docs: list[dict[str, Any]]) -> str:
        return json.dumps(docs, ensure_ascii=False, separators=(",", ":"))
