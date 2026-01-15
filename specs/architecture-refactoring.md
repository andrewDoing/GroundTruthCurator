---
title: Architecture Refactoring
description: The architecture refactoring extracts duplicate API logic into services and splits the repository layer into focused modules.
jtbd: JTBD-003
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Architecture Refactoring

## Overview

The architecture refactoring extracts duplicate API logic into services and splits the repository layer into focused modules.

**Parent JTBD:** Help developers maintain GTC code quality

**Stories:** SA-746, SA-424

## Problem Statement

The GTC backend has accumulated technical debt in two areas:

1. **Duplicate endpoint logic**: The `assignments.py` and `ground_truths.py` API endpoints share ~80% identical code for item updates, including history parsing, ETag validation, and computed tag application.

2. **Monolithic repository**: The `cosmos_repo.py` file is 1,536 lines and conflates persistence concerns with emulator-specific workarounds, Unicode sanitization, and business logic like quota computation.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Create GroundTruthService with unified update logic | Must | Single method handles updates for both endpoints; assignments/ground_truths endpoints delegate to service |
| FR-002 | Extract shared history parsing into reusable method | Must | History parsing code appears once in service layer |
| FR-003 | Extract Cosmos emulator workarounds to separate module | Must | `cosmos_emulator.py` contains all Unicode sanitization and base64 encoding functions |
| FR-004 | Move quota computation to AssignmentService | Should | `_compute_quotas()` no longer exists in repository |
| FR-005 | Preserve all existing API contracts | Must | Frontend integration tests pass without modification |
| FR-006 | Maintain ETag behavior for concurrent edit protection | Must | 409 Conflict responses unchanged |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Maintainability | cosmos_repo.py line count | <1000 lines |
| NFR-002 | Testability | Service methods unit-testable without Cosmos | 100% service layer coverage |
| NFR-003 | Performance | No latency regression | p99 unchanged |

## User Stories

### US-001: Developer extracts update logic

**As a** backend developer
**I want to** have a single service method for ground truth updates
**So that** I can fix bugs once instead of in two places

**Acceptance Criteria:**

- [ ] Given an item update request to either endpoint, when the service processes it, then the same validation and persistence logic executes
- [ ] Given a code change to update logic, when the PR is reviewed, then only one file requires modification

### US-002: Developer navigates repository code

**As a** backend developer
**I want to** find Cosmos emulator workarounds in a dedicated file
**So that** I can understand the core repository logic without distraction

**Acceptance Criteria:**

- [ ] Given the backend codebase, when searching for Unicode sanitization, then results appear in `cosmos_emulator.py`
- [ ] Given `cosmos_repo.py`, when reviewing the file, then no `_sanitize_string_for_cosmos` functions exist

## Technical Considerations

### Target File Structure

```text
backend/app/
├── adapters/repos/
│   ├── base.py                    # Protocol (unchanged)
│   ├── cosmos_repo.py             # Core repo (~800 lines)
│   ├── cosmos_emulator.py         # Emulator workarounds (~200 lines)
│   └── tags_repo.py               # Tags (unchanged)
└── services/
    ├── ground_truth_service.py    # New: unified update logic
    ├── assignment_service.py      # Existing + quota logic
    └── ...
```

### GroundTruthService Interface

```python
class GroundTruthService:
    def __init__(self, repo: GroundTruthRepo):
        self.repo = repo

    async def update_item(
        self,
        dataset: str,
        bucket: UUID,
        item_id: str,
        updates: ItemUpdateDTO,
        user_id: str | None,
        etag: str | None,
        *,
        enforce_assignment: bool = False,
        clear_assignment_on_complete: bool = False,
    ) -> GroundTruthItem:
        """Unified item update logic for both endpoints."""

    def parse_history(self, raw_history: list[dict]) -> list[HistoryItem]:
        """Parse history from API payload."""
```

### Endpoint Refactoring Pattern

**Assignments endpoint (after):**

```python
@router.put("/{dataset}/{bucket}/{item_id}")
async def update_item(...):
    # Validate assignment ownership
    if existing.assigned_to != user.user_id:
        raise HTTPException(403, "Not your assignment")

    # Delegate to service
    return await container.ground_truth_service.update_item(
        ...,
        enforce_assignment=True,
        clear_assignment_on_complete=True,
    )
```

### Functions to Extract to cosmos_emulator.py

- `_sanitize_string_for_cosmos()`
- `_normalize_unicode_for_cosmos()`
- `_restore_unicode_from_cosmos()`
- `_base64_encode_refs_content()`
- `_base64_decode_refs_content()`
- `_list_gt_paginated_with_emulator()`
- `_assign_to_with_read_modify_replace()`

### Functions to Move to Service Layer

- `_compute_quotas()` → `AssignmentService.compute_quotas()`
- `_compute_total_references()` → `GroundTruthItem.total_references` property

### Constraints

- API contracts must be preserved (frontend tests pass)
- ETag validation behavior unchanged
- Emulator detection via URL (`localhost` / `127.0.0.1`) remains
- Container wiring pattern remains (no DI migration in this spec)

## Implementation Phases

### Phase 1: Create GroundTruthService (SA-746)

1. Create `services/ground_truth_service.py`
2. Implement `parse_history()` method
3. Implement `update_item()` with all field handling
4. Wire service in `container.py`
5. Refactor `assignments.py` to use service
6. Refactor `ground_truths.py` to use service
7. Remove duplicate code from endpoints

### Phase 2: Extract Emulator Code (SA-424)

1. Create `adapters/repos/cosmos_emulator.py`
2. Move Unicode functions
3. Move base64 encoding functions
4. Extract emulator-specific paginated list
5. Extract read-modify-replace pattern
6. Update imports in `cosmos_repo.py`

### Phase 3: Move Business Logic (SA-424)

1. Move `_compute_quotas()` to `AssignmentService`
2. Create `total_references` property on domain model
3. Remove business logic from repository

## Open Questions

| Q | Question | Owner | Status |
|---|----------|-------|--------|
| Q1 | Should emulator detection move to configuration? | Backend team | Open |
| Q2 | Should GroundTruthService handle soft delete? | Backend team | Open |

## References

- Research: [.copilot-tracking/subagent/20260122/architecture-refactoring-research.md](../.copilot-tracking/subagent/20260122/architecture-refactoring-research.md)
- [backend/app/api/v1/assignments.py](../backend/app/api/v1/assignments.py)
- [backend/app/api/v1/ground_truths.py](../backend/app/api/v1/ground_truths.py)
- [backend/app/adapters/repos/cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py)
