---
title: Tag Filtering
description: Enhanced tag filtering with tri-state selection (include/exclude/neutral) and advanced boolean query input for flexible item discovery.
jtbd: JTBD-002
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-363
---

## Overview

The Explorer tag filter enables users to narrow down ground truth items by tags. This specification extends the current include-only filtering to support tri-state selection (include, exclude, neutral) and advanced boolean query expressions.

Parent JTBD: Help users find and filter ground truth items

## Problem Statement

The current tag filter supports only include operations with AND logic. Users cannot exclude items with specific tags, limiting filter expressiveness. Teams working with large datasets need to filter out irrelevant items (for example, excluding `frequency:rare` while including `difficulty:hard`) and combine conditions with boolean logic.

Current limitations:

* Binary state only: tags are either selected (include) or unselected (neutral)
* No exclusion capability to filter out items with unwanted tags
* No support for OR logic or complex boolean expressions
* Advanced users cannot express queries like `has A AND (has B OR has C) AND NOT has D`

## Requirements

### Functional Requirements

| ID     | Requirement                                                      | Priority | Acceptance Criteria                                                                         |
| ------ | ---------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------ |
| FR-001 | Support tri-state tag selection: include, exclude, neutral       | Must     | Each tag can be in one of three states; UI reflects current state visually                  |
| FR-002 | Toggle between states with sequential clicks                     | Must     | Click 1: neutral → include; Click 2: include → exclude; Click 3: exclude → neutral          |
| FR-003 | Display visual indicator for excluded tags                       | Must     | Excluded tags show an X indicator distinguishing them from included tags                    |
| FR-004 | Combine multiple included tags with AND logic                    | Must     | Items must have ALL included tags to appear in results                                      |
| FR-005 | Apply excluded tags with NOT logic                               | Must     | Items with ANY excluded tag are filtered out                                                |
| FR-006 | Support advanced tag-query input with boolean operators          | Should   | Text input accepts AND, OR, NOT, and parentheses for complex expressions                    |
| FR-007 | Validate tag-query expressions before applying                   | Must     | Invalid expressions show clear validation error; Explorer table remains functional          |
| FR-008 | Search both manual and computed tags                             | Must     | Include and exclude operations apply across `manualTags` and `computedTags` fields          |
| FR-009 | Persist tag filter state in URL                                  | Should   | Refreshing the page restores the current tag filter configuration                           |
| FR-010 | Provide clear all action for tag filters                         | Must     | Single action resets all tag states to neutral                                              |

### Non-Functional Requirements

| ID      | Category      | Requirement                                              | Target     |
| ------- | ------------- | ------------------------------------------------------- | ---------- |
| NFR-001 | Usability     | Exclusion is discoverable without documentation          | 3 clicks   |
| NFR-002 | Performance   | Tag filter application completes within latency budget   | < 500ms    |
| NFR-003 | Accessibility | Tri-state selection is keyboard accessible               | WCAG 2.1   |
| NFR-004 | Testability   | Core filter logic is testable without Cosmos emulator    | Unit tests |

## User Stories

### US-001: SME excludes items with a specific tag

As a user, I want to exclude items tagged with a certain value, so that I can focus on the subset that matters for my task.

Acceptance criteria:

1. Given I am viewing the Explorer with tag filters
2. When I click a tag twice (include → exclude)
3. Then items with that tag are hidden from results
4. And the tag shows an X indicator

### US-002: SME combines include and exclude filters

As a user, I want to include some tags and exclude others simultaneously, so that I can express complex filter criteria.

Acceptance criteria:

1. Given I select `difficulty:hard` as include and `frequency:rare` as exclude
2. When the filter applies
3. Then only items with `difficulty:hard` AND without `frequency:rare` appear

### US-003: Power user enters a boolean query

As a power user, I want to type a boolean expression for tag filtering, so that I can express OR conditions and nested logic.

Acceptance criteria:

1. Given I open the advanced query input
2. When I enter `has A AND (has B OR has C)`
3. Then items matching the expression appear in results

### US-004: User sees validation error for invalid query

As a user, I want clear feedback when my query is invalid, so that I can correct it without breaking the Explorer.

Acceptance criteria:

1. Given I enter an invalid expression (for example, `has A AND AND B`)
2. When I attempt to apply it
3. Then a validation error message appears
4. And the Explorer table continues to show previous results

## Technical Considerations

### Frontend State Structure

Change from simple string array to structured filter state:

```typescript
// Current
const [selectedTags, setSelectedTags] = useState<string[]>([]);

// Proposed
interface TagFilterState {
  include: string[];
  exclude: string[];
}
const [tagFilter, setTagFilter] = useState<TagFilterState>({ include: [], exclude: [] });
```

### Toggle Pattern

Implement three-click cycle:

```typescript
const handleTagToggle = (tag: string) => {
  if (tagFilter.include.includes(tag)) {
    // Include → Exclude
    setTagFilter(prev => ({
      include: prev.include.filter(t => t !== tag),
      exclude: [...prev.exclude, tag]
    }));
  } else if (tagFilter.exclude.includes(tag)) {
    // Exclude → Neutral
    setTagFilter(prev => ({
      ...prev,
      exclude: prev.exclude.filter(t => t !== tag)
    }));
  } else {
    // Neutral → Include
    setTagFilter(prev => ({
      ...prev,
      include: [...prev.include, tag]
    }));
  }
};
```

### API Parameter Format

Option A (recommended): Separate query parameters

```
GET /ground-truths?tags=tag1,tag2&excludeTags=tag3,tag4
```

Option B: Prefixed syntax

```
GET /ground-truths?tags=+tag1,+tag2,-tag3,-tag4
```

### Backend Query Changes

Add `excludeTags` parameter and update Cosmos query builder:

```python
@router.get("")
async def list_all_ground_truths(
    tags: str | None = Query(default=None),
    exclude_tags: str | None = Query(default=None, alias="excludeTags"),
):
    # ...

def _build_query_filter(self, tags: list[str] | None, exclude_tags: list[str] | None):
    # Include tags (AND)
    for idx, tag in enumerate(tags or []):
        pname = f"@tag{idx}"
        clauses.append(
            f"(ARRAY_CONTAINS(c.manualTags, {pname}) OR ARRAY_CONTAINS(c.computedTags, {pname}))"
        )

    # Exclude tags (NOT)
    for idx, tag in enumerate(exclude_tags or []):
        pname = f"@excludeTag{idx}"
        clauses.append(
            f"NOT (ARRAY_CONTAINS(c.manualTags, {pname}) OR ARRAY_CONTAINS(c.computedTags, {pname}))"
        )
```

### Advanced Boolean Query Parser

For FR-006, implement a query DSL supporting:

* Operators: `AND`, `OR`, `NOT`
* Grouping: parentheses for precedence
* Tag references: `has tagname` or quoted `has "tag:value"`

Example expressions:

```
has frequency:common AND NOT has difficulty:easy
has A AND (has B OR has C)
NOT has draft
```

### Emulator Limitations

The Cosmos DB emulator does not support `ARRAY_CONTAINS()`. This affects testing:

* Unit tests for query building logic can run without emulator
* Integration tests for tag filtering require real Cosmos DB
* Consider mocking the query layer for frontend integration tests
* Document which test suites require production Cosmos connection

## Implementation Phases

### Phase 1: Tri-State UI

* Update `selectedTags` to `TagFilterState` structure
* Implement three-click toggle pattern
* Add visual indicators (checkmark for include, X for exclude)
* Update URL serialization for filter state

### Phase 2: Backend Exclude Support

* Add `excludeTags` query parameter to list endpoint
* Update `_build_query_filter()` with NOT clauses
* Add validation for exclude tag limits
* Write integration tests (requires real Cosmos DB)

### Phase 3: Boolean Query Input

* Add text input component for advanced queries
* Implement expression parser with validation
* Translate parsed expressions to API parameters or Cosmos query
* Display validation errors inline

## Open Questions

| Q  | Question                                                                        | Owner | Status |
| -- | ------------------------------------------------------------------------------ | ----- | ------ |
| Q1 | Should URL encoding use separate params or prefixed syntax?                     | Team  | Open   |
| Q2 | How should emulator limitations be handled in CI pipelines?                     | Team  | Open   |
| Q3 | Should boolean query input replace or complement the chip selection UI?         | Team  | Open   |
| Q4 | What error message format for invalid boolean expressions?                      | Team  | Open   |

## References

* SA-363
* [Research file](../.copilot-tracking/subagent/20260122/tag-filtering-research.md)
* [Cosmos emulator limitations](../backend/docs/cosmos-emulator-limitations.md)
