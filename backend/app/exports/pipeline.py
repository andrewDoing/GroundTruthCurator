from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi.responses import Response

from app.exports.storage.base import ExportStorage
from app.exports.storage.local import LocalExportStorage


def _snapshot_prefix(snapshot_at: str) -> str:
    return f"exports/snapshots/{snapshot_at}"


def _default_snapshot_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _collect_dataset_names(items: Iterable[dict[str, Any]]) -> list[str]:
    dataset_names = {str(item.get("datasetName", "")).strip() for item in items}
    return sorted(name for name in dataset_names if name)


class ExportPipeline:
    def __init__(self, storage: ExportStorage) -> None:
        self._storage = storage

    async def deliver_attachment(self, payload: bytes, filename: str) -> Response:
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def deliver_artifacts(
        self,
        items: list[dict[str, Any]],
        filters: dict[str, Any] | None = None,
        snapshot_at: str | None = None,
    ) -> dict[str, str | int]:
        snapshot_at = snapshot_at or _default_snapshot_at()
        prefix = _snapshot_prefix(snapshot_at)
        dataset_names = _collect_dataset_names(items)

        count = 0
        for item in items:
            item_id = str(item.get("id") or "").strip()
            if not item_id:
                continue
            key = f"{prefix}/ground-truth-{item_id}.json"
            await self._storage.write_json(key, item)
            count += 1

        manifest = {
            "schemaVersion": "v2",
            "snapshotAt": snapshot_at,
            "datasetNames": dataset_names,
            "count": count,
            "filters": filters or {"status": "approved"},
        }
        manifest_key = f"{prefix}/manifest.json"
        await self._storage.write_json(manifest_key, manifest)

        snapshot_dir = prefix
        manifest_path = manifest_key
        if isinstance(self._storage, LocalExportStorage):
            snapshot_dir = str(self._storage.resolve_local_path(prefix).resolve())
            manifest_path = str(self._storage.resolve_local_path(manifest_key).resolve())

        return {
            "snapshotDir": snapshot_dir,
            "count": count,
            "manifestPath": manifest_path,
        }
