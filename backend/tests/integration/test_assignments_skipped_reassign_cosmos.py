from __future__ import annotations

from typing import Any, cast
from uuid import uuid4, UUID
from datetime import datetime, timezone

from httpx import AsyncClient
from pydantic.type_adapter import TypeAdapter
import pytest

from app.domain.models import GroundTruthItem


def make_skipped_item(dataset: str, assigned_to: str) -> dict[str, Any]:
    return {
        "id": f"gt-{uuid4().hex[:8]}",
        "datasetName": dataset,
        # Use NIL UUID for explicit bucket to keep PK simple in tests
        "bucket": str(UUID("00000000-0000-0000-0000-000000000000")),
        "status": "skipped",
        "samplingBucket": 0,
        "synthQuestion": "Q?",
        # Simulate a prior assignment to another SME
        "assignedTo": assigned_to,
        "assignedAt": datetime.now(timezone.utc).isoformat(),
        "refs": [],
        "manualTags": ["source:synthetic", "split:validation"],
    }


@pytest.mark.anyio
async def test_self_serve_reassigns_skipped_and_lists_in_my(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    dataset = f"assign-skip-{uuid4().hex[:6]}"
    other_user = "someone-else"
    item = make_skipped_item(dataset, assigned_to=other_user)

    # Import the skipped item assigned to another user
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Self-serve 1 item for the current user
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 1}, headers=user_headers
    )
    assert r.status_code == 200
    payload = cast(dict[str, Any], r.json())
    assert payload.get("assignedCount") == 1

    assigned_items = TypeAdapter(list[GroundTruthItem]).validate_python(
        payload.get("assigned") or []
    )
    assert len(assigned_items) == 1
    gt = assigned_items[0]

    # After assignment, item should be assigned to current user and status should be draft
    # In integration tests, the effective user id comes from Easy Auth principal (tester@example.com)
    expected_user = "tester@example.com"
    assert gt.assignedTo == expected_user
    assert gt.status.value == "draft"

    # /my should list the item now (since it filters by assignedTo == user and status == draft)
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200
    my_items = TypeAdapter(list[GroundTruthItem]).validate_python(r.json())
    assert len(my_items) == 1
    assert my_items[0].id == gt.id
    assert my_items[0].assignedTo == expected_user
    assert my_items[0].status.value == "draft"
