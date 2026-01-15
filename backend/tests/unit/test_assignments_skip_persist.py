from __future__ import annotations

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone

from app.container import container
from app.domain.models import GroundTruthItem
from app.domain.enums import GroundTruthStatus


class _InMemoryRepo:
    def __init__(self):
        # Key: (datasetName, bucket_str, id)
        self.items: dict[tuple[str, str, str], GroundTruthItem] = {}

    # ---- GroundTruthRepo protocol (minimal working set for this test) ----
    async def import_bulk_gt(
        self, items: list[GroundTruthItem], buckets: int | None = None
    ):  # pragma: no cover
        raise NotImplementedError

    async def list_gt_by_dataset(self, dataset: str, status=None):  # pragma: no cover
        raise NotImplementedError

    async def list_all_gt(self, status=None):  # pragma: no cover
        raise NotImplementedError

    async def get_gt(self, dataset: str, bucket: UUID, item_id: str):  # type: ignore[override]
        key = (dataset, str(bucket), item_id)
        return self.items.get(key)

    async def upsert_gt(self, item: GroundTruthItem):  # type: ignore[override]
        # Simulate ETag update on write
        item.etag = (item.etag or "etag") + ":updated"
        key = (item.datasetName, str(item.bucket), item.id)
        self.items[key] = item
        return item

    async def soft_delete_gt(self, dataset: str, bucket: UUID, item_id: str):  # pragma: no cover
        raise NotImplementedError

    async def delete_dataset(self, dataset: str):  # pragma: no cover
        raise NotImplementedError

    async def stats(self):  # pragma: no cover
        raise NotImplementedError

    async def list_unassigned(self, limit: int):  # pragma: no cover
        raise NotImplementedError

    async def sample_unassigned(
        self, user_id: str, limit: int, exclude_ids: list[str] | None = None
    ) -> list[GroundTruthItem]:  # pragma: no cover
        raise NotImplementedError

    async def list_gt_paginated(
        self,
        status=None,
        dataset: str | None = None,
        tags: list[str] | None = None,
        item_id: str | None = None,
        ref_url: str | None = None,
        sort_by=None,
        sort_order=None,
        page: int = 1,
        limit: int = 25,
    ):  # pragma: no cover
        raise NotImplementedError

    async def list_datasets(self):  # pragma: no cover
        raise NotImplementedError

    async def assign_to(self, item_id: str, user_id: str):  # pragma: no cover
        raise NotImplementedError

    async def list_assigned(self, user_id: str):  # pragma: no cover
        raise NotImplementedError

    async def upsert_assignment_doc(self, user_id: str, gt: GroundTruthItem):  # pragma: no cover
        raise NotImplementedError

    async def list_assignments_by_user(self, user_id: str):  # pragma: no cover
        raise NotImplementedError

    async def get_assignment_by_gt(self, user_id: str, ground_truth_id: str):  # pragma: no cover
        raise NotImplementedError

    async def delete_assignment_doc(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def get_curation_instructions(self, dataset: str):  # pragma: no cover
        raise NotImplementedError

    async def upsert_curation_instructions(self, doc):  # pragma: no cover
        raise NotImplementedError


@pytest.mark.anyio
async def test_status_skipped_keeps_assignment(async_client, user_headers):
    # Arrange: seed a GT item assigned to the current user
    dataset = "ds1"
    bucket = uuid4()
    item_id = "item-1"
    assigned_at = datetime.now(timezone.utc)
    initial_etag = "v1"

    # Use a dedicated in-memory repo for this test
    orig_repo = container.repo
    repo = _InMemoryRepo()
    container.repo = repo
    try:
        gt = GroundTruthItem(
            id=item_id,
            datasetName=dataset,
            bucket=bucket,
            synthQuestion="Q?",
            status=GroundTruthStatus.draft,
            assignedTo=user_headers["X-User-Id"],
            assignedAt=assigned_at,
            _etag=initial_etag,
        )
        # Seed into repo
        await repo.upsert_gt(gt)

        # Act: mark as skipped via assignments endpoint
        res = await async_client.put(
            f"/v1/assignments/{dataset}/{bucket}/{item_id}",
            json={"status": "skipped"},
            headers={**user_headers, "If-Match": initial_etag},
        )

        # Assert
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "skipped"
        # Assignment should persist for skipped
        assert body["assignedTo"] == user_headers["X-User-Id"]
        assert body["assignedAt"] is not None
        # assignedAt should not change
        # Compare to minute precision to avoid TZ/microsecond formatting differences
        assert body["assignedAt"][:16] == assigned_at.isoformat()[:16]
    finally:
        container.repo = orig_repo
