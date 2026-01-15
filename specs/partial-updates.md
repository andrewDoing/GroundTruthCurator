---
title: Partial Document Updates
description: The partial update system patches only changed fields instead of replacing entire documents
jtbd: JTBD-008
stories: [SA-244]
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Partial Document Updates

## Overview

Expand partial document updates (patch operations) to optimize Cosmos DB performance by transmitting only changed fields instead of replacing entire 5-50KB documents, directly supporting JTBD-008's goal of optimizing GTC performance and Cosmos usage.

## Problem Statement

The GTC codebase currently uses full document replacement (`replace_item`, `upsert_item`) for most updates, even when only 2-4 fields change on documents ranging from 5-50KB. This approach:

- Transmits unnecessary data over the network for every update
- Increases end-to-end latency for common operations like status changes and approvals
- Requires read-modify-write cycles that complicate optimistic concurrency
- Misses opportunities for atomic conditional updates

The codebase already has **one working patch implementation** for assignment operations (`assign_to`), demonstrating the pattern works. Expanding this approach to additional high-frequency operations would yield significant bandwidth and latency improvements.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-01 | Status update operations use patch instead of full replacement | P1 | Status changes (draft→approved, etc.) update only status-related fields via `patch_item` |
| FR-02 | Approval workflows use patch operations | P1 | Answer approval updates `status`, `reviewed_at`, `updatedBy`, `assignedTo`, `assignedAt` via patch |
| FR-03 | Field-specific edits use targeted patches | P2 | Editing `answer`, `edited_question`, or `comment` patches only those fields plus `updatedAt` |
| FR-04 | Tag updates use array patch operations | P3 | Adding/removing tags uses `add`/`remove` operations instead of full document replacement |
| FR-05 | Patch operations support optimistic concurrency | P1 | ETag-based concurrency control works with patch operations |
| FR-06 | Emulator compatibility maintained | P1 | All patch operations fall back to read-modify-replace when running against Cosmos emulator |

### Non-Functional Requirements

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| NFR-01 | Bandwidth reduction for status updates | 80-95% reduction | Compare payload sizes before/after for typical GroundTruthItem documents |
| NFR-02 | Latency improvement for patch operations | ≤50ms p95 | Measure end-to-end latency for patch vs. replace operations |
| NFR-03 | No regression in data integrity | Zero data loss | All existing tests pass, ETags enforced on concurrent updates |
| NFR-04 | Emulator fallback latency | ≤100ms p95 | Fallback path performs within acceptable bounds for development |

## Technical Considerations

### Current State

The codebase uses several update patterns:

| Method | Usage | Location |
|--------|-------|----------|
| `replace_item` | Main GT update with ETag | Multiple locations in `cosmos_repo.py` |
| `upsert_item` | Create-if-missing and non-ETag updates | `cosmos_repo.py`, `tags_repo.py` |
| `patch_item` ✅ | Assignment operations | `cosmos_repo.py` L1784 |

The existing `assign_to` implementation demonstrates the working pattern:

```python
patch_operations = [
    {"op": "set", "path": "/assignedTo", "value": user_id},
    {"op": "set", "path": "/assignedAt", "value": now},
    {"op": "set", "path": "/status", "value": GroundTruthStatus.draft.value},
    {"op": "set", "path": "/updatedAt", "value": now},
]

await gt.patch_item(
    item=item_id,
    partition_key=partition_key,
    patch_operations=patch_operations,
    filter_predicate=filter_predicate,
)
```

### Target State

Extract reusable patch helpers and expand patch usage to:

1. **Status/approval updates** - High-frequency operations with minimal field changes
2. **Field-specific edits** - Single-field updates like `answer`, `edited_question`, `comment`
3. **Tag updates** - Array add/remove operations

### Operations to Convert

| Operation | Fields Changed | Priority | Complexity |
|-----------|----------------|----------|------------|
| Status change | `status`, `updatedAt` | P1 | Low |
| Answer approval | `status`, `reviewed_at`, `updatedBy`, `assignedTo`, `assignedAt` | P1 | Low |
| Edit answer | `answer`, `updatedAt` | P2 | Low |
| Edit question | `edited_question`, `updatedAt` | P2 | Low |
| Update comment | `comment`, `updatedAt` | P2 | Low |
| Add/remove manual tags | `manualTags`, `updatedAt` | P3 | Medium |

**Not recommended for patch conversion:**

- **References array** - Complex nested updates with validation logic
- **History array** - Deep nesting with refs inside, benefits less from patch
- **Curation instructions** - Usually full document updates anyway

### Emulator Compatibility

The Cosmos emulator may not support all patch features. The existing `assign_to` implementation provides the fallback pattern:

```python
if self.is_cosmos_emulator_in_use():
    return await self._operation_with_read_modify_replace(item_id, ...)
return await self._operation_with_patch(item_id, ...)
```

All new patch operations must implement this dual-path approach to maintain development workflow.

### Implementation Pattern

```python
async def patch_status(
    self,
    item_id: str,
    partition_key: list,
    status: GroundTruthStatus,
    assigned_to: str | None = None,
    reviewed_at: datetime | None = None,
    updated_by: str | None = None,
    etag: str | None = None,
) -> bool:
    """Patch status-related fields without full document replacement."""
    now = datetime.now(timezone.utc).isoformat()
    
    operations = [
        {"op": "set", "path": "/status", "value": status.value},
        {"op": "set", "path": "/updatedAt", "value": now},
    ]
    
    if assigned_to is not None:
        operations.append({"op": "set", "path": "/assignedTo", "value": assigned_to})
    if reviewed_at is not None:
        operations.append({"op": "set", "path": "/reviewedAt", "value": reviewed_at.isoformat()})
    if updated_by is not None:
        operations.append({"op": "set", "path": "/updatedBy", "value": updated_by})
    
    return await self._patch_with_fallback(
        item_id, partition_key, operations, etag=etag
    )

async def _patch_with_fallback(
    self,
    item_id: str,
    partition_key: list,
    operations: list[dict],
    etag: str | None = None,
    filter_predicate: str | None = None,
) -> bool:
    """Execute patch with emulator fallback."""
    if self.is_cosmos_emulator_in_use():
        return await self._patch_via_read_modify_replace(
            item_id, partition_key, operations, etag
        )
    
    kwargs = {"filter_predicate": filter_predicate} if filter_predicate else {}
    if etag:
        kwargs["etag"] = etag
        kwargs["match_condition"] = MatchConditions.IfNotModified
    
    await self.container.patch_item(
        item=item_id,
        partition_key=partition_key,
        patch_operations=operations,
        **kwargs,
    )
    return True
```

### Cosmos DB Patch API Constraints

| Constraint | Impact |
|------------|--------|
| Max 10 operations per patch | Sufficient for all identified use cases |
| Item must exist | Patch fails if item not found; use upsert for create-if-missing |
| System fields immutable | Cannot patch `_id`, `_ts`, `_etag`, `_rid` |

### Error Handling

| HTTP Status | Meaning | Response |
|-------------|---------|----------|
| 412 Precondition Failed | Filter predicate not satisfied or ETag mismatch | Retry with fresh read or return conflict |
| 404 Not Found | Item doesn't exist | Return not-found error (patch requires existence) |
| 400 Bad Request | Invalid path or operation | Log and raise validation error |

## Open Questions

1. **Metrics collection** - Should we add telemetry to compare patch vs. replace performance in production?
2. **Tag array operations** - Should tag updates use `add`/`remove` operations or `set` the entire array? Array operations are more atomic but add complexity.
3. **History updates** - Is there a subset of history operations that could benefit from patch, or should all history updates remain full-document?

## References

- [Partial document update in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update)
- [Get started with partial document update](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update-getting-started)
- [Partial document update FAQ](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update-faq)
- [Python SDK ContainerProxy.patch_item](https://learn.microsoft.com/en-us/python/api/azure-cosmos/azure.cosmos.containerproxy)
- Research file: [partial-updates-research.md](../.copilot-tracking/subagent/20260122/partial-updates-research.md)
- Existing implementation: [cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py) (assign_to method)
