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
            "history": [
                {"role": "user", "msg": "What is the capital of France?"},
                {"role": "assistant", "msg": "Paris."},
            ],
        },
        {
            "id": "",
            "datasetName": "test-dataset",
            "history": [
                {"role": "user", "msg": "How does gravity work?"},
            ],
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
            "history": [
                {"role": "user", "msg": "This is a valid question that meets length requirements?"},
            ],
        },
        {
            "id": "valid-2",
            "datasetName": "test-dataset",
            "history": [
                {"role": "user", "msg": "Another valid question that is long enough?"},
            ],
        },
        {
            "id": "invalid-history",
            "datasetName": "test-dataset",
            "history": [
                {"role": "user", "msg": ""},
            ],
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
    details = data.get("detail") or []
    assert any("history fields cannot be empty" in err.get("msg", "") for err in details)
