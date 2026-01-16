---
title: Export pipeline implementation changes
description: Tracking updates for the export pipeline implementation work.
ms.date: 2026-01-16
---

<!-- markdownlint-disable-file -->
# Release Changes: Export pipeline implementation

**Related Plan**: 20260116-export-pipeline-implementation-plan.instructions.md
**Implementation Date**: 2026-01-16

## Summary

Tracking updates for the export pipeline implementation tasks.

## Changes

### Added

* backend/app/exports/__init__.py - Introduced the export pipeline package marker.
* backend/app/exports/models.py - Added request models for snapshot export defaults.
* backend/app/exports/registry.py - Added processor and formatter registries with name resolution helpers.
* backend/app/exports/processors/__init__.py - Added export processor package marker.
* backend/app/exports/processors/merge_tags.py - Added merge tags export processor.
* backend/app/exports/formatters/__init__.py - Added export formatter package marker.
* backend/app/exports/formatters/json_items.py - Added JSON items export formatter.
* backend/app/exports/formatters/json_snapshot_payload.py - Added JSON snapshot payload formatter.
* backend/tests/unit/test_export_registry.py - Added unit tests for export registry behavior.
* backend/tests/unit/test_export_formatters.py - Added unit tests for export formatter outputs.
* backend/tests/unit/test_export_processors.py - Added unit tests for export processor behavior.
* backend/app/exports/storage/__init__.py - Added export storage package marker.
* backend/app/exports/storage/base.py - Added export storage interface protocol.
* backend/app/exports/storage/local.py - Added local filesystem export storage backend.
* backend/app/exports/storage/blob.py - Added Azure Blob export storage backend.
* backend/app/exports/pipeline.py - Added pipeline delivery helpers for attachments, streams, and artifacts.
* backend/tests/unit/test_export_pipeline.py - Added unit tests for pipeline delivery behaviors.

### Modified

* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Task 1.1 complete after verifying snapshot endpoint contracts.
* backend/app/api/v1/ground_truths.py - Allowed optional snapshot request bodies while preserving legacy behavior.
* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Task 1.2 and Phase 1 as complete.
* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Task 2.1 complete after adding request models.
* backend/app/core/config.py - Added export processor order setting for pipeline configuration.
* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Task 2.2 and Phase 2 as complete.
* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Tasks 3.1-3.2 and Phase 3 as complete.
* backend/app/core/config.py - Added export storage settings and blob configuration validation.
* backend/pyproject.toml - Added Azure Blob SDK dependency.
* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Tasks 4.1-4.3 and Phase 4 as complete.
* backend/app/container.py - Wired export registries, storage, and pipeline into the container.
* backend/app/exports/registry.py - Added formatter factory support for contextual formatting.
* backend/app/exports/formatters/json_snapshot_payload.py - Preserved legacy filters by avoiding injected dataset names.
* backend/app/services/snapshot_service.py - Delegated snapshot payloads and artifacts to the export pipeline.
* backend/app/api/v1/ground_truths.py - Routed snapshot POST requests through the pipeline with validation.
* backend/tests/unit/test_snapshot_service.py - Updated snapshot service tests for pipeline wiring.
* backend/tests/unit/test_export_registry.py - Updated registry tests for formatter creation.
* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Marked Tasks 5.1-5.3 and Phase 5 as complete.

### Removed

* .copilot-tracking/prompts/implement-export-pipeline-implementation.prompt.md - Removed implementation prompt after completing tasks.

## Release Summary

Total files affected: 26.

### Files Created (17)

* backend/app/exports/__init__.py - Export pipeline package marker
* backend/app/exports/models.py - Snapshot export request models
* backend/app/exports/registry.py - Export processor and formatter registries
* backend/app/exports/processors/__init__.py - Export processors package marker
* backend/app/exports/processors/merge_tags.py - Merge tags export processor
* backend/app/exports/formatters/__init__.py - Export formatters package marker
* backend/app/exports/formatters/json_items.py - JSON items formatter
* backend/app/exports/formatters/json_snapshot_payload.py - Snapshot payload formatter
* backend/app/exports/storage/__init__.py - Export storage package marker
* backend/app/exports/storage/base.py - Export storage protocol
* backend/app/exports/storage/local.py - Local export storage backend
* backend/app/exports/storage/blob.py - Azure Blob export storage backend
* backend/app/exports/pipeline.py - Export pipeline delivery helpers
* backend/tests/unit/test_export_registry.py - Export registry unit tests
* backend/tests/unit/test_export_formatters.py - Export formatter unit tests
* backend/tests/unit/test_export_processors.py - Export processor unit tests
* backend/tests/unit/test_export_pipeline.py - Export pipeline delivery unit tests

### Files Modified (8)

* .copilot-tracking/plans/20260116-export-pipeline-implementation-plan.instructions.md - Task progress updates
* .copilot-tracking/changes/20260116-export-pipeline-implementation-changes.md - Change tracking updates
* backend/app/api/v1/ground_truths.py - Snapshot pipeline routing and validation
* backend/app/core/config.py - Export settings and blob validation
* backend/app/container.py - Export pipeline wiring
* backend/app/services/snapshot_service.py - Pipeline-backed snapshot logic
* backend/pyproject.toml - Azure Blob SDK dependency
* backend/tests/unit/test_snapshot_service.py - Pipeline-aware snapshot tests

### Files Removed (1)

* .copilot-tracking/prompts/implement-export-pipeline-implementation.prompt.md - Cleanup prompt file

### Dependencies & Infrastructure

* New dependency azure-storage-blob
* Export storage settings and validation in backend/app/core/config.py

### Deployment Notes

Ensure the blob backend settings are configured before switching `GTC_EXPORT_STORAGE_BACKEND` to `blob`.
