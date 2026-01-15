"""Integration tests for bulk import validation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_bulk_import_with_valid_items_passes(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Bulk import with all valid items should succeed."""
    payload = [
        {
            "id": "",
            "datasetName": "test-dataset",
            "synthQuestion": "What is the capital of France?",
            "refs": [{"url": "https://example.com", "content": "Paris info"}],
        },
        {
            "id": "",
            "datasetName": "test-dataset",
            "synthQuestion": "How does gravity work?",
        },
    ]

    response = await async_client.post(
        "/v1/ground-truths",
        json=payload,
        headers=user_headers,
    )

    # Print response for debugging
    if response.status_code != 200:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")

    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) == 0
    assert len(data["uuids"]) == 2


@pytest.mark.anyio
async def test_bulk_import_filters_invalid_items(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Bulk import with mixed valid/invalid items should import only valid ones."""
    payload = [
        {
            "id": "valid-1",
            "datasetName": "test-dataset",
            "synthQuestion": "This is a valid question that meets length requirements?",
        },
        {
            "id": "valid-2",
            "datasetName": "test-dataset",
            "synthQuestion": "Another valid question that is long enough?",
        },
        {
            "id": "invalid-url",
            "datasetName": "test-dataset",
            "synthQuestion": "Question with bad reference URL?",
            "refs": [{"url": ""}],
        },
    ]

    response = await async_client.post(
        "/v1/ground-truths",
        json=payload,
        headers=user_headers,
    )

    assert response.status_code == 422
    data = response.json()

    # Check that errors mention validation issues
    error_text = data["detail"][0]["msg"]
    assert "Reference URL cannot be empty" in error_text or "invalid-url" in error_text
