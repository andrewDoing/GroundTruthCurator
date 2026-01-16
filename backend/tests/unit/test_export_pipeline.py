from __future__ import annotations

import json

import pytest

from app.exports.pipeline import ExportPipeline
from app.exports.storage.local import LocalExportStorage


@pytest.mark.anyio
async def test_deliver_artifacts_writes_manifest_and_items(tmp_path) -> None:
    storage = LocalExportStorage(base_dir=tmp_path)
    pipeline = ExportPipeline(storage)

    items = [{"id": "1", "datasetName": "alpha", "status": "approved"}]
    result = await pipeline.deliver_artifacts(
        items=items,
        filters={"status": "approved"},
        snapshot_at="20260116T000000Z",
    )

    assert result["count"] == 1
    manifest_path = tmp_path / "exports" / "snapshots" / "20260116T000000Z" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["schemaVersion"] == "v2"
    assert manifest["filters"]["status"] == "approved"


@pytest.mark.anyio
async def test_deliver_attachment_sets_content_disposition(tmp_path) -> None:
    pipeline = ExportPipeline(LocalExportStorage(base_dir=tmp_path))
    response = await pipeline.deliver_attachment(b"{}", filename="snapshot.json")
    assert response.headers.get("Content-Disposition") == 'attachment; filename="snapshot.json"'
    assert response.body == b"{}"
