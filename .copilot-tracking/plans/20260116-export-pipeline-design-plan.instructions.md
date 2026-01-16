---
applyTo: '.copilot-tracking/changes/20260116-export-pipeline-design-changes.md'
description: Task checklist for designing an export pipeline (processors/formatters) for Ground Truth Curator
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Task Checklist: Export Pipeline Design

## Overview

Design a pluggable export pipeline (processors + formatters) that preserves current snapshot export behaviors while enabling additional formats and a multi-backend storage interface (Azure Blob as the initial concrete backend).

Follow the repository workflow guidance in `AGENTS.md` (Jujutsu commit workflow) and keep a running record of work in `.copilot-tracking/changes/20260116-export-pipeline-design-changes.md` during implementation.

## Objectives

- Preserve the existing snapshot write and download behaviors while introducing an extensible pipeline for export transforms and formats
- Define processor/formatter/registry abstractions, configuration, and a minimal initial export slice (JSON)
- Define an export storage interface that supports multiple backends, with Azure Blob Storage as the first implementation target

## Research Summary

### Project files

- `backend/app/services/snapshot_service.py` - current snapshot artifact writer and in-memory snapshot payload builder
- `backend/app/api/v1/ground_truths.py` - snapshot routes (write + downloadable attachment)
- `backend/app/adapters/storage/base.py` and `backend/app/adapters/storage/local_fs.py` - existing (currently underused) storage abstraction
- `frontend/src/services/groundTruths.ts` - frontend download expectations for `Content-Disposition`
- `docs/computed-tags-design.md` - proposes processor/formatter export pipeline architecture
- `docs/json-export-migration-plan.md` - documents JSON (not JSONL) export expectations

### External references

- `.copilot-tracking/research/20260116-export-pipeline-design-research.md` - verified repo findings and proposed pipeline shape
- FastAPI custom responses (StreamingResponse/FileResponse): https://fastapi.tiangolo.com/advanced/custom-response/
- Azure Storage Blobs client library for Python (auth patterns, async clients): https://learn.microsoft.com/en-us/python/api/overview/azure/storage-blob-readme
- Azure Blob Storage Python quickstart (managed identity / DefaultAzureCredential): https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python

### Standards references

- `AGENTS.md` - repo workflow and expectations
- `backend/CODEBASE.md` - backend layering and conventions

## Implementation Checklist

### [ ] Phase 1: Requirements and compatibility

- [ ] Task 1.1: Document the current export behavior baseline
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 15-40)

- [ ] Task 1.2: Decide the v1 export pipeline API surface
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 42-73)

### [ ] Phase 2: Pipeline abstractions

- [ ] Task 2.1: Specify processor and formatter interfaces
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 77-108)

- [ ] Task 2.2: Specify registries and configuration strategy
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 110-141)

### [ ] Phase 3: Execution flow

- [ ] Task 3.1: Specify export execution orchestration
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 145-174)

- [ ] Task 3.2: Define initial processors and formatters
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 176-206)

### [ ] Phase 4: Storage targets (multi-backend)

- [ ] Task 4.1: Define a multi-backend export storage interface
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 210-247)

- [ ] Task 4.2: Specify Azure Blob configuration and authentication strategy
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 249-280)

- [ ] Task 4.3: Define delivery strategy for Blob-hosted artifacts
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 282-311)

### [ ] Phase 5: Tests and rollout

- [ ] Task 5.1: Add test strategy for pipeline configuration and outputs
  - Details: `.copilot-tracking/details/20260116-export-pipeline-design-details.md` (Lines 315-342)

## Dependencies

- Python 3.11 + FastAPI + Pydantic v2 (already present)
- Existing GroundTruthRepo data access patterns and snapshot tests
- Azure Blob dependencies and configuration when implementing the Blob backend (e.g., `azure-storage-blob` + `azure-identity`)

## Success Criteria

- The export pipeline design is documented with clear interfaces, configuration, and a minimal initial format set (JSON)
- Snapshot endpoints remain backward compatible
- The design includes a clear path to add processors, new formats, and new storage targets without rewriting the core flow
