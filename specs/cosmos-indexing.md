---
title: Cosmos Indexing Optimization
description: The indexing strategy limits indexed fields to reduce write RU costs
jtbd: JTBD-008
stories: [SA-242]
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Cosmos Indexing Optimization

## Overview

Optimize Cosmos DB indexing policy to reduce write RU costs by excluding large text fields that are never queried, directly supporting JTBD-008 (Help optimize GTC performance and Cosmos usage).

## Problem Statement

The current indexing policy uses the default "index everything" strategy (`/*`), which indexes every field in every document. This includes large text fields like `answer`, `contextUsedForGeneration`, and `refs[].content` that are never used in WHERE clauses or ORDER BY expressions. Indexing these fields unnecessarily increases:

- Write RU costs (each indexed property adds to write overhead)
- Index storage consumption (estimated 50-100%+ of data size)
- Background indexing work during writes

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-01 | Switch from wildcard inclusion to explicit field inclusion | Must | Indexing policy uses `excludedPaths: [/*]` with explicit `includedPaths` |
| FR-02 | Index all fields used in WHERE clauses | Must | All filter queries perform without cross-partition scans |
| FR-03 | Index all fields used in ORDER BY clauses | Must | All sort queries use indexes, no in-memory sorts |
| FR-04 | Retain existing composite indexes | Must | All 8 composite indexes preserved unchanged |
| FR-05 | Exclude large text fields from indexing | Must | `answer`, `contextUsedForGeneration`, `refs[].content` not indexed |

### Non-Functional Requirements

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| NFR-01 | Reduce write RU consumption | 20-40% reduction | Azure Monitor RU metrics before/after |
| NFR-02 | Maintain query performance | No regression | Query latency P50/P95 unchanged |
| NFR-03 | Index transformation completion | < 24 hours | Monitor transformation progress via SDK |
| NFR-04 | Zero downtime during migration | 100% availability | Online index transformation |

## Technical Considerations

### Current State

The indexing policy at [backend/scripts/indexing-policy.json](../backend/scripts/indexing-policy.json) indexes all paths:

```json
{
    "indexingMode": "consistent",
    "automatic": true,
    "includedPaths": [{ "path": "/*" }],
    "excludedPaths": [{ "path": "/\"_etag\"/?" }]
}
```

Eight composite indexes are defined and actively used for sorted queries.

### Target State

Switch to explicit field inclusion with wildcard exclusion:

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

Composite indexes remain unchanged.

### Fields to Index

These fields are actively used in queries and must be indexed:

| Field | Query Pattern | Priority |
|-------|--------------|----------|
| `docType` | Equality filter (every query) | Critical |
| `status` | Equality filter | Critical |
| `datasetName` | Equality/STARTSWITH | Critical |
| `id` | Equality/STARTSWITH | Critical |
| `assignedTo` | Equality/IS_NULL | High |
| `reviewedAt` | ORDER BY, composite indexes | Critical |
| `updatedAt` | ORDER BY, composite indexes | Critical |
| `totalReferences` | ORDER BY, composite indexes | High |
| `manualTags` | ARRAY_CONTAINS | Medium |
| `computedTags` | ARRAY_CONTAINS | Medium |
| `refs[].url` | EXISTS + CONTAINS | Medium |

### Fields to Exclude

These fields are never queried and should not be indexed:

| Field | Reason | Size Impact |
|-------|--------|-------------|
| `answer` | Large text, read-only | High |
| `contextUsedForGeneration` | Large text, read-only | High |
| `refs[].content` | Large text (often base64), read-only | High |
| `synthQuestion` | Text, never filtered | Medium |
| `editedQuestion` | Text, never filtered | Medium |
| `contextSource` | Text, never filtered | Low |
| `modelUsedForGeneration` | Text, never filtered | Low |
| `comment` | Text, never filtered | Low |
| `refs[].keyExcerpt` | Text, never filtered | Medium |
| `refs[].title` | Text, never filtered | Low |
| `history[].msg` | Text, never filtered | Medium |
| `history[].role` | Text, never filtered | Low |
| `semanticClusterNumber` | Numeric, never filtered | Low |
| `weight` | Numeric, never filtered | Low |
| `samplingBucket` | Numeric, never filtered | Low |
| `questionLength` | Numeric, never filtered | Low |
| `schemaVersion` | Metadata, never filtered | Low |
| `assignedAt` | Audit field, never filtered | Low |
| `updatedBy` | Audit field, never filtered | Low |
| `curationInstructions` | Text, never filtered | Low |

### Migration Strategy

1. **Test in emulator**: Apply the new policy to dev environments first
2. **Run query regression tests**: Verify all existing queries perform correctly
3. **Measure baseline RUs**: Record current write RU consumption in production
4. **Apply policy update**: Index transformation happens online (no downtime)
5. **Monitor transformation**: Track progress via Azure portal or SDK
6. **Validate post-migration**: Compare RU metrics and query latency

**Note**: Index transformation consumes background RUs. Schedule during low-traffic periods if possible.

## Open Questions

| ID | Question | Impact | Resolution Path |
|----|----------|--------|-----------------|
| OQ-01 | Should `bucket` field be indexed for partition key efficiency? | Query performance | Test with/without explicit inclusion |
| OQ-02 | When will full-text indexes be needed for keyword search? | Future scope | Depends on keyword-search spec timeline |
| OQ-03 | What is acceptable transformation duration for production? | Operations | Align with ops team on maintenance window |

## References

- [Indexing policies in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy)
- [Optimize request cost in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/optimize-cost-reads-writes)
- [Composite indexes in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy#composite-indexes)
- [Research: Cosmos Indexing](../.copilot-tracking/subagent/20260122/cosmos-indexing-research.md)
