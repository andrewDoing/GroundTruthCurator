from __future__ import annotations

from pathlib import Path
import json

from app.adapters.storage.base import SnapshotStorage


class LocalFilesystemStorage(SnapshotStorage):
    async def write_json(self, path: str, obj):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
