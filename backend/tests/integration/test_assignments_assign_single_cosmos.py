from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from httpx import AsyncClient
import pytest


def make_item(
    dataset: str, *, status: str = "draft", assigned_to: str | None = None
) -> dict[str, Any]:
    item_id = f"item-{uuid.uuid4().hex[:8]}"
    bucket_id = str(uuid.uuid4())
    item: dict[str, Any] = {
        "id": item_id,
        "datasetName": dataset,
        "bucket": bucket_id,
        "synthQuestion": "What is the meaning of life?",
        "status": status,
    }
    if assigned_to:
        item["assignedTo"] = assigned_to
        item["assignedAt"] = datetime.now(timezone.utc).isoformat()
    return item


@pytest.mark.anyio
async def test_assign_single_item_success(async_client: AsyncClient, user_headers: dict[str, str]):
    """Test successfully assigning an unassigned item to the current user."""
    ds = f"assign-single-{uuid.uuid4().hex[:6]}"
    item = make_item(ds, status="draft")
    bucket = item["bucket"]
    item_id = item["id"]

    # Import unassigned item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Assign to current user
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign", headers=user_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == item_id
    assert body["datasetName"] == ds
    assert body["bucket"] == bucket
    assert body["status"] == "draft"
    # Verify assignment fields are set (user_id from Easy Auth principal)
    assert body["assignedTo"] is not None
    assert body["assignedAt"] is not None

    # Verify assignment document was created by checking my assignments
    r = await async_client.get("/v1/assignments/my", headers=user_headers)
    assert r.status_code == 200
    my_items = r.json()
    assert any(i["id"] == item_id for i in my_items), "Item should appear in my assignments"


@pytest.mark.anyio
async def test_assign_single_item_not_found(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test assigning a non-existent item returns 404."""
    ds = f"assign-404-{uuid.uuid4().hex[:6]}"
    bucket = str(uuid.uuid4())
    item_id = "nonexistent"

    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign", headers=user_headers
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_assign_single_item_already_assigned(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test assigning an item already assigned to another user returns 409 with structured payload."""
    ds = f"assign-409-{uuid.uuid4().hex[:6]}"
    other_user = "someone-else@example.com"
    item = make_item(ds, status="draft", assigned_to=other_user)
    bucket = item["bucket"]
    item_id = item["id"]
    assigned_at = item["assignedAt"]

    # Import item assigned to another user
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Attempt to assign should fail with 409 (conflict)
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign", headers=user_headers
    )
    assert r.status_code == 409

    # Verify structured response includes assignment details
    body = r.json()
    assert "assignedTo" in body
    assert body["assignedTo"] == other_user
    assert "assignedAt" in body
    assert body["assignedAt"] == assigned_at
    assert "detail" in body


@pytest.mark.anyio
@pytest.mark.parametrize(
    "initial_status,assigned_to_other,description",
    [
        ("skipped", "someone-else@example.com", "skipped item assigned to another user"),
        ("approved", None, "approved item"),
        ("deleted", None, "deleted item"),
    ],
)
async def test_assign_single_item_non_draft_states(
    async_client: AsyncClient,
    user_headers: dict[str, str],
    initial_status: str,
    assigned_to_other: str | None,
    description: str,
):
    """Test that items in non-draft states can be assigned and will be moved to draft."""
    ds = f"assign-{initial_status}-{uuid.uuid4().hex[:6]}"
    item = make_item(ds, status=initial_status, assigned_to=assigned_to_other)
    bucket = item["bucket"]
    item_id = item["id"]

    # Import item with specific status
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Assign should succeed and move item to draft
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign", headers=user_headers
    )
    assert r.status_code == 200, f"Failed to assign {description}"
    body = r.json()
    assert body["status"] == "draft", f"{description} should be moved to draft"
    assert body["assignedTo"] is not None
    if assigned_to_other:
        # Assignment should be to the current user, not the other user
        assert body["assignedTo"] != assigned_to_other


@pytest.mark.anyio
async def test_force_assign_without_role_returns_403(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """Test that force assignment without admin/team-lead role returns 403."""
    ds = f"force-403-{uuid.uuid4().hex[:6]}"
    other_user = "someone-else@example.com"
    item = make_item(ds, status="draft", assigned_to=other_user)
    bucket = item["bucket"]
    item_id = item["id"]

    # Import item assigned to another user
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200

    # Attempt force assignment without privileged role should fail with 403
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign",
        json={"force": True},
        headers=user_headers,
    )
    assert r.status_code == 403
    body = r.json()
    assert "detail" in body
    assert "admin" in body["detail"].lower() or "team-lead" in body["detail"].lower()


@pytest.mark.anyio
async def test_force_assign_with_admin_role_succeeds(
    async_client: AsyncClient, admin_headers: dict[str, str]
):
    """Test that force assignment with admin role succeeds and cleans up previous assignment."""
    ds = f"force-admin-{uuid.uuid4().hex[:6]}"
    other_user = "someone-else@example.com"
    item = make_item(ds, status="draft", assigned_to=other_user)
    bucket = item["bucket"]
    item_id = item["id"]

    # Import item assigned to another user
    r = await async_client.post("/v1/ground-truths", json=[item], headers=admin_headers)
    assert r.status_code == 200

    # Create assignment document for the other user first
    # (simulate the other user having taken the assignment)
    # This is already done via the assignedTo field in the import

    # Force assign with admin role should succeed
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign",
        json={"force": True},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == item_id
    assert body["status"] == "draft"
    # Verify assignment is now to the admin user
    assert body["assignedTo"] is not None
    assert body["assignedTo"] != other_user  # Not the previous assignee

    # Verify the item appears in admin's assignments
    r = await async_client.get("/v1/assignments/my", headers=admin_headers)
    assert r.status_code == 200
    my_items = r.json()
    assert any(i["id"] == item_id for i in my_items), "Item should appear in admin's assignments"


@pytest.mark.anyio
async def test_force_assign_with_team_lead_role_succeeds(
    async_client: AsyncClient, team_lead_headers: dict[str, str]
):
    """Test that force assignment with team-lead role succeeds."""
    ds = f"force-lead-{uuid.uuid4().hex[:6]}"
    other_user = "someone-else@example.com"
    item = make_item(ds, status="draft", assigned_to=other_user)
    bucket = item["bucket"]
    item_id = item["id"]

    # Import item assigned to another user
    r = await async_client.post("/v1/ground-truths", json=[item], headers=team_lead_headers)
    assert r.status_code == 200

    # Force assign with team-lead role should succeed
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign",
        json={"force": True},
        headers=team_lead_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == item_id
    assert body["status"] == "draft"
    assert body["assignedTo"] is not None
    assert body["assignedTo"] != other_user


@pytest.mark.anyio
async def test_force_assign_unassigned_item_succeeds(
    async_client: AsyncClient, admin_headers: dict[str, str]
):
    """Test that force assignment of an unassigned item works (no-op for force)."""
    ds = f"force-unassigned-{uuid.uuid4().hex[:6]}"
    item = make_item(ds, status="draft")  # No assignedTo
    bucket = item["bucket"]
    item_id = item["id"]

    # Import unassigned item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=admin_headers)
    assert r.status_code == 200

    # Force assign should succeed (force has no effect on unassigned items)
    r = await async_client.post(
        f"/v1/assignments/{ds}/{bucket}/{item_id}/assign",
        json={"force": True},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == item_id
    assert body["status"] == "draft"
    assert body["assignedTo"] is not None
