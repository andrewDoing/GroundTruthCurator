from __future__ import annotations

from typing import Any

from app.adapters.search.base import SearchAdapter
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.search.documents.aio import SearchClient


class AzureAISearchAdapter(SearchAdapter):
    """Minimal adapter for Azure AI Search REST API.

    Exposes only a read-only `query` that returns a list of raw hits containing selected fields.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        api_version: str = "2024-07-01",
        api_key: str | None = None,
        token_credential: Any | None = None,
    ) -> None:
        if not endpoint or not index_name:
            raise ValueError("endpoint and index_name are required for AzureAISearchAdapter")
        self.endpoint = endpoint.rstrip("/")
        self.index_name = index_name
        self.api_version = api_version
        self.api_key = api_key
        self._token_credential = token_credential

        # Determine credential precedence: explicit api_key -> AzureKeyCredential, then provided token credential, else DefaultAzureCredential
        if api_key:
            self._credential: Any = AzureKeyCredential(api_key)
        elif token_credential is not None:
            self._credential = token_credential  # Assume caller passed an AsyncTokenCredential
        self.client = SearchClient(
            endpoint=self.endpoint, index_name=self.index_name, credential=self._credential
        )

    async def query(self, q: str, top: int = 5) -> list[dict[str, object]]:
        # Clamp top to [1, 50]
        if top < 1:
            top = 1
        if top > 50:
            top = 50

        try:
            results = await self.client.search(search_text=q, top=top)
            hits: list[dict[str, object]] = []
            async for r in results:  # type: ignore[attr-defined]
                # r may be a dict-like object; coerce to dict
                try:
                    hits.append(dict(r))  # type: ignore[arg-type]
                except Exception:
                    # Fallback: store raw object if dict conversion fails
                    hits.append({"_raw": r})  # type: ignore[list-item]
            return hits
        except HttpResponseError as e:
            status = getattr(e, "status_code", "unknown")
            message = str(e)
            raise RuntimeError(f"Azure Search error {status}: {message}") from e
