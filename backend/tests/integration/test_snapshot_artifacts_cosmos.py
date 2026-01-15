from __future__ import annotations

from typing import Any, cast
from uuid import uuid4
from pathlib import Path

import json
import pytest
from httpx import AsyncClient


def _latest_snapshot_dir(base: str = "exports/snapshots") -> Path | None:
    root = Path(base)
    if not root.exists():
        return None
    dirs = [d for d in root.iterdir() if d.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.name)[-1]


def make_item(dataset: str, item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "synthQuestion": "Q?",
        "answer": "A",
        "refs": [],
        "manualTags": ["source:synthetic", "topic:general"],
    }


@pytest.mark.anyio
async def test_snapshot_writes_manifest_and_items(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    dataset = f"test-snap-{uuid4().hex[:6]}"
    item_id = "gt-snap-1"
    item = make_item(dataset, item_id)

    # import and approve the item
    r = await async_client.post("/v1/ground-truths", json=[item], headers=user_headers)
    assert r.status_code == 200
    r = await async_client.get(f"/v1/ground-truths/{dataset}", headers=user_headers)
    assert r.status_code == 200
    rows = cast(list[dict[str, Any]], r.json())
    etag = cast(str, rows[0]["_etag"])
    bucket = cast(str, rows[0]["bucket"])
    r = await async_client.put(
        f"/v1/ground-truths/{dataset}/{bucket}/{item_id}",
        headers={**user_headers, "If-Match": etag},
        json={"status": "approved"},
    )
    assert r.status_code == 200

    # trigger snapshot
    r = await async_client.post("/v1/ground-truths/snapshot", json={}, headers=user_headers)
    assert r.status_code == 200
    body = cast(dict[str, Any], r.json())
    snap_dir = Path(body.get("snapshotDir", ""))
    if not snap_dir or not snap_dir.exists():
        # Fallback to scanning exports/snapshots
        maybe = _latest_snapshot_dir()
        assert maybe is not None, "no snapshot dir found"
        snap_dir = maybe

    # Validate manifest
    manifest_path = snap_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    assert manifest.get("schemaVersion") == "v2"
    assert manifest.get("snapshotAt")
    count_val = cast(int, manifest.get("count", 0))
    assert count_val >= 1
    filt = cast(dict[str, Any], manifest.get("filters") or {})
    assert filt.get("status") == "approved"

    # Validate per-item JSON exists
    files = list(snap_dir.glob("ground-truth-*.json"))
    assert files, "expected at least one item json"
    doc = json.loads(files[0].read_text())
    assert doc.get("docType") == "ground-truth-item"
    assert doc.get("schemaVersion") == "v2"
    assert doc.get("status") == "approved"
