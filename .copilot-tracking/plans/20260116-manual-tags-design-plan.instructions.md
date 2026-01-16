---
applyTo: '.copilot-tracking/changes/20260116-manual-tags-design-changes.md'
---
<!-- markdownlint-disable-file -->
# Task Checklist: Manual Tags Design

## Overview

Define and implement a consistent, testable manual-tags design focused on configurable mutual exclusivity within tag groups, while keeping API contracts stable for the frontend.

Follow all instructions from #file:../../.github/instructions/task-implementation.instructions.md
If that file is not present in this repository, follow `AGENTS.md` for the repo workflow and the workspace-wide instructions configured in VS Code.

## Objectives

* Define the manual tag validation policy for interactive writes vs bulk import
* Implement a backend configuration flag to enable/disable exclusivity enforcement for `exclusive=True` groups
* Ensure manual tags cannot collide with computed tags and that API contracts remain stable for the frontend

## Research Summary

### Project Files

* `.copilot-tracking/research/20260116-manual-tags-design-research.md` - Verified current behavior, key files, and decision points
* `backend/app/api/v1/tags.py` - `/v1/tags` and `/v1/tags/schema` behavior and allowlist override
* `backend/app/services/tagging_service.py` - Tag normalization and validation helpers
* `backend/app/services/validation_service.py` - Bulk import strict validation with a registry-derived allow-set
* `frontend/src/services/tags.ts` - Frontend expectations for schema and tag list payloads
* `docs/computed-tags-design.md` - Overall tags split model and computed tag constraints
* `backend/docs/tagging_plan.md` - Original intent and constraints for tag schema/rules

### External References

* `.copilot-tracking/research/20260116-manual-tags-design-research.md` (Lines 160-169) - Reference links
* <https://docs.pydantic.dev/latest/concepts/validators/> - Pydantic v2 field validator patterns
* <https://fastapi.tiangolo.com/tutorial/response-model/> - FastAPI response model behavior
* <https://learn.microsoft.com/azure/cosmos-db/partitioning-overview> - Cosmos DB partitioning constraints relevant to the global tags container

## Implementation Checklist

### [ ] Phase 1: Confirm requirements and align policy

* [ ] Task 1.1: Decide manual tag validation mode(s) (MVP)
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 18-53)

* [ ] Task 1.2: Decide the source of truth for “allowed manual tags” (optional / follow-up)
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 54-73)

### [ ] Phase 2: Implement configurable exclusivity (backend)

* [ ] Task 2.1: Add a config flag to enable/disable exclusivity enforcement
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 76-97)

* [ ] Task 2.2: Document and expose the exclusivity flag (if needed)
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 98-110)

### [ ] Phase 3: Validation and normalization improvements

* [ ] Task 3.1: Ensure exclusivity toggle does not affect computed-tags invariants
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 113-125)

* [ ] Task 3.2: Confirm computed tag stripping remains authoritative
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 126-141)

### [ ] Phase 4: API contracts and frontend expectations

* [ ] Task 4.1: Confirm `/v1/tags/schema` and frontend behavior under the toggle
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 144-157)

* [ ] Task 4.2: Confirm `/v1/tags` response contract (optional / follow-up)
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 158-168)

### [ ] Phase 5: Verification and documentation

* [ ] Task 5.1: Add/adjust tests for exclusivity toggle
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 171-184)

* [ ] Task 5.2: Document configuration and operations
  * Details: `.copilot-tracking/details/20260116-manual-tags-design-details.md` (Lines 185-196)

## Dependencies

* Python 3.11, `uv`, FastAPI, Pydantic v2
* Azure Cosmos DB (or emulator) when validating tags registry persistence
* Frontend build toolchain (Vite) to verify tag-picker behavior end-to-end

## Success Criteria

* Manual tag policy is explicitly defined and implemented consistently across all write paths
* The `/v1/tags` and `/v1/tags/schema` contracts remain stable and match frontend expectations
* Provider selection is test-covered and computed-tag collisions are prevented at startup and on write
