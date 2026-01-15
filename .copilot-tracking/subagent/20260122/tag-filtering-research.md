# Research: Tag Filtering System

**Topic:** tag-filtering  
**Date:** 2026-01-22  
**Status:** Complete

## Summary

The tag filtering system in Ground Truth Curator allows users to filter items by tags in the Explorer view. Currently, the system supports **include-only** filtering with AND logic. A planned enhancement (SA-363) will add tri-state selection (include/exclude/neutral) and boolean logic for advanced filtering.

## Key Findings

### 1. Current Explorer Tag Filter UI

**Location:** [frontend/src/components/app/QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx)

The Explorer component maintains tag filter state:

```typescript
// Filter state (unapplied)
const [selectedTags, setSelectedTags] = useState<string[]>([]);

// Applied filter state
const [appliedFilter, setAppliedFilter] = useState<FilterState>({
  status: "all",
  dataset: "all",
  tags: [],
  // ...
});
```

**Current UI behavior:**
- Tags are displayed in a collapsible section "Filter by Tags"
- Manual tags and computed tags are shown separately (manual in violet, computed in slate with lock icon)
- Clicking a tag toggles it between selected (include) and unselected (neutral)
- Selected tags show a badge count and "Clear all" option
- Multiple selected tags use **AND logic** ("items must have ALL selected tags")
- Tags fetched via `fetchTagsWithComputed()` which returns `{ manualTags: string[], computedTags: string[] }`

### 2. Tag State Management

**Tag toggle function:**
```typescript
const handleTagToggle = (tag: string) => {
  setSelectedTags((prev) =>
    prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
  );
};
```

**Current limitation:** Binary state only (selected vs unselected) - no exclusion state.

### 3. Tag-Related Fields on Ground Truth Items

**Location:** [backend/app/domain/models.py](backend/app/domain/models.py#L76-L86)

```python
class GroundTruthItem(BaseModel):
    # Tag fields: manualTags are user-provided, computedTags are system-generated
    manual_tags: list[str] = Field(default_factory=list, alias="manualTags")
    computed_tags: list[str] = Field(default_factory=list, alias="computedTags")

    @computed_field
    @property
    def tags(self) -> list[str]:
        """Return a merged, sorted view of manual and computed tags."""
        merged = set(self.manual_tags or []) | set(self.computed_tags or [])
        return sorted(merged)
```

**Key points:**
- `manualTags`: User-applied tags (editable)
- `computedTags`: System-generated tags from plugins (read-only)
- `tags`: Computed property merging both (for backward compatibility)

### 4. Backend API Tag Filtering

**Location:** [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L162-L230)

The `list_all_ground_truths` endpoint accepts tags as a comma-separated string:

```python
@router.get("", response_model=GroundTruthListResponse)
async def list_all_ground_truths(
    tags: str | None = Query(default=None),
    # ...
):
    # Tag validation
    MAX_TAGS_PER_QUERY = 10
    MAX_TAG_LENGTH = 100
    
    if tags is not None:
        raw_tags = [tag.strip() for tag in tags.split(",")]
        cleaned = [tag for tag in raw_tags if tag]
        # Validation checks...
        tag_list = cleaned if cleaned else None
```

**Frontend sends tags:**
```typescript
// In groundTruths.ts
if (params.tags?.length) query.tags = params.tags.join(",");
```

### 5. Cosmos DB Query for Tag Filtering

**Location:** [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L562-L571)

```python
def _build_query_filter(self, ..., tags: list[str] | None, ...):
    if include_tags and tags:
        normalized = [tag for tag in (tag.strip() for tag in tags) if tag]
        for idx, tag in enumerate(normalized):
            pname = f"@tag{idx}"
            # Search across manualTags and computedTags
            clauses.append(
                f"(ARRAY_CONTAINS(c.manualTags, {pname}) OR "
                f"ARRAY_CONTAINS(c.computedTags, {pname}))"
            )
            params.append({"name": pname, "value": tag})
```

**Current query pattern:**
- Each tag becomes an AND clause
- Searches both `manualTags` and `computedTags` arrays
- Uses `ARRAY_CONTAINS()` function (not supported in Cosmos Emulator)

### 6. Emulator Limitation

**Location:** [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md)

> `ARRAY_CONTAINS SQL Function Not Supported` - Tag filtering tests must be skipped on emulator and run against real Cosmos DB.

## Current Filter Capabilities

| Capability | Status | Notes |
|------------|--------|-------|
| Include tags (AND) | ✅ Supported | Items must have ALL selected tags |
| Exclude tags (NOT) | ❌ Not supported | Planned in SA-363 |
| OR logic | ❌ Not supported | Planned in SA-363 |
| Boolean expressions | ❌ Not supported | Planned in SA-363 |
| Manual tags | ✅ Supported | Violet styling in UI |
| Computed tags | ✅ Supported | Slate styling with lock icon |

## Patterns Supporting Tri-State Selection (SA-363)

### Frontend Changes Needed

1. **State structure change:**
```typescript
// Current: string[] (selected tags)
// Proposed: Map<string, 'include' | 'exclude'> or similar
interface TagFilterState {
  include: string[];
  exclude: string[];
}
```

2. **UI toggle pattern:**
- Click 1: Neutral → Include (checkmark)
- Click 2: Include → Exclude (X indicator)
- Click 3: Exclude → Neutral (cleared)

3. **Query parameter format:**
```typescript
// Option A: Separate params
tags=tag1,tag2&excludeTags=tag3,tag4

// Option B: Prefixed syntax
tags=+tag1,+tag2,-tag3,-tag4
```

### Backend Changes Needed

1. **API parameter changes:**
```python
@router.get("")
async def list_all_ground_truths(
    tags: str | None = Query(default=None),  # Include tags
    exclude_tags: str | None = Query(default=None, alias="excludeTags"),  # New
):
```

2. **Cosmos query for exclusion:**
```python
# NOT ARRAY_CONTAINS pattern
for idx, tag in enumerate(excluded_tags):
    pname = f"@excludeTag{idx}"
    clauses.append(
        f"NOT (ARRAY_CONTAINS(c.manualTags, {pname}) OR "
        f"ARRAY_CONTAINS(c.computedTags, {pname}))"
    )
```

### Advanced Boolean Logic (SA-363)

The PRD specifies support for:
```
has frequency:common AND NOT(has difficulty:easy)
```

This would require:
1. A query DSL parser on the backend
2. Translation to Cosmos SQL WHERE clauses
3. Frontend text input with validation

## Recommendations for Implementation

1. **Phase 1: Tri-state UI**
   - Update `selectedTags` to `tagFilters: Map<string, 'include' | 'exclude'>`
   - Add visual indicators for include/exclude states
   - Implement three-click toggle pattern

2. **Phase 2: Backend exclude support**
   - Add `excludeTags` query parameter
   - Update `_build_query_filter()` with NOT clauses
   - Add integration tests (requires real Cosmos DB)

3. **Phase 3: Boolean query input (optional)**
   - Add text input for advanced queries
   - Implement parser with AND/OR/NOT/parentheses
   - Add validation and error display

## Related Files

| File | Purpose |
|------|---------|
| [frontend/src/components/app/QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx) | Explorer UI with tag filter |
| [frontend/src/services/tags.ts](frontend/src/services/tags.ts) | Tag fetching and validation |
| [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts) | API calls with tag params |
| [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py) | List endpoint with tag filtering |
| [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py) | Cosmos queries with ARRAY_CONTAINS |
| [backend/app/domain/models.py](backend/app/domain/models.py) | GroundTruthItem with tag fields |
| [prd-refined-2.json](prd-refined-2.json) | SA-363 requirements for tri-state |

## Open Questions

1. Should the URL encoding for tag filters use separate params or a prefix syntax?
2. How to handle emulator limitations for exclude queries in development?
3. Should the boolean query input be a separate mode or integrated with chip selection?
