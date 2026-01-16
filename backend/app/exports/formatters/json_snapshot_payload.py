from __future__ import annotations

import json
from typing import Any

from app.exports.registry import ExportFormatter


def _collect_dataset_names(docs: list[dict[str, Any]]) -> list[str]:
    dataset_names = {str(doc.get("datasetName", "")).strip() for doc in docs}
    return sorted(name for name in dataset_names if name)


class JsonSnapshotPayloadFormatter(ExportFormatter):
    def __init__(
        self,
        snapshot_at: str,
        filters: dict[str, Any] | None = None,
    ) -> None:
        self._snapshot_at = snapshot_at
        self._filters = dict(filters) if filters else {}

    @property
    def format_name(self) -> str:
        return "json_snapshot_payload"

    def format(self, docs: list[dict[str, Any]]) -> str:
        dataset_names = _collect_dataset_names(docs)
        filters = dict(self._filters)
        if "status" not in filters:
            filters["status"] = "approved"

        payload = {
            "schemaVersion": "v2",
            "snapshotAt": self._snapshot_at,
            "datasetNames": dataset_names,
            "count": len(docs),
            "filters": filters,
            "items": docs,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
