---
title: Query Optimization
description: The query optimization effort replaces expensive cross-partition queries with efficient patterns
jtbd: JTBD-008
stories: [SA-247, SA-248]
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Query Optimization

## Overview

Replace expensive Cosmos DB cross-partition queries with efficient patterns and remove arbitrary limits to improve GTC performance and reduce Request Unit (RU) consumption.

## Problem Statement

The GTC backend uses Cosmos DB with a MultiHash hierarchical partition key on `[/datasetName, /bucket]`. Several queries bypass this partitioning strategy, resulting in:

1. **Cross-partition query fan-out**: 16+ queries use `enable_scan_in_query=True`, scanning all physical partitions
2. **Hardcoded 200-item limits**: Arbitrary caps on unassigned item sampling prevent fair distribution across datasets
3. **No RU monitoring**: Query costs are invisible, making optimization difficult
4. **Missing composite indexes**: Common filter patterns lack supporting indexes

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-1 | Remove hardcoded 200-item limit from sampling queries | High | `list_unassigned()`, `_query_unassigned_by_selector()`, and `_query_unassigned_global_excluding_user()` use configurable limit |
| FR-2 | Add configurable `SAMPLING_QUERY_MAX_ITEMS` setting | High | Setting documented in config, default value justified |
| FR-3 | Use continuation tokens for sampling methods | High | Methods support pagination beyond single query batch |
| FR-4 | Convert ID-only queries to point reads when partition key available | Medium | `assign_to()` uses `read_item()` when caller provides dataset/bucket |
| FR-5 | Add caching for `stats()` results | Medium | Stats cached with TTL-based or Change Feed invalidation |
| FR-6 | Add caching for `list_datasets()` results | Medium | Dataset list cached with TTL-based invalidation |
| FR-7 | Add composite index for `(status, assignedTo)` | Medium | Index deployed via [indexing-policy.json](../backend/scripts/indexing-policy.json) |

### Non-Functional Requirements

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| NFR-1 | Reduce RU consumption for point-read conversions | ~2-5 RU savings per operation | RU logging comparison |
| NFR-2 | Maintain query latency under load | P95 < 100ms for single-partition queries | OpenTelemetry metrics |
| NFR-3 | Add RU observability for expensive queries | 100% of cross-partition queries logged | Log audit |
| NFR-4 | Zero breaking changes to API contracts | No API changes | Test suite passes |

## Technical Considerations

### Expensive Queries Identified

| Query Location | Pattern | Issue | Fix |
|----------------|---------|-------|-----|
| [cosmos_repo.py:525](../backend/app/adapters/repos/cosmos_repo.py#L525) | `list_all_gt()` - `SELECT * FROM c` | Full container scan | Add pagination, batch processing |
| [cosmos_repo.py:1350](../backend/app/adapters/repos/cosmos_repo.py#L1350) | `stats()` - `SELECT c.status FROM c` | Full container scan for counts | Cache results, consider Change Feed |
| [cosmos_repo.py:1375](../backend/app/adapters/repos/cosmos_repo.py#L1375) | `list_datasets()` - `SELECT DISTINCT VALUE c.datasetName` | Full container scan | Cache results |
| [cosmos_repo.py:1404](../backend/app/adapters/repos/cosmos_repo.py#L1404) | `list_unassigned()` - status filter | Cross-partition, capped at 200 | Composite index, remove cap |
| [cosmos_repo.py:1742](../backend/app/adapters/repos/cosmos_repo.py#L1742) | `assign_to()` - `SELECT TOP 1 ... WHERE c.id = @id` | Cross-partition lookup by ID | Point read if PK known |
| [cosmos_repo.py:1896](../backend/app/adapters/repos/cosmos_repo.py#L1896) | `list_assigned()` - filter by `assignedTo` | Cross-partition by user | Composite index |
| [cosmos_repo.py:944](../backend/app/adapters/repos/cosmos_repo.py#L944) | `_get_filtered_count` - `SELECT VALUE COUNT(1)` | Cross-partition aggregation | Cache or Change Feed |

### 200-Item Limit Analysis (SA-248)

**Root Cause**: Hardcoded `min(limit, 200)` in three sampling methods:

- [cosmos_repo.py:1405](../backend/app/adapters/repos/cosmos_repo.py#L1405): `list_unassigned()`
- [cosmos_repo.py:1623](../backend/app/adapters/repos/cosmos_repo.py#L1623): `_query_unassigned_by_selector()`
- [cosmos_repo.py:1678](../backend/app/adapters/repos/cosmos_repo.py#L1678): `_query_unassigned_global_excluding_user()`

**Impact**:

- Prevents fair sampling across datasets of varying sizes
- Undocumented constraint confuses maintainers
- Inconsistent with `PAGINATION_TAG_FETCH_MAX=500` in config
- No continuation token usage—loop breaks instead of paginating

**Recommended Fix**:

1. Add `SAMPLING_QUERY_MAX_ITEMS` to `Settings` class in [config.py](../backend/app/core/config.py)
2. Replace `min(limit, 200)` with `min(limit, settings.sampling_query_max_items)`
3. Document rationale: RU budget, memory constraints, sampling fairness tradeoffs
4. Implement continuation token support for larger sampling needs

### Point Read Opportunities

Point reads cost ~1 RU per KB versus 3-10+ RU for queries.

| Current Pattern | Location | Optimization |
|-----------------|----------|--------------|
| Query by ID for assignment | Line 1742 | Use `read_item()` if `datasetName` and `bucket` available |

**Already Optimized** (no changes needed):

- `get_gt()` (line 1058): Uses `read_item()` with full partition key
- `get_curation_instructions()` (line 1086): Uses `read_item()`
- Tags repo (line 121): Uses `read_item()`

### Cross-Partition Query Mitigation

**Strategies for queries that must remain cross-partition:**

1. **Composite indexes**: Add `(status, assignedTo)` to support unassigned and assigned queries
2. **Caching**: Time-based or Change Feed invalidation for infrequently changing data
3. **Pagination**: Use continuation tokens instead of arbitrary caps
4. **Batch processing**: Process large scans in chunks with back-pressure

**Recommended composite index addition** to [indexing-policy.json](../backend/scripts/indexing-policy.json):

```json
[
    {"path": "/status", "order": "ascending"},
    {"path": "/assignedTo", "order": "ascending"}
]
```

### RU Monitoring

**Current State**: No RU monitoring implemented. The observability stack uses OpenTelemetry with Azure Monitor but lacks Cosmos DB RU metrics.

**Recommended Implementation**:

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

### Query Efficiency Summary

| Query Type | Count | Partition Efficiency | Action |
|------------|-------|---------------------|--------|
| Point reads | 3 | ✅ Single partition | None |
| Single-partition queries | 2 | ✅ Single partition | None |
| Cross-partition with filter | 10 | ⚠️ Partial | Add indexes |
| Full container scans | 4 | ❌ All partitions | Cache or redesign |

## Implementation Phases

### Phase 1: SA-248 - Remove Arbitrary Limits (Immediate)

1. Remove `min(limit, 200)` cap from sampling methods
2. Add configurable `SAMPLING_QUERY_MAX_ITEMS` setting with documented default
3. Implement continuation token support for proper pagination

### Phase 2: SA-247 - Query Optimization (Short-term)

1. Add RU logging for expensive queries
2. Implement caching for `stats()` and `list_datasets()`
3. Deploy composite index for `(status, assignedTo)`
4. Convert `assign_to()` to point read when partition key available

### Phase 3: Future Enhancements

1. Evaluate global secondary index for status-only queries
2. Implement Change Feed for materialized views
3. Add automatic query analysis and RU alerting

## Open Questions

1. **Default value for `SAMPLING_QUERY_MAX_ITEMS`**: Should it align with `PAGINATION_TAG_FETCH_MAX` (500) or have a separate justification?
2. **Cache TTL for stats**: What invalidation strategy balances accuracy vs. RU savings?
3. **Point read adoption**: Should `assign_to()` require partition key from callers, or fall back to query?

## References

- [Azure Cosmos DB Query Optimization](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-query-container#avoid-cross-partition-queries)
- [Partition Key Design Best Practices](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning-overview)
- [Request Units in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/request-units)
- [Composite Indexes](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy#composite-indexes)
- [Optimize Request Cost](https://learn.microsoft.com/en-us/azure/cosmos-db/optimize-cost-reads-writes)
- Research: [query-optimization-research.md](../.copilot-tracking/subagent/20260122/query-optimization-research.md)
- Codebase: [cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py), [config.py](../backend/app/core/config.py), [indexing-policy.json](../backend/scripts/indexing-policy.json)
