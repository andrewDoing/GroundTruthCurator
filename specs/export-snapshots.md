---
title: Export Snapshots
description: The export system generates downloadable JSON snapshots of curated data.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Export Snapshots

## Overview

The export system generates downloadable JSON snapshots of curated data.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

Teams need to export curated ground-truth data for downstream consumption, training pipelines, or archival purposes, in formats that include metadata and support both single-file and per-item outputs.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The system shall support exporting approved items as a single JSON attachment | Must | Calling export returns a JSON file for download |
| FR-002 | The system shall support exporting approved items as per-item JSON files with a manifest (artifact mode) | Should | Calling export with artifact mode produces individual files plus manifest |
| FR-003 | The snapshot download endpoint shall return a JSON document with Content-Disposition header | Must | Browser downloads the file with suggested filename |
| FR-004 | Artifact exports shall include a manifest with `schemaVersion` and snapshot metadata | Must | Manifest contains version and metadata fields |
| FR-005 | Export processors shall run before formatting and may merge tag fields | Should | Exported items have a single `tags` array if configured |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Compatibility | Manifest `schemaVersion` shall be stable across releases | Version documented and incremented on breaking changes |
| NFR-002 | Defaults | When no request body is provided, attachment mode is the default | Endpoint works without explicit mode selection |

## User Stories

### US-001: Download Snapshot

**As a** curator
**I want to** download a snapshot of approved items
**So that** I can use them in downstream pipelines

**Acceptance Criteria:**
- [ ] Given I trigger export, when the response arrives, then my browser downloads a JSON file

### US-002: Export Artifacts

**As a** pipeline operator
**I want to** export items as individual files with a manifest
**So that** I can process them incrementally

**Acceptance Criteria:**
- [ ] Given I request artifact mode, when export completes, then per-item JSON files and a manifest are produced

## Technical Considerations

### Data Model

- Snapshot output in attachment mode: single JSON array of items.
- Snapshot output in artifact mode: directory with `manifest.json` and `items/<id>.json` files.
- Manifest includes `schemaVersion`, `exportedAt`, `itemCount`.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Backend API | Generate snapshot | POST /v1/ground-truths/snapshot |
| File system | Write artifact files | Server writes to exports/snapshots/ |

### Constraints

- Only approved items are included in exports by default.
- Export processors are configurable and run before serialization.

## Open Questions

(None)

## References

- [backend/docs/export-pipeline.md](../backend/docs/export-pipeline.md)
- [frontend/src/services/groundTruths.ts](../frontend/src/services/groundTruths.ts)
