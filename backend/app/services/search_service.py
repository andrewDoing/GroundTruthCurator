from __future__ import annotations

from typing import Optional, TypedDict, cast
import logging

from app.adapters.search.base import SearchAdapter
from app.core.config import settings
from app.domain.models import GroundTruthItem, Reference

logger = logging.getLogger(__name__)


class SearchResult(TypedDict):
    url: Optional[str]
    title: Optional[str]
    chunk: Optional[str]


class SearchService:
    # Canonical fields we care about from search backends
    RESULT_FIELDS: list[str] = ["url", "title", "chunk"]

    def __init__(self, adapter: SearchAdapter | None = None) -> None:
        # Adapter may be absent in some environments; keep it optional.
        self.adapter: SearchAdapter | None = adapter
        # Get configurable field names from settings
        self.url_field = settings.SEARCH_FIELD_URL
        self.title_field = settings.SEARCH_FIELD_TITLE
        self.chunk_field = settings.SEARCH_FIELD_CHUNK

    def attach_reference(self, item: GroundTruthItem, ref: Reference) -> GroundTruthItem:
        # Attach to canonical 'refs' list.
        item.refs.append(ref)
        return item

    def detach_reference(self, item: GroundTruthItem, ref_id: str) -> GroundTruthItem:
        # Detach by URL if provided; otherwise drop nothing.
        item.refs = [r for r in item.refs if getattr(r, "url", None) != ref_id]
        return item

    async def query(self, q: str, top: int = 5) -> list[SearchResult]:
        if not self.adapter:
            return []
        # Delegate and normalize shape to {url, title}
        assert self.adapter is not None
        raw_results = await self.adapter.query(q=q, top=top)
        normalized: list[SearchResult] = []
        for r in raw_results:
            # Map provider hit to canonical SearchResult using configurable field names
            url = cast(Optional[str], r.get(self.url_field))
            title = cast(Optional[str], r.get(self.title_field))
            chunk = cast(Optional[str], r.get(self.chunk_field))
            normalized.append({"url": url, "title": title, "chunk": chunk})

        logger.debug("search_service.normalized_results", extra={"count": len(normalized)})
        return normalized
