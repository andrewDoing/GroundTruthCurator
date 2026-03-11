from __future__ import annotations

from typing import Optional, TypedDict, cast
import logging

from app.adapters.search.base import SearchAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchResult(TypedDict):
    url: Optional[str]
    title: Optional[str]
    chunk: Optional[str]


class SearchService:
    """Generic search façade backed by a pluggable SearchAdapter.

    This service handles the retrieval-query path (``/v1/search``) only.
    Reference selection and attachment are RAG-compat concerns owned by
    ``RagCompatPack``; they are not part of the generic core.
    """

    # Canonical fields we care about from search backends
    RESULT_FIELDS: list[str] = ["url", "title", "chunk"]

    def __init__(self, adapter: SearchAdapter | None = None) -> None:
        # Adapter may be absent in some environments; keep it optional.
        self.adapter: SearchAdapter | None = adapter
        # Get configurable field names from settings
        self.url_field = settings.SEARCH_FIELD_URL
        self.title_field = settings.SEARCH_FIELD_TITLE
        self.chunk_field = settings.SEARCH_FIELD_CHUNK

    async def query(self, q: str, top: int = 5) -> list[SearchResult]:
        """Query the configured search backend and return normalized results.

        Returns an empty list when no adapter is configured.
        """
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
