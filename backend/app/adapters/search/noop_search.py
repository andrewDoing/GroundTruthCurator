from __future__ import annotations

from app.adapters.search.base import SearchAdapter
from app.domain.models import Reference


class NoopSearch(SearchAdapter):
    async def attach(self, item_id: str, ref: Reference) -> None:
        return None

    async def detach(self, item_id: str, ref_id: str) -> None:
        return None

    async def query(self, q: str, top: int = 5) -> list[dict[str, object]]:
        return []
