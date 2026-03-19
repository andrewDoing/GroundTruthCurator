from __future__ import annotations

from app.domain.models import AgenticGroundTruthEntry
from app.plugins.base import PluginPackRegistry
from app.plugins.pack_registry import get_default_pack_registry


class DemoSearchAdapter:
    def __init__(
        self,
        items: list[AgenticGroundTruthEntry],
        plugin_pack_registry: PluginPackRegistry | None = None,
    ) -> None:
        self._items = items
        self._plugin_pack_registry = plugin_pack_registry or get_default_pack_registry()

    async def query(self, q: str, top: int = 5) -> list[dict[str, object]]:
        query = q.strip().lower()
        if not query:
            return []

        matches: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        for item in self._items:
            for ref in self._plugin_pack_registry.collect_search_documents(item):
                doc_id = ref.get("id")
                url = ref.get("url")
                if not isinstance(url, str) or not url:
                    continue
                haystack = " ".join(
                    [
                        str(doc_id or ""),
                        url,
                        str(ref.get("title") or ""),
                        str(ref.get("chunk") or ""),
                        item.datasetName,
                        item.id,
                    ]
                ).lower()
                if query not in haystack:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                matches.append(
                    {
                        "id": doc_id,
                        "url": url,
                        "title": ref.get("title"),
                        "chunk": ref.get("chunk") or f"Reference for {item.id}",
                    }
                )
                if len(matches) >= top:
                    return matches
        return matches
