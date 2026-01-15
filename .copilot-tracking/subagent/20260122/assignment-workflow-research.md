---
topic: assignment-workflow
jtbd: JTBD-001
date: 2026-01-22
status: complete
---

# Research: Assignment Workflow

## Context

The assignment workflow enables users to request, claim, and complete curation work items with ownership and optimistic concurrency protections.

## Sources Consulted

### URLs
- (None)

### Codebase
- [backend/CODEBASE.md](backend/CODEBASE.md): Documents the assignment endpoints and ETag/soft-delete conventions.
- [frontend/README.md](frontend/README.md): Describes dev user simulation header usage.

### Documentation
- [.copilot-tracking/research/20260121-high-level-requirements-research.md](.copilot-tracking/research/20260121-high-level-requirements-research.md): Consolidates observed requirements and cites detailed sources.
- [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md): Captures intended stable API semantics for assignment-related write paths.
- [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md): Defines the single-item self-assign behavior and conflict protection.

## Key Findings

1. The system supports a self-serve assignment flow that returns items to work on, and a “my assignments” view scoped to the current user.
2. Assignment write paths enforce optimistic concurrency via ETag (If-Match or equivalent) and return stable conflict semantics.
3. Assignment ownership is enforced for mutation endpoints with a stable ownership error when violated.
4. Status transitions that represent completing work (approve/skip/delete) clear assignment fields atomically.
5. Doc-only gaps exist in PRD artifacts, but they are not treated as current requirements when not reflected in code.

## Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| ETag-based optimistic concurrency | [backend/CODEBASE.md](backend/CODEBASE.md) | Defines write preconditions and conflict behavior |
| Dev user simulation via header | [frontend/README.md](frontend/README.md) | Supports per-user assignment semantics in development |

## Open Questions

- (None)

## Recommendations for Spec

- Specify assignment lifecycle states and ownership/ETag requirements as stable contracts.
- Specify what “my assignments” returns (draft items assigned to the current user).
- Specify expected error behavior for ETag mismatch and ownership violations.
