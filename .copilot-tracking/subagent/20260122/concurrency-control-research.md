---
topic: concurrency-control
jtbd: JTBD-008
date: 2026-01-22
status: complete
---

# Research: Concurrency Control

## Context

The concurrency control mechanism prevents race conditions during simultaneous updates. This research examines how GTC handles concurrent modifications to ground-truth items and assignments, identifies potential race conditions, and documents Azure Cosmos DB's concurrency mechanisms.

## Sources Consulted

### Codebase

- [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py): Main Cosmos DB repository implementation with ETag-based optimistic concurrency
- [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py): Assignment service with self-assign workflow
- [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py): Assignment API endpoints with ETag enforcement
- [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py): Ground-truth API endpoints with ETag enforcement
- [backend/docs/user-self-serve-plan.md](backend/docs/user-self-serve-plan.md): Design document for concurrent assignment handling

### Documentation

- [Azure Cosmos DB: Transactions and Optimistic Concurrency Control](https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency): Official Microsoft documentation on ETag-based OCC
- [specs/assignment-workflow.md](specs/assignment-workflow.md): Spec documenting concurrency requirements (NFR-001)
- [specs/data-persistence.md](specs/data-persistence.md): Spec documenting ETag enforcement requirement (FR-005)
- [backend/CODEBASE.md](backend/CODEBASE.md): Documents ETag concurrency conventions

### PR Review Comments

- PR #21 review comments (URLs returned 404 - repository may be private or comments deleted)

## Key Findings

### 1. ETag-Based Optimistic Concurrency Is Implemented

GTC uses Azure Cosmos DB's native `_etag` system property for optimistic concurrency control:

- **All write paths require ETag**: Both `assignments.py` and `ground_truths.py` enforce ETag via `If-Match` header or `etag` body field
- **HTTP 412 on mismatch**: Returns "ETag mismatch" when server ETag differs from client-provided ETag
- **Conditional replace**: Uses `MatchConditions.IfNotModified` with `replace_item()` ([cosmos_repo.py#L854-L870](backend/app/adapters/repos/cosmos_repo.py#L854-L870))

### 2. Assignment Uses Patch with Filter Predicate (Production)

For production Cosmos DB, assignments use atomic patch operations with `filter_predicate`:

```python
# From cosmos_repo.py _assign_to_with_patch()
filter_predicate = (
    f"FROM c WHERE (c.assignedTo = null OR c.assignedTo = '' "
    f"OR c.assignedTo = '{user_id}' OR c.status != 'draft')"
)
```

This atomically enforces that items can only be assigned if:
- Item is unassigned (`assignedTo = null` or empty)
- Item is already assigned to requesting user
- Item is not in draft state (allowing re-assignment of completed items)

### 3. Emulator Uses Read-Modify-Replace Pattern

For Cosmos DB emulator (which doesn't support `filter_predicate`), GTC falls back to a read-modify-replace pattern ([cosmos_repo.py#L1322-L1378](backend/app/adapters/repos/cosmos_repo.py#L1322-L1378)):

```python
# Conditional check happens in application code
can_assign = (
    not current_assigned_to
    or current_assigned_to == ""
    or current_assigned_to == user_id
    or current_status != GroundTruthStatus.draft.value
)
```

**Risk**: The emulator path has a TOCTOU window between read and replace.

### 4. Assignment Document Cleanup Is Non-Atomic

When assignments complete (approve/skip/delete), the workflow:
1. Updates GroundTruthItem (clears `assignedTo`)
2. Deletes AssignmentDocument (separate operation)

If step 2 fails, orphaned assignment docs may exist. The code handles this gracefully by logging errors but not failing the request ([assignments.py#L220-L240](backend/app/api/v1/assignments.py#L220-L240)).

### 5. Self-Assign Handles Contention via Retry

The self-assign workflow ([assignment_service.py#L36-L101](backend/app/services/assignment_service.py#L36-L101)):
- Samples candidates with 2x overfetch to handle contention
- Retries once with exclusion list if initial pass is short
- Individual assignment failures don't stop the batch

## Race Condition Risks

| Operation | Risk | Current Mitigation | Recommended Fix |
|-----------|------|-------------------|-----------------|
| Ground-truth update | Lost update if two users modify same item | ETag required on all writes; 412 on mismatch | **Adequate** - correctly implemented |
| Self-serve assignment | Two users claim same item | Patch with `filter_predicate` (atomic) | **Adequate for production**; emulator has TOCTOU |
| Single-item assign | Two users click assign simultaneously | Validates `assignedTo` before `assign_to()` | **Adequate** - `assign_to()` is atomic in production |
| Status transition | Concurrent approve/skip/delete | ETag enforced; separate users blocked by ownership | **Adequate** - ownership + ETag |
| Assignment doc cleanup | Orphaned docs if delete fails | Best-effort delete; logs error | **Low risk** - docs cleaned on next user query |
| Curation instructions | Two users update dataset instructions | ETag-based conditional replace | **Adequate** |
| Emulator assignment | TOCTOU between read and replace | None (emulator limitation) | Accept risk or use stored procedure |

## Assignment Workflow Analysis

### Current Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                     Self-Serve Assignment                         │
├──────────────────────────────────────────────────────────────────┤
│ 1. sample_unassigned(limit * 2)                                  │
│    └─> Query for draft/skipped items where assignedTo is null    │
│                                                                  │
│ 2. For each candidate:                                           │
│    ├─ assign_to(item_id, user_id)                                │
│    │   └─> Patch with filter_predicate (atomic)                  │
│    │       - Success: returns True                                │
│    │       - 412/conflict: returns False                          │
│    │                                                              │
│    └─ If success: upsert_assignment_doc()                        │
│        └─> Creates materialized view doc in assignments container │
│                                                                  │
│ 3. Retry once with exclude_ids if still below limit              │
└──────────────────────────────────────────────────────────────────┘
```

### Race Scenarios

**Scenario A: Two users request assignments simultaneously**
- Both query `sample_unassigned()` and get overlapping candidate sets
- Each calls `assign_to()` with `filter_predicate`
- Cosmos DB ensures only one succeeds per item
- Losing user's request returns `False`, moves to next candidate
- **Result**: Safe - atomic at database level

**Scenario B: User A assigns while User B updates same item**
- User A holds item with ETag `E1`
- User B assigns item (changes `assignedTo`)
- User A submits update with `E1`
- Cosmos rejects with 412 (ETag `E2` now on server)
- **Result**: Safe - ETag prevents lost update

**Scenario C: Two tabs approve same item**
- Tab 1 and Tab 2 both load item with ETag `E1`
- Tab 1 approves -> succeeds, ETag becomes `E2`
- Tab 2 approves with `E1` -> 412 Precondition Failed
- **Result**: Safe - user sees conflict error

**Scenario D (Emulator only): Assignment TOCTOU**
- User A reads item (unassigned)
- User B reads item (unassigned)
- User A writes `assignedTo=A` (succeeds)
- User B writes `assignedTo=B` (succeeds - no ETag check)
- **Result**: User A's assignment lost
- **Mitigation**: Emulator is development-only; production uses atomic patch

## Azure Cosmos DB Concurrency Mechanisms

From official documentation:

### 1. Optimistic Concurrency Control (OCC)
- Every item has system-generated `_etag` property
- Updated automatically on every write
- Use `If-Match` header with `_etag` value for conditional writes
- Server returns 412 Precondition Failed on mismatch

### 2. Patch Operations with Filter Predicate
- Atomic conditional update in single round-trip
- Filter evaluated server-side before applying patch
- Returns 412 if filter doesn't match

### 3. Stored Procedures
- ACID transactions within a logical partition
- Automatic rollback on exception
- Useful for multi-item atomic operations

### 4. Status Code Summary

| Code | Meaning | Retry? |
|------|---------|--------|
| 409 | Conflict (duplicate ID or unique constraint) | No |
| 412 | Precondition Failed (ETag mismatch) | Read-then-retry |
| 449 | Transient write conflict | Yes with backoff |

## Recommendations for Spec

### Must Include

1. **ETag enforcement on all writes**: Document that all update/delete operations require valid ETag; missing or mismatched ETag returns HTTP 412
2. **Assignment atomicity**: Document that production uses Cosmos DB patch with `filter_predicate` for atomic assignment
3. **Ownership enforcement**: Document that only the assigned user can modify items in draft state
4. **Error handling contract**: Define stable error codes for 412 (ETag mismatch) and 409 (assignment conflict)

### Should Include

5. **Emulator limitations**: Note that emulator path has reduced concurrency guarantees (acceptable for development)
6. **Assignment document consistency**: Document that assignment docs are best-effort and may be orphaned temporarily
7. **Self-assign retry behavior**: Document overfetch and retry strategy for contention handling

### Nice to Have

8. **Monitoring guidance**: Recommend logging 412/409 rates to detect contention hotspots
9. **Client retry guidance**: Recommend exponential backoff on 412 with fresh read before retry
10. **Future: Stored procedure for multi-item transactions**: If cross-item atomicity needed (e.g., assignment + assignment doc creation), consider stored procedure

## Open Questions

1. Should the spec define a maximum retry count for clients on 412?
2. Is orphaned assignment document cleanup needed as a background job?
3. Should the emulator path use ETag-based replace instead of unconditional replace for better parity?
