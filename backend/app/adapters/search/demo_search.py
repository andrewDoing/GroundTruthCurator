from __future__ import annotations

from app.domain.models import AgenticGroundTruthEntry


class DemoSearchAdapter:
    def __init__(self, items: list[AgenticGroundTruthEntry]) -> None:
        self._items = items

    async def query(self, q: str, top: int = 5) -> list[dict[str, object]]:
        query = q.strip().lower()
        if not query:
            return []

        matches: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        for item in self._items:
            refs = list(item.refs)
            for turn in item.history or []:
                refs.extend(getattr(turn, "refs", None) or [])
            for ref in refs:
                haystack = ' '.join(
                    [ref.url, ref.title or '', ref.content or '', ref.keyExcerpt or '', item.datasetName, item.id]
                ).lower()
                if query not in haystack:
                    continue
                if ref.url in seen_urls:
                    continue
                seen_urls.add(ref.url)
                matches.append(
                    {
                        'url': ref.url,
                        'title': ref.title,
                        'chunk': ref.content or ref.keyExcerpt or f'Reference for {item.id}',
                    }
                )
                if len(matches) >= top:
                    return matches
        return matches
