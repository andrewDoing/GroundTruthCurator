---
title: Explorer Sorting Enhancements
description: Add tag count sorting capability and fix ascending sort visual indicator bug.
jtbd: JTBD-002
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-684
  - SA-361
---

## Overview

The Explorer should support sorting items by total tag count and correctly display ascending sort visual indicators.

Parent JTBD: Help users find and filter ground truth items

## Problem Statement

Users cannot sort ground truth items by tag count, making it difficult to identify items with unusually low or high tag counts that may need review. Additionally, the ascending sort visual indicator does not update correctly for the Answer column (SA-361), causing confusion about the active sort state.

## Requirements

### Functional Requirements

| ID     | Requirement                                                              | Priority | Acceptance Criteria                                                                      |
| ------ | ------------------------------------------------------------------------ | -------- | --------------------------------------------------------------------------------------- |
| FR-001 | Add tag count as a sortable column in the Explorer                       | Must     | Users can click the Tags column header to sort by total tag count                        |
| FR-002 | Tag count sorting follows the three-state toggle pattern                 | Must     | First click: descending; second click: ascending; third click: clear sort               |
| FR-003 | Tag count includes both manual and computed tags                         | Must     | The `tagCount` field represents the unified total of all tags on an item                |
| FR-004 | Display visual sort indicator for tag count column                       | Must     | Arrow indicator (↓/↑) displays with violet=applied, amber=pending states               |
| FR-005 | Fix ascending sort indicator for Answer column                           | Must     | Clicking twice on Answer column displays the ascending arrow (↑) correctly              |
| FR-006 | Descending tag count sort lists low-count items last                     | Should   | Sorting descending by tag count places items with fewer tags at the bottom              |

### Non-Functional Requirements

| ID      | Category    | Requirement                                         | Target                                     |
| ------- | ----------- | --------------------------------------------------- | ------------------------------------------ |
| NFR-001 | Performance | Tag count sorting does not degrade query latency    | Latency within 10% of existing sort fields |
| NFR-002 | Data        | Existing items have `tagCount` field populated      | 100% via backfill script                   |
| NFR-003 | Consistency | Tag count updates when tags are added or removed    | Real-time on write operations              |

## User Stories

### US-001: Sort by tag count to find under-tagged items

As a GTC user, I want to sort items by tag count descending, so that I can find ground truths with fewer tags than expected and prioritize them for review.

Acceptance criteria:

1. Given I am viewing the Explorer
2. When I click the Tags column header
3. Then items sort by total tag count descending
4. And items with the fewest tags appear at the bottom

### US-002: Ascending sort indicator displays correctly

As a user, I want the ascending sort arrow to display when I toggle to ascending sort, so that I can confirm which direction is active.

Acceptance criteria:

1. Given I have clicked a sortable column once (descending)
2. When I click the same column again
3. Then the indicator changes from ↓ to ↑
4. And the indicator displays in the correct color state (violet=applied, amber=pending)

## Technical Considerations

### Backend Changes

Follow the `totalReferences` implementation pattern:

1. Add `tagCount` to `SortField` enum in [backend/app/domain/enums.py](../backend/app/domain/enums.py):

   ```python
   class SortField(str, Enum):
       # existing fields...
       tag_count = "tagCount"
   ```

2. Add field mapping in `_build_secure_sort_clause` in [backend/app/adapters/repos/cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py):

   ```python
   secure_field_map = {
       # existing mappings...
       SortField.tag_count: "c.tagCount",
   }
   ```

3. Ensure `tagCount` field is computed and stored on ground truth documents during write operations.

4. Update Cosmos DB indexing policy to include `tagCount` for efficient sorting.

### Backfill Requirement

Create a backfill script following the pattern in [backend/scripts/backfill_total_references.py](../backend/scripts/backfill_total_references.py):

* Calculate `tagCount` as the sum of manual tags and computed tags for each item.
* Update all existing documents with the computed value.
* Log progress and handle errors gracefully.

### Frontend Changes

1. Add `"tagCount"` to the `SortColumn` type in [frontend/src/components/app/QuestionsExplorer.tsx](../frontend/src/components/app/QuestionsExplorer.tsx).

2. Add a sortable Tags column header with click handler.

3. Map frontend column name `"tagCount"` to API parameter `"tagCount"`.

4. Ensure visual indicator logic applies to the new column.

### SA-361 Bug Fix

Investigate the ascending sort indicator issue for the Answer column in [frontend/src/components/app/QuestionsExplorer.tsx](../frontend/src/components/app/QuestionsExplorer.tsx). The bug may be in:

* Conditional rendering logic for the indicator.
* State synchronization between `sortDirection` and `appliedFilter.sortDirection`.
* The specific conditional check for `hasAnswer` column.

## Open Questions

| Q  | Question                                                                 | Owner | Status |
| -- | ------------------------------------------------------------------------ | ----- | ------ |
| Q1 | Should tag count display as a visible column value or only be sortable?  | Team  | Open   |
| Q2 | How should items with zero tags sort relative to items with null tags?   | Team  | Open   |

## References

* SA-684: GTC: Ability to sort by tag number effectively
* SA-361: Ascending sort visual indicator bug for Answer column
* [Research file](../.copilot-tracking/subagent/20260122/explorer-sorting-research.md)
