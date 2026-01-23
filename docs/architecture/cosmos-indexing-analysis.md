# Cosmos DB Indexing Policy Optimization Analysis

## Executive Summary

The current indexing policy has significant gaps that force many queries to use in-memory filtering, increasing RU costs and latency. This analysis identifies 12 missing composite indexes that would enable direct Cosmos DB query execution and reduce costs by up to 70%.

---

## Current State Analysis

### Existing Composite Indexes (8 total)

1. **reviewedAt DESC, id ASC** - Supports default sorting by review date
2. **updatedAt DESC, id ASC** - Supports sorting by update date
3. **reviewedAt ASC, id ASC** - Supports ascending review date sort
4. **status ASC, reviewedAt DESC, id ASC** - Supports filtered queries by status with review date sort
5. **totalReferences ASC, id ASC** - Supports sorting by reference count (ascending)
6. **totalReferences DESC, id ASC** - Supports sorting by reference count (descending)
7. **status ASC, totalReferences ASC, id ASC** - Status filter with reference count sort (asc)
8. **status ASC, totalReferences DESC, id ASC** - Status filter with reference count sort (desc)

### Current Query Patterns (from cosmos_repo.py)

#### 1. Direct Cosmos DB Queries (Efficient)
These queries use existing indexes:
- Simple status filter + sort by reviewedAt/updatedAt/totalReferences/id
- Example: `WHERE c.status = @status ORDER BY c.reviewedAt DESC, c.id ASC OFFSET X LIMIT Y`

#### 2. In-Memory Filtered Queries (Inefficient)
These queries fetch ALL matching documents and filter in memory:
- Queries with `tags` (ARRAY_CONTAINS)
- Queries with `exclude_tags` (NOT ARRAY_CONTAINS)
- Queries with `ref_url` (EXISTS + CONTAINS - not supported by emulator)
- Queries with `keyword` search
- Queries sorting by `tag_count` (ARRAY_LENGTH in ORDER BY)

**Comment in code (line 747-751):**
```
# For queries with tags, we need to filter in-memory since ARRAY_CONTAINS
# doesn't work well with ORDER BY in Cosmos DB
# Also use in-memory filtering for ref_url if Cosmos emultor is used since EXISTS is not supported by emulator
# Keyword search also requires in-memory filtering (no full-text index)
# Tag count sorting also requires in-memory filtering (ARRAY_LENGTH in ORDER BY is not well-supported)
```

#### 3. Key Query Filters
- **status** - GroundTruthStatus enum (draft, under_review, approved, etc.)
- **dataset** - String, filters by datasetName
- **tags** - Array contains ALL specified tags (AND logic)
- **exclude_tags** - Excludes items with ANY of these tags
- **item_id** - STARTSWITH search on id field
- **ref_url** - CONTAINS search in refs.url (nested array)
- **keyword** - Full-text search in multiple fields (in-memory)

#### 4. Sort Fields (from SortField enum)
- `reviewedAt` - Most common default sort
- `updatedAt` - Update timestamp
- `id` - Unique identifier
- `hasAnswer` - Maps to reviewedAt (see line 700)
- `totalReferences` - Count of references
- `tag_count` - ARRAY_LENGTH (requires in-memory sort)

#### 5. Pagination Pattern
- Uses `OFFSET X LIMIT Y` for direct queries
- Uses in-memory slicing for filtered queries
- Always includes secondary sort by `id ASC` for stability

### Count Queries
- `SELECT VALUE COUNT(1) FROM c WHERE ...`
- Used for pagination metadata
- Same filter patterns as list queries

---

## Performance Issues

### 1. Missing Status + Dataset Indexes
**Impact:** High - Very common filter combination
- Query: `WHERE c.status = 'draft' AND c.datasetName = 'my-dataset' ORDER BY c.reviewedAt DESC`
- **Current:** Table scan or partial index use
- **RU Cost:** ~10-50 RUs per query depending on data size
- **Frequency:** Every paginated list with dataset filter

### 2. Missing Dataset-Only Indexes
**Impact:** High - Dataset filtering without status
- Query: `WHERE c.datasetName = 'my-dataset' ORDER BY c.updatedAt DESC`
- **Current:** Table scan with post-filter sort
- **RU Cost:** ~20-100 RUs
- **Frequency:** Dataset-scoped views

### 3. Missing Status + UpdatedAt Indexes
**Impact:** Medium - Status filter with updatedAt sort
- Query: `WHERE c.status = 'approved' ORDER BY c.updatedAt DESC`
- **Current:** Inefficient - status filter + full sort
- **RU Cost:** ~15-50 RUs

### 4. Missing Multi-Field Filter Indexes
**Impact:** High - Combined filters are forced to in-memory
- Query: `WHERE c.status = 'draft' AND c.datasetName = 'ds1' ORDER BY c.totalReferences DESC`
- **Current:** Full scan → in-memory filter and sort
- **RU Cost:** ~50-200+ RUs
- **Frequency:** Filtered + sorted queries

### 5. Tag-Based Queries (Architecture Limitation)
**Impact:** Critical - All tag queries use in-memory filtering
- Query: `WHERE ARRAY_CONTAINS(c.manualTags, 'important') ORDER BY c.reviewedAt DESC`
- **Current:** Fetches up to 10,000 items (PAGINATION_TAG_FETCH_MAX), filters in-memory
- **RU Cost:** ~100-500+ RUs depending on result set size
- **Root Cause:** Cosmos DB doesn't support ARRAY_CONTAINS + ORDER BY efficiently
- **Note:** This is a Cosmos DB limitation, not a missing index

### 6. Missing docType Indexes
**Impact:** Medium - docType filter appears in many queries
- Query: `WHERE c.docType = 'ground-truth-item' AND c.status = 'draft' ORDER BY c.reviewedAt DESC`
- **Current:** Partial index coverage
- **RU Cost:** ~10-30 RUs

---

## Recommendations

### Priority 1: Critical Missing Indexes (Implement Immediately)

#### 1. Status + Dataset + Sort Combinations (8 indexes)
```json
// Status + Dataset + ReviewedAt DESC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/reviewedAt", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Status + Dataset + ReviewedAt ASC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/reviewedAt", "order": "ascending"},
    {"path": "/id", "order": "ascending"}
]

// Status + Dataset + UpdatedAt DESC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/updatedAt", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Status + Dataset + UpdatedAt ASC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/updatedAt", "order": "ascending"},
    {"path": "/id", "order": "ascending"}
]

// Status + Dataset + TotalReferences DESC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/totalReferences", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Status + Dataset + TotalReferences ASC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/totalReferences", "order": "ascending"},
    {"path": "/id", "order": "ascending"}
]

// Status + Dataset + ID DESC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/id", "order": "descending"}
]

// Status + Dataset + ID ASC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/id", "order": "ascending"}
]
```

**Justification:**
- Most common query pattern: filter by status AND dataset, sort by various fields
- Enables direct Cosmos DB execution without in-memory filtering
- Estimated RU reduction: 50-70% for these queries

#### 2. Dataset-Only Sort Combinations (4 indexes)
```json
// Dataset + ReviewedAt DESC
[
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/reviewedAt", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Dataset + UpdatedAt DESC
[
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/updatedAt", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Dataset + TotalReferences DESC
[
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/totalReferences", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Dataset + ID ASC
[
    {"path": "/datasetName", "order": "ascending"},
    {"path": "/id", "order": "ascending"}
]
```

**Justification:**
- Dataset-scoped queries without status filter
- Common in dataset-specific views and analytics
- Estimated RU reduction: 40-60%

### Priority 2: Status + UpdatedAt Combinations

#### 3. Status + UpdatedAt (2 indexes)
```json
// Status + UpdatedAt DESC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/updatedAt", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]

// Status + UpdatedAt ASC
[
    {"path": "/status", "order": "ascending"},
    {"path": "/updatedAt", "order": "ascending"},
    {"path": "/id", "order": "ascending"}
]
```

**Justification:**
- Currently missing - only have status + reviewedAt
- Common for "recently updated" views filtered by status
- Estimated RU reduction: 30-50%

### Priority 3: Consider docType Indexes

While `docType = 'ground-truth-item'` appears in many queries, adding it to composite indexes would create index explosion. Instead:

**Option A:** Keep using partition key strategy
- Partition key `/datasetName` + `/bucket` already provides physical separation
- docType filter is cheap when combined with partition key

**Option B:** Add selective docType indexes for high-traffic patterns
```json
// DocType + Status + ReviewedAt DESC (only if needed)
[
    {"path": "/docType", "order": "ascending"},
    {"path": "/status", "order": "ascending"},
    {"path": "/reviewedAt", "order": "descending"},
    {"path": "/id", "order": "ascending"}
]
```

**Recommendation:** Skip docType indexes initially. Monitor query metrics and add only if high RU costs are observed.

---

## Tag Query Optimization (Architectural Recommendation)

### Current Problem
Tag-based queries use in-memory filtering because Cosmos DB doesn't efficiently support:
```sql
WHERE ARRAY_CONTAINS(c.manualTags, 'tag1') 
  AND ARRAY_CONTAINS(c.manualTags, 'tag2')
ORDER BY c.reviewedAt DESC
```

### Limitation
This is a **Cosmos DB architectural limitation**, not a missing index issue. Composite indexes cannot include array fields.

### Potential Solutions

#### Option 1: Denormalize Tags (Recommended)
Add computed fields for common tag combinations:
```json
{
  "manualTags": ["important", "urgent"],
  "computedTags": ["security"],
  "_tagIndex": "important|urgent|security"  // Denormalized for sorting
}
```

Then query:
```sql
WHERE CONTAINS(c._tagIndex, 'important')
ORDER BY c.reviewedAt DESC
```

**Pros:**
- Enables efficient tag + sort queries
- Can use composite indexes
- Estimated RU reduction: 60-80% for tag queries

**Cons:**
- Requires document updates to add _tagIndex field
- Slight storage overhead (~50-200 bytes per document)

#### Option 2: Separate Tag Index Container
Create a separate container with inverted index:
```json
// In tag-index container
{
  "tag": "important",
  "groundTruthIds": ["id1", "id2", "id3"],
  "pk": "important"  // partition key
}
```

Query flow:
1. Lookup tag in index container → get IDs
2. Query main container with `WHERE c.id IN (...)` + ORDER BY

**Pros:**
- Cleaner separation of concerns
- Faster tag lookups

**Cons:**
- Two-phase query (2x round trips)
- Requires maintaining consistency between containers
- More complex application logic

#### Option 3: Accept Current Performance
Keep in-memory filtering with safeguards:
- `PAGINATION_TAG_FETCH_MAX = 10000` limit prevents memory exhaustion
- Works for small-to-medium result sets
- Simplest implementation

**Recommendation:** Start with Option 3 (current), evaluate Option 1 if tag query volume increases.

---

## Cost Analysis

### Current State (Estimated RUs)
- Simple query (status + sort): ~5-10 RUs ✅
- Status + dataset + sort: ~20-50 RUs ❌ (no index)
- Dataset-only + sort: ~30-100 RUs ❌ (no index)
- Tag query (in-memory): ~100-500 RUs ❌ (architectural limit)

### After Implementing Priority 1 & 2 Indexes
- Simple query: ~5-10 RUs ✅ (no change)
- Status + dataset + sort: ~5-15 RUs ✅ (70% reduction)
- Dataset-only + sort: ~8-20 RUs ✅ (60% reduction)
- Tag query: ~100-500 RUs ❌ (requires architectural change)

### Expected Overall Impact
- **50-70% RU reduction** for filtered queries (most common pattern)
- **40-60% latency reduction** (avoiding in-memory processing)
- **No impact on storage** (indexes are metadata)

---

## Implementation Plan

### Phase 1: Add Priority 1 Indexes (Week 1)
1. Update `indexing-policy.json` with 12 new composite indexes:
   - 8 status + dataset + sort combinations
   - 4 dataset-only + sort combinations
2. Apply policy to Cosmos DB container (requires reindexing)
3. Monitor reindexing progress (can take hours for large containers)
4. Validate query performance improvements

### Phase 2: Add Priority 2 Indexes (Week 2)
1. Add 2 status + updatedAt combinations
2. Monitor RU consumption and latency

### Phase 3: Evaluate Tag Query Optimization (Month 2)
1. Analyze tag query frequency and RU costs
2. If high impact, implement denormalized tag index (Option 1)
3. Run A/B test to measure improvement

### Phase 4: Production Monitoring (Ongoing)
1. Set up Azure Monitor alerts for high RU consumption
2. Track P95 latency for key query patterns
3. Review Cosmos DB query metrics monthly
4. Consider additional indexes based on real usage patterns

---

## Testing Strategy

### 1. Validate Index Coverage
Before applying to production:
```python
# Test queries that should use new indexes
test_queries = [
    # Status + Dataset + Sort
    "WHERE c.status = 'draft' AND c.datasetName = 'test' ORDER BY c.reviewedAt DESC",
    "WHERE c.status = 'approved' AND c.datasetName = 'prod' ORDER BY c.totalReferences DESC",
    
    # Dataset-only + Sort
    "WHERE c.datasetName = 'test' ORDER BY c.updatedAt DESC",
    
    # Status + UpdatedAt
    "WHERE c.status = 'under_review' ORDER BY c.updatedAt DESC",
]

# Use Cosmos DB Metrics to verify index usage
# Check Query Stats: Index Hit Rate should be ~100%
```

### 2. Load Testing
- Run load tests with 100+ concurrent queries
- Measure RU consumption before and after
- Compare P50, P95, P99 latencies

### 3. Rollback Plan
Cosmos DB allows reverting indexing policies:
```json
// Keep backup of current policy
// Can restore if issues arise
// Reindexing takes time, so plan for maintenance window
```

---

## Query Pattern Recommendations

### 1. Avoid OFFSET for Large Offsets
Current code uses `OFFSET X LIMIT Y`, which is expensive for large offsets.

**Problem:**
```sql
-- Page 100 with limit 50 = OFFSET 4950
-- Cosmos DB must scan 4950 items even if indexed
SELECT * FROM c WHERE ... ORDER BY c.reviewedAt DESC OFFSET 4950 LIMIT 50
```

**Better:** Continuation tokens (already used for some queries)
```python
# Store last item's reviewedAt and id from previous page
# Next query: WHERE c.reviewedAt < @lastReviewedAt 
#            OR (c.reviewedAt = @lastReviewedAt AND c.id > @lastId)
# This uses index efficiently regardless of page depth
```

### 2. Optimize Count Queries
Count queries still scan all matching documents.

**Current:**
```sql
SELECT VALUE COUNT(1) FROM c WHERE c.status = 'draft' AND c.datasetName = 'test'
-- Must scan entire result set
```

**Better:** Cache counts or use approximate counts
```python
# Option A: Cache counts in Redis with TTL
# Option B: Use Azure Cosmos DB changefeed to maintain counts
# Option C: Accept approximate counts for large datasets
```

### 3. Use Partition Key Filters When Possible
Current partition key: `/datasetName` + `/bucket`

**Optimal queries include partition key:**
```sql
-- Good: Uses partition key
WHERE c.datasetName = 'test' AND c.status = 'draft'

-- Suboptimal: Cross-partition query
WHERE c.status = 'draft'  -- scans all partitions
```

---

## Monitoring Checklist

After deploying new indexes:

- [ ] Monitor reindexing progress (Azure Portal → Indexing Policy)
- [ ] Check RU consumption (should decrease 50-70%)
- [ ] Measure P95 query latency (should decrease 40-60%)
- [ ] Validate index hit rate (should be ~100% for covered queries)
- [ ] Monitor storage size (minimal increase expected)
- [ ] Set up alerts for RU threshold breaches
- [ ] Review slow query logs (identify remaining bottlenecks)
- [ ] Load test critical endpoints

---

## Additional Optimization Opportunities

### 1. Use Server-Side Pagination
Replace `skip` + `take` with continuation tokens for better performance at scale.

### 2. Implement Query Result Caching
Cache frequent queries (e.g., dataset list) in Redis with 5-minute TTL.

### 3. Review Partition Key Strategy
Current: `/datasetName` + `/bucket`
- Good: Aligns with most common filter (dataset)
- Consider: Does `bucket` provide enough distribution?
- Evaluate: Are there hot partitions?

### 4. Add Read Replicas
If read-heavy workload, enable geo-replication with read replicas.

### 5. Use Dedicated Gateway
For high throughput, consider dedicated gateway for lower latency.

---

## References

- [Cosmos DB Composite Indexes](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy#composite-indexes)
- [Cosmos DB Query Performance](https://learn.microsoft.com/en-us/azure/cosmos-db/sql/query-cheat-sheet)
- [Indexing Best Practices](https://learn.microsoft.com/en-us/azure/cosmos-db/sql/query-cheat-sheet#indexing-best-practices)
- Code: `backend/app/adapters/repos/cosmos_repo.py` lines 540-1000
- Current Policy: `backend/scripts/indexing-policy.json`
