from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_chat_rejects_empty_message(async_client, user_headers):
    res = await async_client.post(
        "/v1/chat",
        json={"message": "   "},
        headers=user_headers,
    )
    assert res.status_code == 422


@pytest.mark.anyio
async def test_chat_rejects_suspicious_content(async_client, user_headers):
    res = await async_client.post(
        "/v1/chat",
        json={"message": "<script>alert(1)</script>"},
        headers=user_headers,
    )
    assert res.status_code == 422


@pytest.mark.anyio
async def test_chat_returns_expected_fields(async_client, user_headers):
    # reset_chat_state fixture ensures CHAT_ENABLED is True by default
    # and inference_service/chat_service are properly initialized
    res = await async_client.post(
        "/v1/chat",
        json={"message": "Tell me something"},
        headers=user_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert "content" in body
    assert isinstance(body.get("references"), list)


@pytest.mark.anyio
async def test_chat_returns_503_when_disabled(async_client, user_headers, monkeypatch):
    # Use monkeypatch to avoid polluting global state
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHAT_ENABLED", False)

    res = await async_client.post(
        "/v1/chat",
        json={"message": "anything"},
        headers=user_headers,
    )
    assert res.status_code == 503
