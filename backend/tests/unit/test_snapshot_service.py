from __future__ import annotations

import pytest
from typing import Any

from app.exports.formatters.json_items import JsonItemsFormatter
from app.exports.formatters.json_snapshot_payload import JsonSnapshotPayloadFormatter
from app.exports.pipeline import ExportPipeline
from app.exports.processors.merge_tags import MergeTagsProcessor
from app.exports.registry import ExportFormatterRegistry, ExportProcessorRegistry
from app.exports.storage.local import LocalExportStorage
from app.services.snapshot_service import SnapshotService
from app.domain.models import GroundTruthItem
from app.domain.enums import GroundTruthStatus


class _FakeRepo:
    def __init__(self, items: list[GroundTruthItem]):
        self._items = items
        self.calls: list[tuple[str, Any]] = []

    async def list_all_gt(self, status=None):  # type: ignore[override]
        self.calls.append(("list_all_gt", status))
        # Filter by status if provided
        if status is None:
            return list(self._items)
        return [it for it in self._items if it.status == status]

    # Stubs to satisfy GroundTruthRepo protocol for type checkers in tests
    async def import_bulk_gt(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_gt_by_dataset(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def get_gt(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def upsert_gt(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def soft_delete_gt(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def delete_dataset(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def stats(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_unassigned(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def query_unassigned_by_dataset_prefix(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def query_unassigned_global(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def sample_unassigned(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def assign_to(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def clear_assignment(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_assigned(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def upsert_assignment_doc(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_assignments_by_user(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def get_assignment_by_gt(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def delete_assignment_doc(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def get_curation_instructions(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def upsert_curation_instructions(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_gt_paginated(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_datasets(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


def _make_item(id: str, dataset: str, status: GroundTruthStatus) -> GroundTruthItem:
    return GroundTruthItem(
        id=id,
        datasetName=dataset,
        bucket=None,
        status=status,
        synthQuestion="Q?",
        answer="A",
        refs=[],
        manualTags=[],
        computedTags=[],
    )


def _build_snapshot_service(repo: _FakeRepo) -> SnapshotService:
    storage = LocalExportStorage(base_dir=".")
    pipeline = ExportPipeline(storage)
    processor_registry = ExportProcessorRegistry()
    processor_registry.register(MergeTagsProcessor())
    formatter_registry = ExportFormatterRegistry()
    formatter_registry.register(JsonItemsFormatter())
    formatter_registry.register_factory(
        "json_snapshot_payload",
        lambda snapshot_at, filters=None: JsonSnapshotPayloadFormatter(
            snapshot_at=snapshot_at,
            filters=filters,
        ),
    )
    return SnapshotService(
        repo,
        export_pipeline=pipeline,
        processor_registry=processor_registry,
        formatter_registry=formatter_registry,
        default_processor_order=[],
    )


@pytest.mark.anyio
async def test_collect_approved_calls_repo_with_status():
    items = [
        _make_item("1", "d1", GroundTruthStatus.approved),
        _make_item("2", "d2", GroundTruthStatus.draft),
    ]
    repo = _FakeRepo(items)
    svc = _build_snapshot_service(repo)

    res = await svc.collect_approved()

    # Only approved returned
    assert all(it.status == GroundTruthStatus.approved for it in res)
    # Repo called with status=approved
    assert repo.calls and repo.calls[0][0] == "list_all_gt"
    assert repo.calls[0][1] == GroundTruthStatus.approved


@pytest.mark.anyio
async def test_build_snapshot_payload_includes_only_approved():
    items = [
        _make_item("1", "d1", GroundTruthStatus.approved),
        _make_item("2", "d2", GroundTruthStatus.draft),
    ]
    repo = _FakeRepo(items)
    svc = _build_snapshot_service(repo)

    payload = await svc.build_snapshot_payload()

    assert payload["schemaVersion"] == "v2"
    assert payload["filters"]["status"] == "approved"
    assert all(it["status"] == "approved" for it in payload["items"])  # type: ignore[index]


@pytest.mark.anyio
async def test_build_snapshot_payload_counts_and_timestamp_present():
    items = [
        _make_item("1", "dx", GroundTruthStatus.approved),
        _make_item("2", "dx", GroundTruthStatus.approved),
    ]
    repo = _FakeRepo(items)
    svc = _build_snapshot_service(repo)

    payload = await svc.build_snapshot_payload()

    assert payload["count"] == 2
    # snapshotAt looks like a timestamp string
    assert isinstance(payload["snapshotAt"], str) and len(payload["snapshotAt"]) >= 15


@pytest.mark.anyio
async def test_build_snapshot_payload_has_dataset_names_sorted_unique():
    items = [
        _make_item("1", "faq", GroundTruthStatus.approved),
        _make_item("2", "docs", GroundTruthStatus.approved),
        _make_item("3", "faq", GroundTruthStatus.approved),
        _make_item("4", "", GroundTruthStatus.approved),
    ]
    repo = _FakeRepo(items)
    svc = _build_snapshot_service(repo)

    payload = await svc.build_snapshot_payload()

    assert payload["datasetNames"] == ["docs", "faq"]


@pytest.mark.anyio
async def test_build_snapshot_payload_empty_list():
    repo = _FakeRepo([])
    svc = _build_snapshot_service(repo)

    payload = await svc.build_snapshot_payload()

    assert payload["count"] == 0
    assert payload["items"] == []
