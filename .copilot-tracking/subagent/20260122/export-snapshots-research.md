---
topic: export-snapshots
jtbd: JTBD-001
date: 2026-01-22
status: complete
---

# Research: Export Snapshots

## Context

The export system generates downloadable JSON snapshots of curated data in configurable formats.

## Sources Consulted

### URLs
- (None)

### Codebase
- [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts): Includes `downloadSnapshot` function that triggers a browser download of JSON.
- [backend/app/services/snapshot_service.py](backend/app/services/snapshot_service.py): Implements snapshot export logic.

### Documentation
- [.copilot-tracking/research/20260121-high-level-requirements-research.md](.copilot-tracking/research/20260121-high-level-requirements-research.md): Consolidates export/snapshot requirements.
- [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md): Documents attachment and artifact export modes, defaults, and manifest requirements.

## Key Findings

1. The backend supports two export modes: `attachment` (single JSON file) and `artifact` (per-item JSON files + manifest).
2. The snapshot download endpoint returns a JSON document for browser download with Content-Disposition header.
3. Artifact exports include a manifest with a stable `schemaVersion` and snapshot metadata.
4. Export processors run before formatting and may merge tag fields into a single `tags` array.
5. The frontend triggers download via a service function that invokes the snapshot endpoint.

## Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| Snapshot export endpoint with Content-Disposition | [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md) | Defines wire behavior for download |
| Manifest with schemaVersion | [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md) | Defines contract for artifact mode |

## Open Questions

- (None)

## Recommendations for Spec

- Specify supported export modes (attachment, artifact) and their default behavior.
- Specify that attachment mode returns a single JSON document with download headers.
- Specify that artifact mode includes a manifest with `schemaVersion`.
