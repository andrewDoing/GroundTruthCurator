# Explorer Sorting System Research

## Context

Research into how the Explorer component implements column sorting, sort state management, visual indicators, and backend integration.

## Sources Consulted

### Codebase

- [frontend/src/components/app/QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx): Main Explorer component with sorting logic
- [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts): API service with sort parameter handling
- [backend/app/domain/enums.py](backend/app/domain/enums.py): `SortField` and `SortOrder` enum definitions
- [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py): API endpoint accepting sort parameters
- [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py): Cosmos DB ORDER BY implementation

---

## 1. Current Column Sorting Implementation

### Frontend Sort State

The Explorer manages sort state with two pieces of React state:

```typescript
type SortColumn = "refs" | "reviewedAt" | "hasAnswer" | null;
type SortDirection = "asc" | "desc";

const [sortColumn, setSortColumn] = useState<SortColumn>(null);
const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
```

### Sort Handler Logic

The `handleSort` function implements a three-state toggle:

1. **First click**: Set column, direction = `desc`
2. **Second click (same column)**: Toggle direction to `asc`
3. **Third click (same column)**: Clear sort (column = `null`, direction = `desc`)

```typescript
const handleSort = (column: "refs" | "reviewedAt" | "hasAnswer") => {
  if (sortColumn === column) {
    if (sortDirection === "desc") {
      setSortDirection("asc");
    } else {
      setSortColumn(null);
      setSortDirection("desc");
    }
  } else {
    setSortColumn(column);
    setSortDirection("desc");
  }
};
```

---

## 2. Available Sorting Options

### Frontend Sortable Columns

| Column | UI Label | API Parameter |
|--------|----------|---------------|
| `refs` | Refs | `totalReferences` |
| `reviewedAt` | Reviewed | `reviewedAt` |
| `hasAnswer` | Answer? | `hasAnswer` |

### Backend SortField Enum

```python
class SortField(str, Enum):
    reviewed_at = "reviewedAt"
    updated_at = "updatedAt"
    id = "id"
    has_answer = "hasAnswer"
    totalReferences = "totalReferences"
```

### Backend SortOrder Enum

```python
class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"
```

### Default Sort

- **Backend default**: `reviewedAt DESC`
- **Frontend default**: No sort applied (column = `null`)

---

## 3. Visual Sort Indicator Implementation

### Indicator Design

Sort indicators use arrow symbols displayed inline with column headers:

- **Descending**: `↓`
- **Ascending**: `↑`

### Two-State Visual System

The Explorer shows two distinct indicator states:

1. **Applied filter (violet)**: Shows the sort currently active in the backend response
2. **Pending filter (amber, 50% opacity)**: Shows a selected but unapplied sort

```tsx
{appliedFilter.sortColumn === "refs" && (
  <span className="text-violet-600">
    {appliedFilter.sortDirection === "desc" ? "↓" : "↑"}
  </span>
)}
{sortColumn === "refs" && sortColumn !== appliedFilter.sortColumn && (
  <span className="text-amber-500 opacity-50">
    {sortDirection === "desc" ? "↓" : "↑"}
  </span>
)}
```

### Known Issue

SA-361 reports that the ascending sort visual indicator does not update correctly for the Answer column. The code structure appears correct, so the bug may be in the conditional rendering logic or state synchronization.

---

## 4. Tag Count as a Sortable Field

### Current Status

**Tag count is NOT currently a sortable field.**

### Backlog Item

SA-684 requests this feature:

> "GTC: Ability to sort by tag number effectively"
>
> As a GTC user, I would like to be able to sort by tags descending to find ground truths that have fewer tags than expected to be able to find items needing review.

### Implementation Requirements

To add tag count sorting:

#### Backend Changes

1. Add `tagCount` to `SortField` enum:
   ```python
   class SortField(str, Enum):
       # existing...
       tag_count = "tagCount"
   ```

2. Add computed field or stored property `tagCount` to documents (similar to `totalReferences` backfill pattern)

3. Add field mapping in `_build_secure_sort_clause`:
   ```python
   secure_field_map = {
       # existing...
       SortField.tag_count: "c.tagCount",
   }
   ```

4. Create backfill script (follow `backfill_total_references.py` pattern)

5. Update Cosmos DB indexing policy to include `tagCount`

#### Frontend Changes

1. Add `"tagCount"` to `SortColumn` type
2. Add sortable column header in table
3. Map frontend column name to API parameter

---

## 5. Sorting Passed to Backend API

### Frontend Service Call

The Explorer builds API parameters from applied filter state:

```typescript
const sortByParam =
  appliedFilter.sortColumn === "refs"
    ? "totalReferences"
    : appliedFilter.sortColumn;

const params = {
  // ...filters
  sortBy: sortByParam,
  sortOrder: sortByParam ? appliedFilter.sortDirection : undefined,
  page: safePage,
  limit: itemsPerPage,
};

listAllGroundTruths(params);
```

### Service Layer

`groundTruths.ts` passes parameters to the generated API client:

```typescript
if (params.sortBy)
  query.sortBy = params.sortBy as components["schemas"]["SortField"];
if (params.sortOrder) query.sortOrder = params.sortOrder;
```

### API Endpoint

`GET /v1/ground-truths` accepts query parameters:

```python
sort_by: SortField = Query(default=SortField.reviewed_at.value, alias="sortBy"),
sort_order: SortOrder = Query(default=SortOrder.desc.value, alias="sortOrder"),
```

### Cosmos DB Query

The repository builds a secure ORDER BY clause:

```python
def _build_secure_sort_clause(self, sort_field: SortField, sort_direction: SortOrder) -> str:
    secure_field_map = {
        SortField.id: "c.id",
        SortField.updated_at: "c.updatedAt",
        SortField.reviewed_at: "c.reviewedAt",
        SortField.has_answer: "c.reviewedAt",
        SortField.totalReferences: "c.totalReferences",
    }
    # ...builds "ORDER BY c.field ASC/DESC"
```

A secondary sort by `c.id ASC` is added for stable pagination when the primary sort field is not `id`.

---

## Key Findings Summary

| Question | Answer |
|----------|--------|
| How is sorting implemented? | React state (`sortColumn`, `sortDirection`) with three-state toggle handler |
| Available sort options? | `refs` (totalReferences), `reviewedAt`, `hasAnswer` |
| Sort direction indicator? | Arrow symbols (↓/↑), violet=applied, amber=pending |
| Is tag count sortable? | No - requested in SA-684, not yet implemented |
| How is sort passed to API? | `sortBy` and `sortOrder` query params to `GET /v1/ground-truths` |

---

## Recommendations

1. **SA-361 bug fix**: Investigate why ascending sort visual for Answer column doesn't update
2. **SA-684 implementation**: Follow `totalReferences` pattern for computed `tagCount` field
3. **Consider**: Adding `updatedAt` as a frontend sortable column (already supported by backend)
