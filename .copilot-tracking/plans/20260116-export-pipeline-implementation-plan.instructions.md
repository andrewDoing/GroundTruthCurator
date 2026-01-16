---
applyTo: '.copilot-tracking/changes/20260116-export-pipeline-implementation-changes.md'
---
<!-- markdownlint-disable-file -->
# Task Checklist: Export Pipeline Implementation

## Overview

Implement the export pipeline architecture from the designs and wire it into the existing snapshot endpoints without breaking backward compatibility.

Follow repository workflow guidance from #file:../../AGENTS.md

## Objectives

* Preserve existing snapshot endpoint behavior (routes, payload keys, and `Content-Disposition` semantics).
* Introduce export pipeline components (models, registries, processors, formatters, delivery modes, and storage backends) with unit test coverage.
* Add Blob storage support behind explicit settings and a backend selector, without impacting local defaults.

## Research Summary

### Project Files

* .copilot-tracking/research/20260116-export-pipeline-implementation-research.md - Verified current snapshot contracts, coupling to frontend download behavior, and concrete code touchpoints.
* backend/app/api/v1/ground_truths.py - Snapshot endpoints that must remain backward compatible.
* backend/app/services/snapshot_service.py - Current snapshot artifact write and payload build behavior.
* backend/app/core/config.py - Settings strictness (`extra="forbid"`) that requires explicit new env vars.
* frontend/src/services/groundTruths.ts - Parses `Content-Disposition` to derive download filename.
* docs/computed-tags-design.md - Export pipeline architecture requirements.

### External References

* .copilot-tracking/research/20260116-export-pipeline-implementation-research.md - Captures SDK usage patterns and response behavior references.

## Implementation Checklist

### [x] Phase 1: Lock down compatibility contract

* [x] Task 1.1: Confirm snapshot endpoint contracts (write + download)
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 15-37)

* [x] Task 1.2: Define compatibility-safe defaults for pipeline adoption
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 39-60)

### [x] Phase 2: Build pipeline core (registries + request models)

* [x] Task 2.1: Add export pipeline request/option models
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 64-84)

* [x] Task 2.2: Implement processor and formatter registries
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 86-109)

### [x] Phase 3: Implement initial processors and formatters

* [x] Task 3.1: Implement processor `merge_tags`
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 113-130)

* [x] Task 3.2: Implement formatters `json_items` and `json_snapshot_payload`
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 132-152)

### [x] Phase 4: Storage backends and delivery modes

* [x] Task 4.1: Define and implement an export storage interface
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 156-178)

* [x] Task 4.2: Add Azure Blob storage backend
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 180-204)

* [x] Task 4.3: Implement delivery modes (attachment/artifact/stream)
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 206-227)

### [x] Phase 5: Wire into container, API, and tests

* [x] Task 5.1: Wire registries, storage, and pipeline via container
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 231-245)

* [x] Task 5.2: Update snapshot service and routes to use pipeline internally
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 247-266)

* [x] Task 5.3: Add new unit tests for pipeline components
  * Details: .copilot-tracking/details/20260116-export-pipeline-implementation-details.md (Lines 268-289)

## Dependencies

* Backend Python environment (per backend/pyproject.toml)
* Azure SDK packages:
  * `azure-identity` (already present)
  * `azure-storage-blob` (to add for Blob backend)
* Local dev: Cosmos Emulator and existing integration test environment (as already used by repo)

## Success Criteria

* Existing snapshot unit/integration tests pass unchanged.
* Export pipeline core exists and is covered by new unit tests.
* Blob backend is selectable via explicit settings and does not impact default local behavior.
