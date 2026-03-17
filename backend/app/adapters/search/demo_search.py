from __future__ import annotations

from app.domain.models import AgenticGroundTruthEntry
from app.plugins.pack_registry import get_rag_compat_pack


class DemoSearchAdapter:
    def __init__(self, items: list[AgenticGroundTruthEntry]) -> None:
        self._items = items

    async def query(self, q: str, top: int = 5) -> list[dict[str, object]]:
        query = q.strip().lower()
        if not query:
            return []

        matches: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        rag_pack = get_rag_compat_pack()
        for item in self._items:
            for ref in rag_pack.refs_from_item(item):
                haystack = " ".join(
                    [
                        ref.url,
                        ref.title or "",
                        ref.content or "",
                        ref.keyExcerpt or "",
                        item.datasetName,
                        item.id,
                    ]
                ).lower()
                if query not in haystack:
                    continue
                if ref.url in seen_urls:
                    continue
                seen_urls.add(ref.url)
                matches.append(
                    {
                        "url": ref.url,
                        "title": ref.title,
                        "chunk": ref.content or ref.keyExcerpt or f"Reference for {item.id}",
                    }
                )
                if len(matches) >= top:
                    return matches
        return matches
