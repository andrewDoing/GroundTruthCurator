from __future__ import annotations

import json

from app.exports.formatters.json_items import JsonItemsFormatter
from app.exports.formatters.json_snapshot_payload import JsonSnapshotPayloadFormatter


def test_json_items_formatter_round_trips() -> None:
    docs = [{"id": "1", "datasetName": "alpha"}]
    formatter = JsonItemsFormatter()
    payload = json.loads(formatter.format(docs))
    assert payload == docs


def test_json_snapshot_payload_formatter_builds_envelope() -> None:
    docs = [
        {"id": "1", "datasetName": "alpha", "manualTags": ["a"]},
        {"id": "2", "datasetName": "beta", "computedTags": ["b"]},
    ]
    formatter = JsonSnapshotPayloadFormatter(
        snapshot_at="20260116T000000Z",
        filters={"status": "approved", "datasetNames": ["alpha"]},
    )
    payload = json.loads(formatter.format(docs))

    assert payload["schemaVersion"] == "v2"
    assert payload["snapshotAt"] == "20260116T000000Z"
    assert payload["datasetNames"] == ["alpha", "beta"]
    assert payload["count"] == 2
    assert payload["filters"]["status"] == "approved"
    assert payload["filters"]["datasetNames"] == ["alpha"]
    assert payload["items"] == docs
