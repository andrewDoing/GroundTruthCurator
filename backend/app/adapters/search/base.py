from __future__ import annotations

from typing import Protocol


class SearchAdapter(Protocol):
    async def query(self, q: str, top: int = 5) -> list[dict[str, object]]: ...
