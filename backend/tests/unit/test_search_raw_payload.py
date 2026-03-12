"""Unit tests for raw search payload preservation.

Validates that SearchService.query() retains the complete provider response
in the ``raw_payload`` field alongside the normalized url/title/chunk.
"""

from __future__ import annotations

import pytest

from app.services.search_service import SearchService


# ---------------------------------------------------------------------------
# Fake adapter
# ---------------------------------------------------------------------------


class FakeSearchAdapter:
    """Returns canned results for testing."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results

    async def query(self, q: str, top: int = 5) -> list[dict]:
        return self._results[:top]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_raw_payload_included_in_results():
    raw_hit = {
        "url": "https://example.com/doc1",
        "title": "Doc 1",
        "chunk": "Some text",
        "score": 0.95,
        "metadata": {"source": "index-a"},
    }
    service = SearchService(adapter=FakeSearchAdapter([raw_hit]))
    results = await service.query("test query")

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/doc1"
    assert results[0]["title"] == "Doc 1"
    assert results[0]["chunk"] == "Some text"
    assert "raw_payload" in results[0]
    assert results[0]["raw_payload"]["score"] == 0.95
    assert results[0]["raw_payload"]["metadata"] == {"source": "index-a"}


@pytest.mark.anyio
async def test_raw_payload_contains_full_provider_response():
    raw_hit = {
        "url": "https://example.com/doc2",
        "title": "Doc 2",
        "chunk": "Content",
        "extra_field_1": "value1",
        "extra_field_2": [1, 2, 3],
        "nested": {"deep": True},
    }
    service = SearchService(adapter=FakeSearchAdapter([raw_hit]))
    results = await service.query("query")

    payload = results[0]["raw_payload"]
    assert payload["extra_field_1"] == "value1"
    assert payload["extra_field_2"] == [1, 2, 3]
    assert payload["nested"]["deep"] is True


@pytest.mark.anyio
async def test_raw_payload_is_independent_copy():
    """Mutating raw_payload should not affect the normalized fields."""
    raw_hit = {"url": "https://example.com", "title": "T", "chunk": "C"}
    service = SearchService(adapter=FakeSearchAdapter([raw_hit]))
    results = await service.query("q")

    results[0]["raw_payload"]["url"] = "MODIFIED"
    assert results[0]["url"] == "https://example.com"


@pytest.mark.anyio
async def test_empty_results_no_payload():
    service = SearchService(adapter=FakeSearchAdapter([]))
    results = await service.query("q")
    assert results == []


@pytest.mark.anyio
async def test_no_adapter_returns_empty():
    service = SearchService(adapter=None)
    results = await service.query("q")
    assert results == []


@pytest.mark.anyio
async def test_configurable_field_names_with_raw_payload():
    """When field names are remapped, raw_payload still contains the original hit."""
    raw_hit = {
        "document_url": "https://example.com",
        "heading": "Title",
        "content": "Chunk text",
        "relevance": 0.88,
    }
    service = SearchService(adapter=FakeSearchAdapter([raw_hit]))
    service.url_field = "document_url"
    service.title_field = "heading"
    service.chunk_field = "content"

    results = await service.query("q")
    assert results[0]["url"] == "https://example.com"
    assert results[0]["title"] == "Title"
    assert results[0]["chunk"] == "Chunk text"
    assert results[0]["raw_payload"]["relevance"] == 0.88
    assert results[0]["raw_payload"]["document_url"] == "https://example.com"
