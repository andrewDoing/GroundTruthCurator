---
title: Concurrency Control
description: The concurrency control mechanism prevents race conditions during simultaneous updates
jtbd: JTBD-008
stories: [SA-246]
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Concurrency Control

## Overview

This spec documents the existing concurrency control patterns in GTC that prevent race conditions during simultaneous updates to ground-truth items and assignments.

## Problem Statement

Concurrent modifications to ground-truth items create race condition risks:

- **Lost updates**: Two users modify the same item simultaneously; one change overwrites the other
- **Double assignment**: Multiple users claim the same unassigned item
- **Inconsistent state**: Partial failures leave data in undefined states

These risks are already addressed through ETag-based optimistic concurrency control and atomic patch operations.

## Current Implementation (Already Adequate)

### ETag-Based Optimistic Concurrency

GTC uses Azure Cosmos DB's native `_etag` system property for optimistic concurrency control:

- All write paths require ETag via `If-Match` header or `etag` body field
- Cosmos DB automatically updates `_etag` on every write
- Conditional replace uses `MatchConditions.IfNotModified` with `replace_item()`
- Mismatched ETag returns HTTP 412 Precondition Failed with "ETag mismatch" message

Implementation location: [cosmos_repo.py#L854-L870](backend/app/adapters/repos/cosmos_repo.py#L854-L870)

### Atomic Patch Operations

Production assignment uses Cosmos DB patch with `filter_predicate` for atomic operations:

```python
filter_predicate = (
    f"FROM c WHERE (c.assignedTo = null OR c.assignedTo = '' "
    f"OR c.assignedTo = '{user_id}' OR c.status != 'draft')"
)
```

This atomically enforces:

- Item is unassigned (`assignedTo = null` or empty), OR
- Item is already assigned to requesting user, OR
- Item is not in draft state (allowing re-assignment of completed items)

Implementation location: [cosmos_repo.py _assign_to_with_patch()](backend/app/adapters/repos/cosmos_repo.py)

### Self-Assign Contention Handling

The self-assign workflow handles contention through overfetch and retry:

1. Samples candidates with 2× overfetch to handle contention
2. Individual assignment failures don't stop the batch
3. Retries once with exclusion list if initial pass falls short

Implementation location: [assignment_service.py#L36-L101](backend/app/services/assignment_service.py#L36-L101)

### Emulator Fallback

Cosmos DB emulator doesn't support `filter_predicate`, so GTC uses a read-modify-replace pattern for development:

- Reads current state, validates in application code, then writes
- Has a TOCTOU (time-of-check-to-time-of-use) window between read and replace
- Acceptable for development; production uses atomic patch

Implementation location: [cosmos_repo.py#L1322-L1378](backend/app/adapters/repos/cosmos_repo.py#L1322-L1378)

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-001 | All update/delete operations require valid ETag | Must | ✓ Implemented |
| FR-002 | Missing or mismatched ETag returns HTTP 412 | Must | ✓ Implemented |
| FR-003 | Assignment uses atomic patch with filter predicate | Must | ✓ Implemented |
| FR-004 | Only assigned user can modify items in draft state | Must | ✓ Implemented |
| FR-005 | Self-assign handles contention via overfetch and retry | Should | ✓ Implemented |
| FR-006 | Error response includes stable code for 412/409 conflicts | Should | ✓ Implemented |
| FR-007 | Client retry guidance documented for 412 scenarios | Should | Gap |
| FR-008 | Emulator limitations documented for developers | Should | Gap |

### Non-Functional Requirements

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-001 | Conflict detection latency | < 50ms additional overhead | ✓ Met |
| NFR-002 | 412/409 rate monitoring coverage | All API endpoints | Gap |
| NFR-003 | Zero lost updates in production under contention | 100% | ✓ Met |

## Technical Considerations

### Race Condition Scenarios

| Scenario | Risk | Current Mitigation | Status |
|----------|------|-------------------|--------|
| Ground-truth update | Lost update if two users modify same item | ETag required on all writes; 412 on mismatch | ✓ Adequate |
| Self-serve assignment | Two users claim same item | Patch with `filter_predicate` (atomic) | ✓ Adequate |
| Single-item assign | Two users click assign simultaneously | `assign_to()` is atomic in production | ✓ Adequate |
| Status transition | Concurrent approve/skip/delete | ETag enforced; separate users blocked by ownership | ✓ Adequate |
| Assignment doc cleanup | Orphaned docs if delete fails | Best-effort delete; logs error; cleaned on next query | ✓ Adequate |
| Curation instructions | Two users update dataset instructions | ETag-based conditional replace | ✓ Adequate |
| Emulator assignment | TOCTOU between read and replace | Development-only; production uses atomic patch | Acceptable |

### Monitoring Gaps

Add observability for concurrency conflicts:

- Track 412 Precondition Failed rate per endpoint
- Track 409 Conflict rate for assignment operations
- Alert on sustained high conflict rates indicating contention hotspots

### Documentation Needs

- Add client retry guidance: exponential backoff on 412 with fresh read before retry
- Document emulator limitations for local development
- Document stable error codes in API documentation

## Status Codes

| Code | Meaning | Client Action |
|------|---------|---------------|
| 409 | Conflict (duplicate ID or assignment conflict) | Do not retry without user intervention |
| 412 | Precondition Failed (ETag mismatch) | Read fresh data, then retry |
| 449 | Transient write conflict | Retry with exponential backoff |

## Open Questions

1. Should the spec define a maximum retry count for clients on 412?
2. Is orphaned assignment document cleanup needed as a background job, or is query-time cleanup sufficient?
3. Should the emulator path use ETag-based replace for better parity with production?

## References

- [Azure Cosmos DB: Transactions and Optimistic Concurrency Control](https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency)
- [Research: concurrency-control-research.md](.copilot-tracking/subagent/20260122/concurrency-control-research.md)
- [specs/assignment-workflow.md](assignment-workflow.md) - NFR-001 concurrency requirement
- [specs/data-persistence.md](data-persistence.md) - FR-005 ETag enforcement
- [backend/CODEBASE.md](../backend/CODEBASE.md) - ETag concurrency conventions
