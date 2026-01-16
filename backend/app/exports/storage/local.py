from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator

from app.exports.storage.base import ExportStorage


class LocalExportStorage(ExportStorage):
    def __init__(self, base_dir: str | Path = ".") -> None:
        self._base_dir = Path(base_dir)

    async def write_json(self, key: str, obj: dict[str, Any]) -> None:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2)

    async def write_bytes(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            handle.write(data)

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        path = self._resolve_path(key)

        async def iterator() -> AsyncIterator[bytes]:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return iterator()

    async def list_prefix(self, prefix: str) -> list[str]:
        base = self._resolve_path(prefix)
        if not base.exists():
            return []
        files = [p for p in base.rglob("*") if p.is_file()]
        rel_paths = [p.relative_to(self._base_dir) for p in files]
        return [str(p).replace("\\", "/") for p in rel_paths]

    def resolve_local_path(self, key: str) -> Path:
        return self._resolve_path(key)

    def _resolve_path(self, key: str) -> Path:
        path = Path(key)
        if path.is_absolute():
            return path
        return self._base_dir / path
