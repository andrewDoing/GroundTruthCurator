# Partial Updates Research: SA-244

**Research Date:** 2026-01-22
**Topic:** Cosmos DB Partial Document Updates (Patch Operations)
**JTBD:** Help optimize GTC performance and Cosmos usage

---

## Executive Summary

The GTC codebase currently uses **full document replacement** (`replace_item`, `upsert_item`) for most updates, but already has **one working patch implementation** for assignment operations. Expanding partial updates to additional operations would reduce network bandwidth, improve latency, and potentially lower RU consumption for common update patterns.

---

## Current Codebase Analysis

### 1. Update Methods Currently Used

| Method | Location | Usage |
|--------|----------|-------|
| `replace_item` | [cosmos_repo.py#L1113](backend/app/adapters/repos/cosmos_repo.py#L1113) | Main GT update with ETag |
| `replace_item` | [cosmos_repo.py#L1158](backend/app/adapters/repos/cosmos_repo.py#L1158) | GT update in retry loop |
| `replace_item` | [cosmos_repo.py#L1869](backend/app/adapters/repos/cosmos_repo.py#L1869) | Assignment fallback (emulator) |
| `upsert_item` | [cosmos_repo.py#L1126](backend/app/adapters/repos/cosmos_repo.py#L1126) | Create-if-missing fallback |
| `upsert_item` | [cosmos_repo.py#L1214](backend/app/adapters/repos/cosmos_repo.py#L1214) | Non-ETag updates |
| `upsert_item` | [tags_repo.py#L140](backend/app/adapters/repos/tags_repo.py#L140) | Tags document updates |
| **`patch_item`** | [cosmos_repo.py#L1784](backend/app/adapters/repos/cosmos_repo.py#L1784) | Assignment operations ✅ |

### 2. Existing Patch Implementation

The `assign_to` method at line 1784 already uses patch operations successfully:

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

This demonstrates the pattern is already in production use with conditional updates.

### 3. Main Update Operations in the Codebase

| Operation | Fields Changed | Current Method | Patch Candidate? |
|-----------|----------------|----------------|------------------|
| SME assignment | `assignedTo`, `assignedAt`, `status`, `updatedAt` | `patch_item` ✅ | Already using patch |
| Status change | `status`, `updatedAt` | `replace_item` | ✅ High priority |
| Answer approval | `status`, `reviewed_at`, `updatedBy`, `assignedTo`, `assignedAt` | `upsert_gt` | ✅ High priority |
| Edit answer | `answer`, `edited_question`, `comment`, `updatedAt` | `upsert_gt` | ✅ Medium priority |
| Add/update refs | `refs`, `totalReferences`, `updatedAt` | `upsert_gt` | ⚠️ Complex (array operations) |
| Update tags | `manualTags`, `updatedAt` | `upsert_gt` | ✅ Medium priority |
| Update history | `history` | `upsert_gt` | ⚠️ Complex (nested arrays) |
| Curation instructions | Full document | `upsert_item` | ❌ Usually full doc |
| Global tags | `tags` array | `upsert_item` | ⚠️ Could use add/remove |

---

## Azure Cosmos DB Patch API Capabilities

### Supported Operations

| Operation | Description | Use Case |
|-----------|-------------|----------|
| `set` | Set field value (creates if missing) | Status updates, field edits |
| `add` | Add to array or create field | Adding tags, refs |
| `replace` | Replace existing value (fails if missing) | Strict updates |
| `remove` | Remove field or array element | Clearing assignments |
| `incr` | Increment numeric field | Counters |
| `move` | Move value between paths | Field migrations |

### Key Limitations

1. **Max 10 operations** per patch request
2. **Item must exist** - patch_item fails if item not found (unlike upsert)
3. **No parameterized filter predicates** - SQL injection risk requires careful escaping
4. **System fields immutable** - Cannot patch `_id`, `_ts`, `_etag`, `_rid`
5. **Emulator compatibility** - May need fallback path (as implemented for assign_to)

### Python SDK Syntax

```python
# Single operation
operations = [{"op": "set", "path": "/status", "value": "approved"}]

# Multiple operations
operations = [
    {"op": "set", "path": "/status", "value": "approved"},
    {"op": "set", "path": "/reviewedAt", "value": now},
    {"op": "set", "path": "/assignedTo", "value": None},
    {"op": "remove", "path": "/assignedAt"},
]

# With conditional predicate
response = await container.patch_item(
    item=item_id,
    partition_key=partition_key,
    patch_operations=operations,
    filter_predicate="FROM c WHERE c.status = 'draft'",
    etag=etag,
    match_condition=MatchConditions.IfNotModified
)
```

---

## RU Cost Analysis

### Microsoft Documentation Findings

From the [FAQ](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update-faq):

> "Partial Document Update is normalized into request unit billing in the same way as other database operations. **Users shouldn't expect a significant reduction in RU.**"

### Key Performance Benefits

While RU cost may not dramatically decrease, partial updates provide:

1. **Reduced Network Bandwidth** - Only changed fields transmitted
2. **Lower End-to-End Latency** - Smaller payloads, faster processing
3. **Atomic Conditional Updates** - Server-side filter predicates
4. **Multi-Region Conflict Resolution** - Automatic path-level merging
5. **Reduced Client CPU** - No read-modify-write cycle needed

### Estimated Impact for GTC

| Document Type | Typical Size | Fields Updated | Bandwidth Savings |
|---------------|--------------|----------------|-------------------|
| GroundTruthItem | 5-50 KB | 2-4 fields | 80-95% |
| CurationInstructions | 1-5 KB | Full document | None |
| Tags document | <1 KB | tags array | Minimal |
| AssignmentDocument | <1 KB | Full document | Minimal |

For large GroundTruthItems with extensive history/refs, the bandwidth savings could be significant.

---

## Recommended Opportunities

### Priority 1: Status/Assignment Updates (High Impact, Low Risk)

**Target:** `upsert_gt` when only status-related fields change

```python
# New method: patch_status
async def patch_status(
    self, item_id: str, partition_key: list,
    status: GroundTruthStatus,
    assigned_to: str | None = None,
    reviewed_at: datetime | None = None,
    updated_by: str | None = None
) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    operations = [
        {"op": "set", "path": "/status", "value": status.value},
        {"op": "set", "path": "/updatedAt", "value": now},
    ]
    if assigned_to is not None:
        operations.append({"op": "set", "path": "/assignedTo", "value": assigned_to})
    # ... etc
    return await self._patch_with_fallback(item_id, partition_key, operations)
```

**API Endpoints Affected:**
- `PUT /v1/assignments/{dataset}/{bucket}/{item_id}` (approval)
- `PUT /v1/ground-truths/{dataset}/{bucket}/{item_id}` (status change)

### Priority 2: Field-Specific Updates (Medium Impact)

**Target:** Single-field updates like `edited_question`, `answer`, `comment`

```python
async def patch_fields(
    self, item_id: str, partition_key: list,
    fields: dict[str, Any], etag: str | None = None
) -> GroundTruthItem:
    operations = [
        {"op": "set", "path": f"/{k}", "value": v}
        for k, v in fields.items()
    ]
    operations.append({"op": "set", "path": "/updatedAt", "value": now})
    # ...
```

### Priority 3: Tags Updates (Medium Impact)

**Target:** `tags_repo.py` operations

```python
# Instead of read-modify-write:
operations = [{"op": "add", "path": "/tags/-", "value": new_tag}]
```

### Lower Priority / Complex Cases

- **References array** - Complex nested updates, may need full replacement
- **History array** - Deep nesting with refs inside, likely needs full document
- **Curation instructions** - Usually full document updates

---

## Implementation Considerations

### 1. Emulator Compatibility

The existing `assign_to` implementation shows the pattern:
- Try `patch_item` first
- Fall back to read-modify-replace for emulator

```python
if self.is_cosmos_emulator_in_use():
    return await self._assign_to_with_read_modify_replace(item_id, user_id)
return await self._assign_to_with_patch(item_id, user_id)
```

### 2. ETag Handling

Patch operations support ETag for optimistic concurrency:

```python
await container.patch_item(
    item=item_id,
    partition_key=pk,
    patch_operations=ops,
    etag=etag,
    match_condition=MatchConditions.IfNotModified
)
```

### 3. Error Handling

- **412 Precondition Failed** - Filter predicate not satisfied
- **404 Not Found** - Item doesn't exist (patch_item requires existence)
- **400 Bad Request** - Invalid path or operation

### 4. Testing Strategy

1. Unit tests for patch operation building
2. Integration tests against emulator (with fallback verification)
3. Integration tests against live Cosmos (if available)

---

## Conclusion

The codebase already has a working patch implementation for assignments. Expanding this pattern to status updates and field-specific edits would:

1. **Reduce network bandwidth** by 80-95% for large documents
2. **Improve latency** for common update operations
3. **Enable atomic conditional updates** without read-modify-write cycles
4. **Simplify conflict resolution** in multi-region scenarios

**Recommended next steps:**
1. Extract common patch helper method from `assign_to`
2. Implement `patch_status` for approval/status changes
3. Implement `patch_fields` for targeted field updates
4. Add comprehensive emulator fallback testing

---

## References

- [Partial document update in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update)
- [Get started with partial document update](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update-getting-started)
- [Partial document update FAQ](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update-faq)
- [Python SDK ContainerProxy.patch_item](https://learn.microsoft.com/en-us/python/api/azure-cosmos/azure.cosmos.containerproxy)
- Existing implementation: [cosmos_repo.py#L1765-L1810](backend/app/adapters/repos/cosmos_repo.py#L1765)
