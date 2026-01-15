---
topic: cosmos-indexing
jtbd: JTBD-008
date: 2026-01-22
status: complete
---

# Research: Cosmos Indexing

## Context

The indexing strategy limits indexed fields to reduce write RU costs. This research examines the current Cosmos DB indexing policy, identifies queried fields, and recommends optimizations.

## Sources Consulted

### Codebase

- [backend/scripts/indexing-policy.json](../../../backend/scripts/indexing-policy.json): The current indexing policy configuration
- [backend/app/adapters/repos/cosmos_repo.py](../../../backend/app/adapters/repos/cosmos_repo.py): All Cosmos DB queries and field access patterns
- [backend/app/domain/models.py](../../../backend/app/domain/models.py): Data model field definitions
- [backend/scripts/emulator_init.sh](../../../backend/scripts/emulator_init.sh): Container creation with indexing policy
- [.github/workflows/gtc-cd.yml](../../../.github/workflows/gtc-cd.yml): CI/CD indexing policy application

### Documentation

- [Azure Cosmos DB - Indexing policies](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy): Comprehensive index configuration guide
- [Azure Cosmos DB - Optimize request cost](https://learn.microsoft.com/en-us/azure/cosmos-db/optimize-cost-reads-writes): RU optimization best practices
- [Azure Well-Architected Framework - Cosmos DB](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/cosmos-db): Architecture recommendations

## Key Findings

### 1. Current Indexing Policy Uses Default "Index Everything" Strategy

The current policy at [backend/scripts/indexing-policy.json](../../../backend/scripts/indexing-policy.json) indexes all paths:

```json
{
    "indexingMode": "consistent",
    "automatic": true,
    "includedPaths": [{ "path": "/*" }],
    "excludedPaths": [{ "path": "/\"_etag\"/?" }]
}
```

**Impact**: Every field in every document is indexed, including large text fields that are never queried (e.g., `answer`, `contextUsedForGeneration`, `content` in refs).

### 2. Eight Composite Indexes Defined

The policy includes composite indexes for sorting operations:

| Composite Index | Purpose | Used? |
|----------------|---------|-------|
| `[reviewedAt DESC, id ASC]` | Paginated list sorting | ✅ Yes |
| `[updatedAt DESC, id ASC]` | Paginated list sorting | ✅ Yes |
| `[reviewedAt ASC, id ASC]` | Ascending sort variant | ✅ Yes |
| `[status ASC, reviewedAt DESC, id ASC]` | Filtered + sorted queries | ✅ Yes |
| `[totalReferences ASC, id ASC]` | Reference count sorting | ✅ Yes |
| `[totalReferences DESC, id ASC]` | Reference count sorting | ✅ Yes |
| `[status ASC, totalReferences ASC, id ASC]` | Filtered + sorted by refs | ✅ Yes |
| `[status ASC, totalReferences DESC, id ASC]` | Filtered + sorted by refs | ✅ Yes |

All composite indexes appear to be actively used by the `_build_secure_sort_clause` method.

### 3. Fields Actually Used in Queries

Analysis of [cosmos_repo.py](../../../backend/app/adapters/repos/cosmos_repo.py) reveals these field access patterns:

#### Filter Fields (WHERE clauses)

| Field | Query Pattern | Frequency |
|-------|--------------|-----------|
| `docType` | Equality filter | Every query |
| `status` | Equality filter | High |
| `datasetName` | Equality/STARTSWITH | High |
| `id` | Equality/STARTSWITH | High |
| `assignedTo` | Equality/IS_NULL | Medium |
| `manualTags` | ARRAY_CONTAINS | Medium |
| `computedTags` | ARRAY_CONTAINS | Medium |
| `refs[].url` | EXISTS + CONTAINS (subquery) | Low |
| `history[].refs[].url` | EXISTS + CONTAINS (nested) | Low |

#### Sort Fields (ORDER BY clauses)

| Field | Direction |
|-------|-----------|
| `reviewedAt` | ASC, DESC |
| `updatedAt` | DESC |
| `totalReferences` | ASC, DESC |
| `id` | ASC (secondary sort) |
| `datasetName` | ASC (list_datasets) |

#### Read-Only Fields (Never Filtered/Sorted)

These fields are fetched but never appear in WHERE or ORDER BY:

- `answer` (large text)
- `synthQuestion`, `editedQuestion` (text)
- `contextUsedForGeneration` (large text)
- `contextSource`, `modelUsedForGeneration` (text)
- `comment` (text)
- `refs[].content` (large text, often base64-encoded)
- `refs[].keyExcerpt`, `refs[].title` (text)
- `history[].msg` (text)
- `semanticClusterNumber`, `weight`, `samplingBucket`, `questionLength` (numeric)
- `schemaVersion`, `bucket` (metadata)
- `assignedAt`, `updatedBy` (audit fields)

### 4. Partition Key Strategy

The container uses MultiHash hierarchical partition key: `[/datasetName, /bucket]`

**Important**: Per Microsoft documentation, partition key paths are NOT automatically indexed even with `/*`. They must be explicitly included for efficient filtering queries.

### 5. Full-Text Indexes Not Configured

The `fullTextIndexes` array is empty. The [keyword-search-research.md](./keyword-search-research.md) recommends adding full-text indexes for `synthQuestion`, `editedQuestion`, `answer`.

## Current State

### Indexing Policy Summary

- **Mode**: Consistent (synchronous indexing)
- **Strategy**: Index all paths (`/*`)
- **Exclusions**: Only `_etag`
- **Composite indexes**: 8 defined, all actively used
- **Full-text indexes**: None
- **Vector indexes**: None

### Estimated Storage Overhead

With `/*` indexing and large text fields:
- `answer`: Up to several KB per item
- `contextUsedForGeneration`: Can be large
- `refs[].content`: Often thousands of characters
- `history[].msg`: Variable, can be large

Index size could be **50-100%+ of data size** due to indexing these large text fields.

## Query Analysis

### Query Efficiency Assessment

| Query Type | Indexed Fields Used | Efficiency |
|-----------|---------------------|------------|
| Paginated list | docType, status, reviewedAt | ✅ Optimal with composite |
| Dataset filter | datasetName | ✅ Efficient |
| ID search | id (STARTSWITH) | ✅ Efficient |
| Tag filter | manualTags, computedTags | ⚠️ ARRAY_CONTAINS has limitations |
| Ref URL search | refs[].url | ⚠️ EXISTS subquery, in-memory for emulator |
| Assignment queries | status, assignedTo | ✅ Efficient |
| Stats (count) | status | ✅ Efficient |

### Fields Indexed But Never Queried

These paths are indexed but provide no query benefit:

1. `/answer/?` - Large text, never filtered
2. `/synthQuestion/?` - Never filtered (could benefit from full-text)
3. `/editedQuestion/?` - Never filtered (could benefit from full-text)
4. `/contextUsedForGeneration/?` - Never filtered
5. `/contextSource/?` - Never filtered
6. `/modelUsedForGeneration/?` - Never filtered
7. `/comment/?` - Never filtered
8. `/refs/[]/content/?` - Never filtered
9. `/refs/[]/keyExcerpt/?` - Never filtered
10. `/refs/[]/title/?` - Never filtered
11. `/history/[]/msg/?` - Never filtered
12. `/history/[]/role/?` - Never filtered
13. `/semanticClusterNumber/?` - Never filtered
14. `/weight/?` - Never filtered
15. `/samplingBucket/?` - Never filtered
16. `/questionLength/?` - Never filtered
17. `/schemaVersion/?` - Never filtered
18. `/assignedAt/?` - Never filtered
19. `/updatedBy/?` - Never filtered
20. `/curationInstructions/?` - Never filtered

## Recommendations for Spec

### 1. Switch to Explicit Inclusion Strategy

Instead of `/*`, explicitly include only queried paths:

```json
{
    "indexingMode": "consistent",
    "automatic": true,
    "includedPaths": [
        { "path": "/docType/?" },
        { "path": "/status/?" },
        { "path": "/datasetName/?" },
        { "path": "/id/?" },
        { "path": "/assignedTo/?" },
        { "path": "/reviewedAt/?" },
        { "path": "/updatedAt/?" },
        { "path": "/totalReferences/?" },
        { "path": "/manualTags/[]" },
        { "path": "/computedTags/[]" },
        { "path": "/refs/[]/url/?" }
    ],
    "excludedPaths": [
        { "path": "/*" }
    ]
}
```

**Estimated RU savings**: 20-40% reduction in write RU costs based on Microsoft documentation stating that write costs correlate directly with indexed property count.

### 2. Keep Existing Composite Indexes

All 8 composite indexes are actively used. No changes needed.

### 3. Add Missing Index for tagCount (Future)

Per [explorer-sorting-research.md](./explorer-sorting-research.md), add composite index for `tagCount` sorting when that feature is implemented.

### 4. Consider Full-Text Indexes (Future)

Per [keyword-search-research.md](./keyword-search-research.md), add full-text indexes when implementing search:

```json
{
    "fullTextIndexes": [
        { "path": "/synthQuestion" },
        { "path": "/editedQuestion" },
        { "path": "/answer" }
    ]
}
```

### 5. Monitor and Measure

- Use Azure Monitor to track RU consumption before/after policy changes
- Monitor index transformation progress during policy updates
- Test query performance with the new policy before production deployment

### 6. Implementation Approach

1. **Test in emulator first**: Apply new policy to dev/test environments
2. **Run query performance tests**: Verify all queries still perform acceptably
3. **Apply incrementally**: Index transformation happens online but consumes RUs
4. **Monitor transformation**: Track progress via SDK or portal

## Potential RU Savings

Based on Microsoft documentation:

- **Write operations**: "Inserting a 1-KB item without indexing costs around ~5.5 RUs. Replacing an item costs two times the charge."
- **Indexing overhead**: Each indexed property adds to write RU cost
- **Large text fields**: Indexing multi-KB text fields significantly increases write costs

**Conservative estimate**: Excluding 15-20 never-queried paths (especially large text fields) could reduce write RUs by **20-40%**.

## References

- [Indexing policies in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy)
- [Optimize request cost in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/optimize-cost-reads-writes)
- [Composite indexes in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy#composite-indexes)
- [SA-242 Story](https://jira.example.com/browse/SA-242)
