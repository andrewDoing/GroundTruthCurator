from __future__ import annotations

from typing import Protocol, Any


class SnapshotStorage(Protocol):
    async def write_json(self, path: str, obj: Any) -> None: ...
