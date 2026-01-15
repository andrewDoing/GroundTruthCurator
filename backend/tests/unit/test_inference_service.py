"""Unit tests for the GTC inference adapter.

The test-client implementation in app/adapters/inference/inference.py is treated
as read-only/opaque. These tests focus on the supported shim layer exposed by
app/adapters/gtc_inference_adapter.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adapters.gtc_inference_adapter import (
    GTCInferenceAdapter,
    MAX_RESULTS,
    MAX_STRING_LENGTH,
)


class TestExtractReferences:
    def test_maps_fields_and_snippet(self):
        adapter = _make_adapter()
        calls = [
            {
                "results": [
                    {
                        "chunk_id": "doc-1",
                        "title": "Title 1",
                        "url": "https://a.com",
                        "content": "Content 1",
                    }
                ]
            }
        ]

        refs = adapter._extract_references(calls)
        assert refs == [
            {
                "id": "doc-1",
                "title": "Title 1",
                "url": "https://a.com",
                "snippet": "Content 1",
            }
        ]

    def test_falls_back_to_id_when_chunk_id_missing(self):
        adapter = _make_adapter()
        calls = [
            {"results": [{"id": "fallback", "title": "T", "url": "https://x", "content": "C"}]}
        ]
        refs = adapter._extract_references(calls)
        assert refs[0]["id"] == "fallback"

    def test_skips_calls_with_error(self):
        adapter = _make_adapter()
        calls = [
            {
                "error": "boom",
                "results": [{"chunk_id": "1", "title": "T", "url": "u", "content": "c"}],
            },
            {"results": [{"chunk_id": "2", "title": "T2", "url": "u2", "content": "c2"}]},
        ]
        refs = adapter._extract_references(calls)
        assert len(refs) == 1
        assert refs[0]["id"] == "2"

    def test_truncates_snippet(self):
        adapter = _make_adapter()
        calls = [
            {
                "results": [
                    {
                        "chunk_id": "1",
                        "title": "T",
                        "url": "u",
                        "content": "x" * (MAX_STRING_LENGTH + 5),
                    }
                ]
            }
        ]
        refs = adapter._extract_references(calls)
        assert refs[0]["snippet"].endswith("...")
        assert len(refs[0]["snippet"]) == MAX_STRING_LENGTH + 3

    def test_caps_total_references(self):
        adapter = _make_adapter()
        calls = [
            {
                "results": [
                    {
                        "chunk_id": f"doc-{i}",
                        "title": f"T{i}",
                        "url": f"https://{i}",
                        "content": "C",
                    }
                    for i in range(MAX_RESULTS + 10)
                ]
            }
        ]
        refs = adapter._extract_references(calls)
        assert len(refs) == MAX_RESULTS


class TestGenerate:
    def test_empty_message_raises(self):
        adapter = _make_adapter()
        with pytest.raises(ValueError, match="message cannot be empty"):
            adapter.generate(user_id="u", message="   ")

    def test_happy_path_returns_content_and_references(self):
        fake_inference_service = MagicMock()
        fake_inference_service.process_inference_request.return_value = {
            "response_text": "hello",
            "calls": [{"results": [{"chunk_id": "c1", "title": "t", "url": "u", "content": "s"}]}],
        }

        adapter = _make_adapter(inference_service=fake_inference_service)
        result = adapter.generate(user_id="u", message="What is X?")
        assert result["content"] == "hello"
        assert result["references"][0]["id"] == "c1"

    def test_empty_response_text_raises(self):
        fake_inference_service = MagicMock()
        fake_inference_service.process_inference_request.return_value = {
            "response_text": "",
            "calls": [],
        }
        adapter = _make_adapter(inference_service=fake_inference_service)
        with pytest.raises(RuntimeError, match="empty response"):
            adapter.generate(user_id="u", message="What is X?")

    def test_inference_exception_wrapped(self):
        fake_inference_service = MagicMock()
        fake_inference_service.process_inference_request.side_effect = Exception("kaboom")
        adapter = _make_adapter(inference_service=fake_inference_service)
        with pytest.raises(RuntimeError, match="Agent request failed"):
            adapter.generate(user_id="u", message="What is X?")


def _make_adapter(*, inference_service: object | None = None) -> GTCInferenceAdapter:
    """Create an adapter without hitting Azure SDK network calls."""
    with patch("app.adapters.gtc_inference_adapter.DefaultAzureCredential"):
        with patch("app.adapters.gtc_inference_adapter.InferenceService") as mock_inference_cls:
            if inference_service is not None:
                mock_inference_cls.return_value = inference_service

            return GTCInferenceAdapter(
                project_endpoint="https://project.example.com",
                agent_id="agent-123",
                retrieval_url="https://retrieval.example.com/search",
                permissions_scope="api://retrieval/.default",
                credential=MagicMock(),
            )
