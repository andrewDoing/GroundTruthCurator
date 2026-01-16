---
title: Export pipeline
description: Snapshot export pipeline supporting attachment and artifact exports to local disk or Azure Blob Storage.
ms.date: 2026-01-20
ms.topic: reference
keywords:
  - export
  - snapshot
  - blob storage
  - fastapi
estimated_reading_time: 8
---

## Overview

The backend includes an export pipeline that can:

* Export ground truth items as a single JSON response (attachment)
* Export ground truth items as storage artifacts (one JSON file per item + a manifest)
* Apply a configurable chain of export processors before formatting

This pipeline is primarily exposed via the snapshot endpoints under `/v1/ground-truths/snapshot`.

## API endpoints

### POST `/v1/ground-truths/snapshot`

Creates a snapshot export.

Supports `attachment` or `artifact` delivery.

If the request body is omitted or `{}`, the server uses defaults (equivalent to `delivery.mode=attachment`).

### GET `/v1/ground-truths/snapshot`

Downloads the approved snapshot as a JSON attachment.

* Always returns a JSON document payload (not storage artifacts)
* Uses the `json_snapshot_payload` format

## Request schema

The POST body is `SnapshotExportRequest`:

```json
{
  "format": "json_snapshot_payload",
  "filters": {
    "status": "approved",
    "datasetNames": ["dataset-a", "dataset-b"]
  },
  "processors": ["merge_tags"],
  "delivery": {
    "mode": "attachment"
  }
}
```

Notes:

* `format` defaults to `json_snapshot_payload` when omitted
* `filters.status` defaults to `approved`
* `filters.datasetNames` is optional; when provided it filters items by `datasetName`
* `processors` is optional; when omitted the default processor order comes from `GTC_EXPORT_PROCESSOR_ORDER`

## Delivery modes

Set `delivery.mode` to choose how the server returns the export.

### `attachment`

Returns a JSON response with `Content-Disposition: attachment` so browsers download the file.

* `json_snapshot_payload` returns `ground-truth-snapshot-{snapshotAt}.json`
* `json_items` returns `ground-truth-items-{snapshotAt}.json`

### `artifact`

Writes artifacts to the configured storage backend and returns a JSON object describing the snapshot location.

Artifacts are written under:

* `exports/snapshots/{snapshotAt}/ground-truth-{id}.json`
* `exports/snapshots/{snapshotAt}/manifest.json`

The manifest includes:

* `schemaVersion` (currently `v2`)
* `snapshotAt`
* `datasetNames`
* `count`
* `filters`

## Formats

### `json_snapshot_payload`

Produces a single JSON object:

```json
{
  "schemaVersion": "v2",
  "snapshotAt": "20260120T123456Z",
  "datasetNames": ["dataset-a"],
  "count": 42,
  "filters": {"status": "approved"},
  "items": [ /* exported documents */ ]
}
```

This is the default for `GET /v1/ground-truths/snapshot`.

### `json_items`

Produces a raw JSON array of exported documents.

## Processors

Processors run before formatting.

### `merge_tags`

Merges tag fields into a single `tags` array on each exported document:

* Reads `manualTags`/`manual_tags` and `computedTags`/`computed_tags`
* Writes `tags` as a sorted union of the two

## Storage backends

Storage is selected via settings:

* `GTC_EXPORT_STORAGE_BACKEND=local` (default)
* `GTC_EXPORT_STORAGE_BACKEND=blob`

### Local storage

When using local storage, artifacts are written to paths under the server working directory.

The API response includes absolute paths for convenience:

* `snapshotDir`: absolute path to the snapshot directory
* `manifestPath`: absolute path to the manifest

### Azure Blob storage

When using blob storage:

* Set `GTC_EXPORT_BLOB_ACCOUNT_URL` (for example, `https://<account>.blob.core.windows.net`)
* Set `GTC_EXPORT_BLOB_CONTAINER` (container name)

The export pipeline uses `DefaultAzureCredential`.

Dependencies:

* `azure-identity`
* `azure-storage-blob`

## Configuration

Common export-related settings:

* `GTC_EXPORT_PROCESSOR_ORDER`: CSV list of processor names (for example, `merge_tags`)
* `GTC_EXPORT_STORAGE_BACKEND`: `local` or `blob`
* `GTC_EXPORT_BLOB_ACCOUNT_URL`: required when `blob`
* `GTC_EXPORT_BLOB_CONTAINER`: required when `blob`

## Tests

Unit tests cover the registry behavior, formatters, processors, and delivery modes.

## Examples

### Create a downloadable snapshot (POST)

```bash
curl -sS \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"delivery":{"mode":"attachment"}}' \
  http://localhost:8000/v1/ground-truths/snapshot \
  -o snapshot.json
```

### Create artifact export (POST)

```bash
curl -sS \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"delivery":{"mode":"artifact"}}' \
  http://localhost:8000/v1/ground-truths/snapshot
```

### Download approved snapshot (GET)

```bash
curl -sS \
  http://localhost:8000/v1/ground-truths/snapshot \
  -o snapshot.json
```
