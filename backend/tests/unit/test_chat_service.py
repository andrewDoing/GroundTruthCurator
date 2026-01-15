from __future__ import annotations

import pytest

from app.services.chat_service import ChatService
from app.adapters.agent_steps_store import AgentStepsStore


class FakeInferenceService:
    """Fake InferenceService that returns canned responses for testing."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def generate(self, *, user_id: str, message: str) -> dict:
        """Synchronous generate matching InferenceService interface."""
        self.calls.append((user_id, message))
        return self.response


class RecordingStore(AgentStepsStore):
    def __init__(self) -> None:
        self.saved: list[dict[str, object]] = []

    async def save(self, *, user_id: str, request: dict, response: dict) -> None:  # type: ignore[override]
        self.saved.append({"user_id": user_id, "request": request, "response": response})


@pytest.mark.anyio
async def test_generate_response_mock_fallback():
    """When inference_service is None, ChatService returns mock response."""
    service = ChatService(inference_service=None)
    result = await service.generate_response(user_id="u", message="hi", context=None)
    assert "content" in result
    assert isinstance(result["references"], list)


@pytest.mark.anyio
async def test_generate_response_passes_through_inference_response():
    """ChatService passes through response from InferenceService."""
    fake_response = {"content": "hello", "references": [{"id": "r1"}]}
    inference = FakeInferenceService(fake_response)
    service = ChatService(inference_service=inference)  # type: ignore[arg-type]

    result = await service.generate_response(user_id="user", message="msg", context="ctx")
    assert result == fake_response
    assert inference.calls == [("user", "msg")]


@pytest.mark.anyio
async def test_generate_response_persists_steps_when_enabled():
    """ChatService persists steps when store_steps is enabled."""
    fake_response = {"content": "hello", "references": []}
    inference = FakeInferenceService(fake_response)
    store = RecordingStore()
    service = ChatService(inference_service=inference, steps_store=store, store_steps=True)  # type: ignore[arg-type]

    await service.generate_response(user_id="user", message="msg", context=None)
    assert store.saved
    saved = store.saved[0]
    assert saved["user_id"] == "user"
    assert saved["response"] == fake_response
