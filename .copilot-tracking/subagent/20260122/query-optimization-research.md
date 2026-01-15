---
topic: query-optimization
jtbd: JTBD-008
date: 2026-01-22
status: complete
stories: SA-247, SA-248
---

# Research: Query Optimization

## Context

The query optimization effort replaces expensive cross-partition queries with efficient patterns. This research identifies all Cosmos DB queries in the GTC codebase, analyzes their partition key usage, and provides recommendations for optimization.

## Sources Consulted

### Codebase

- [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py): Main repository with all Cosmos DB queries
- [config.py](backend/app/core/config.py): Configuration including pagination limits and `PAGINATION_TAG_FETCH_MAX`
- [assignments.py](backend/app/api/v1/assignments.py): Assignment API endpoints
- [tags_repo.py](backend/app/adapters/repos/tags_repo.py): Tags repository (uses point reads)

### Documentation

- [Optimize request cost in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/optimize-cost-reads-writes): Point reads cost ~1 RU/KB, queries vary significantly
- [Query an Azure Cosmos DB container](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-query-container): Cross-partition queries fan out to all physical partitions
- [Partitioning and horizontal scaling](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning-overview): Partition key selection best practices

## Key Findings

### 1. Partition Key Strategy

**Current Strategy**: MultiHash hierarchical key on `[/datasetName, /bucket]`

```python
# From cosmos_repo.py line 205
Partition key strategy: MultiHash hierarchical key on [/datasetName, /bucket].
The `bucket` field is a UUID and is stored as its string representation.
```

**Implications**:

- Single-partition queries require BOTH `datasetName` AND `bucket` values
- Queries filtering only by `datasetName` are still cross-partition (across buckets)
- Queries without either filter scan ALL partitions

### 2. The Arbitrary 200 Limit (SA-248)

Found in multiple locations as `min(limit, 200)` or `min(take, 200)`:

| Location | Line | Context |
|----------|------|---------|
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1405) | 1405 | `list_unassigned()`: `max_item_count=min(limit, 200)` |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1623) | 1623 | `_query_unassigned_by_selector()`: `max_item_count=min(take, 200)` |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1678) | 1678 | `_query_unassigned_global_excluding_user()`: `max_item_count=min(take, 200)` |

**Issue**: This hardcoded 200 limit caps how many unassigned items can be fetched per query, but:

- It's undocumented and appears arbitrary
- The comment doesn't explain why 200 was chosen
- May cause issues if more items are needed for fair sampling across datasets
- Creates inconsistency with `PAGINATION_TAG_FETCH_MAX` (500) in config

### 3. Cross-Partition Queries Identified

**`enable_scan_in_query=True` appears 16+ times**, indicating cross-partition queries:

| Category | Count | Notes |
|----------|-------|-------|
| Total cross-partition queries | 16 | All use `enable_scan_in_query=True` |
| Single-partition operations | 2 | Assignment lookups use `enable_scan_in_query=False` |
| Point reads | 3 | `read_item()` calls with full partition key |

## Expensive Query Inventory

| Query Location | Query Pattern | Issue | Recommendation |
|----------------|---------------|-------|----------------|
| [cosmos_repo.py:525](backend/app/adapters/repos/cosmos_repo.py#L525) | `list_all_gt()` - `SELECT * FROM c` with optional status filter | Full container scan, no partition key filter | Add pagination, consider batch processing |
| [cosmos_repo.py:759](backend/app/adapters/repos/cosmos_repo.py#L759) | `list_gt_paginated()` - ORDER BY with OFFSET/LIMIT | Cross-partition with sort | Already optimized with server-side pagination |
| [cosmos_repo.py:1350](backend/app/adapters/repos/cosmos_repo.py#L1350) | `stats()` - `SELECT c.status FROM c` | Full container scan for counts | Use Change Feed or materialized view |
| [cosmos_repo.py:1375](backend/app/adapters/repos/cosmos_repo.py#L1375) | `list_datasets()` - `SELECT DISTINCT VALUE c.datasetName` | Full container scan | Cache results, use Change Feed |
| [cosmos_repo.py:1404](backend/app/adapters/repos/cosmos_repo.py#L1404) | `list_unassigned()` - status filter only | Cross-partition, capped at 200 | Could use composite index |
| [cosmos_repo.py:1742](backend/app/adapters/repos/cosmos_repo.py#L1742) | `assign_to()` - `SELECT TOP 1 ... WHERE c.id = @id` | Cross-partition lookup by ID only | **Should use point read if PK known** |
| [cosmos_repo.py:1818](backend/app/adapters/repos/cosmos_repo.py#L1818) | `_assign_to_with_read_modify_replace()` - `SELECT TOP 1 * FROM c WHERE c.id = @id` | Cross-partition for emulator | Inherent emulator limitation |
| [cosmos_repo.py:1896](backend/app/adapters/repos/cosmos_repo.py#L1896) | `list_assigned()` - filter by `assignedTo` | Cross-partition by user | Consider separate index or container |
| [cosmos_repo.py:_get_filtered_count](backend/app/adapters/repos/cosmos_repo.py#L944) | `SELECT VALUE COUNT(1)` | Cross-partition aggregation | Cache or use Change Feed |

## Point Read Opportunities

Per Microsoft documentation, point reads cost ~1 RU per KB vs queries which can cost 3-10+ RU:

| Current Pattern | Location | Optimization |
|-----------------|----------|--------------|
| Query by ID for assignment | Line 1742 | If `datasetName` and `bucket` are available, use `read_item()` |
| Get item after upsert | Multiple | Already uses `get_gt()` with point read ✓ |

**Already optimized**:

- `get_gt()` (line 1058) - Uses `read_item()` with full partition key
- `get_curation_instructions()` (line 1086) - Uses `read_item()`
- Tags repo (line 121) - Uses `read_item()`

## Arbitrary Limit Analysis (SA-248)

### Current Behavior

The 200 limit appears in three methods related to unassigned item sampling:

```python
# cosmos_repo.py line 1405
max_item_count=min(limit, 200)

# cosmos_repo.py line 1623
max_item_count=min(take, 200)

# cosmos_repo.py line 1678
max_item_count=min(take, 200)
```

### Implications

1. **Fairness**: When sampling across datasets with different sizes, the 200 cap may prevent fair distribution
2. **Performance**: The limit exists to prevent runaway queries but lacks documentation
3. **Inconsistency**: Config has `PAGINATION_TAG_FETCH_MAX=500` but these use hardcoded 200
4. **No server-side continuation**: If more items are needed, the code breaks out of the loop rather than using continuation tokens

### Recommendation

1. Make the limit configurable via `Settings` (e.g., `SAMPLING_QUERY_MAX_ITEMS`)
2. Document the rationale (RU budget, memory constraints, etc.)
3. Consider using continuation tokens for larger sampling needs
4. Align with `PAGINATION_TAG_FETCH_MAX` or document why they differ

## Recommendations for Spec

### High Priority

1. **Replace ID-only queries with point reads** when partition key is available
   - `assign_to()` queries by ID then patches; if caller provides dataset/bucket, use point read
   - Estimated savings: ~2-5 RU per operation

2. **Make the 200 limit configurable**
   - Add `SAMPLING_QUERY_MAX_ITEMS` to config
   - Document the tradeoff between RU cost and sampling fairness

3. **Add composite indexes** for common query patterns:
   - `(status, assignedTo)` for unassigned queries
   - `(datasetName, status)` for dataset-scoped queries

### Medium Priority

4. **Cache `stats()` results** using Change Feed or time-based invalidation
   - Currently scans entire container for 3 counts
   - Could use materialized counters updated via Change Feed

5. **Cache `list_datasets()` results**
   - Dataset list changes infrequently
   - Use TTL-based cache or invalidate on import

6. **Use continuation tokens** in sampling methods instead of hard caps
   - More robust for larger datasets
   - Better RU efficiency with pagination

### Low Priority

7. **Consider secondary container** for assignment tracking
   - Current cross-partition `list_assigned()` could be single-partition with PK=`userId`
   - Already have `assignments` container but it duplicates data

8. **Monitor RU consumption** per query type
   - Add diagnostics logging for RU charges
   - Identify optimization candidates based on actual usage

## Query Efficiency Summary

| Query Type | Count | Partition Efficiency | Action Needed |
|------------|-------|---------------------|---------------|
| Point reads | 3 | ✅ Single partition | None |
| Single-partition queries | 2 | ✅ Single partition | None |
| Cross-partition with filter | 10 | ⚠️ Partial | Add indexes |
| Full container scans | 4 | ❌ All partitions | Cache or redesign |

## RU Monitoring Status

### Current State

**No RU monitoring implemented.** The codebase does not capture or log Request Unit (RU) consumption from Cosmos DB queries.

The observability implementation ([OBSERVABILITY_IMPLEMENTATION.md](backend/docs/OBSERVABILITY_IMPLEMENTATION.md)) uses OpenTelemetry with Azure Monitor but does not include Cosmos DB RU metrics.

### Recommendation

Add RU logging for expensive operations:

```python
async def _execute_query_with_metrics(
    self, 
    query: str, 
    parameters: list, 
    operation_name: str
) -> tuple[list, float]:
    """Execute query and log RU consumption."""
    items = []
    total_ru = 0.0
    
    iterator = self._gt_container.query_items(
        query=query,
        parameters=parameters,
        enable_scan_in_query=True,
    )
    
    async for item in iterator:
        items.append(item)
    
    # Get RU charge from response headers
    total_ru = getattr(iterator, '_last_response_headers', {}).get(
        'x-ms-request-charge', 0
    )
    
    self._logger.info(
        "cosmos.query.metrics",
        extra={
            "operation": operation_name,
            "ru_charge": total_ru,
            "item_count": len(items),
        }
    )
    
    return items, total_ru
```

## Indexing Policy Analysis

The current indexing policy ([indexing-policy.json](backend/scripts/indexing-policy.json)) includes composite indexes for common sort patterns but lacks optimization for assignment queries:

**Current composite indexes**:
- `reviewedAt` + `id` (both directions)
- `updatedAt` + `id`
- `status` + `reviewedAt` + `id`
- `totalReferences` + `id` (both directions)
- `status` + `totalReferences` + `id`

**Recommended additions**:
```json
[
    {"path": "/status", "order": "ascending"},
    {"path": "/assignedTo", "order": "ascending"}
]
```

This would optimize the `list_unassigned()` and `list_assigned()` queries that filter by status and assignedTo.

## Implementation Priorities

### Phase 1 (SA-248 - Immediate)
1. Remove `min(limit, 200)` cap from sampling methods
2. Add configurable `SAMPLING_QUERY_MAX_ITEMS` setting
3. Use continuation tokens for proper pagination

### Phase 2 (SA-247 - Short-term)
1. Add RU logging for expensive queries
2. Cache `stats()` and `list_datasets()` results
3. Add composite index for `(status, assignedTo)`

### Phase 3 (Future)
1. Consider global secondary index for status-only queries
2. Evaluate Change Feed for materialized views
3. Implement automatic query analysis/alerting

## References

- [Azure Cosmos DB Query Optimization](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-query-container#avoid-cross-partition-queries)
- [Partition Key Design Best Practices](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning-overview)
- [Request Units in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/request-units)
- [Composite Indexes](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy#composite-indexes)
- Codebase: [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py), [config.py](backend/app/core/config.py), [indexing-policy.json](backend/scripts/indexing-policy.json)
