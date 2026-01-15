# Implementation Plan: Item ID Filter for Ground Truths Explorer

## Overview
Add a simple text input field to the Ground Truths Explorer that allows users to search for specific ground truth items by their ID. The filter will perform backend filtering by passing the itemId parameter to the API endpoint. This integrates with the existing filter system and Apply Filters workflow.

## What We Need (Right Now Only)
- Text input field for Item ID with clear button
- State management for the ID filter value
- Pass itemId parameter to backend API via query string
- Integration with existing Apply Filters button workflow
- Update filter state interface to include itemId

## Files to Change

### 1. `src/components/app/QuestionsExplorer.tsx` (MODIFY)
Add Item ID filter UI and state management.

**Functions:**
- No new functions needed - use existing state setters and handlers
- Update `FilterState` interface to include `itemId: string`
- Update `handleApplyFilters()` to include itemId in the applied filter state
- Update `hasUnappliedChanges` useMemo to include itemId comparison

**New state:**
- `const [itemIdFilter, setItemIdFilter] = useState<string>("")`

**UI Changes:**
- Add text input after Dataset selector
- Label: "Item ID:"
- Placeholder: "Enter item ID to search..."
- Show clear button when itemIdFilter has text

### 2. `src/services/groundTruths.ts` (MODIFY)
Add itemId parameter to API call.

**Interface changes:**
- `ListAllGroundTruthsParams` - add `itemId?: string | null`

**Functions:**
- `listAllGroundTruths()` - pass itemId to backend query parameters
  - Add condition: `if (params.itemId) query.itemId = params.itemId;`
  - Backend will handle the filtering and return only matching items
  - Pagination will correctly reflect filtered item counts

### 3. `src/api/generated.ts` (INFO ONLY - auto-generated)
Backend will add `itemId?: string | null` to the query parameters for `list_all_ground_truths_v1_ground_truths_get` operation. After backend changes, run `npm run api:types` to regenerate this file.

## Implementation Details

### Component State Flow
```
User types in text input
  ↓
setItemIdFilter("item-123")
  ↓
User clicks "Apply Filters"
  ↓
handleApplyFilters() updates appliedFilter with itemId: "item-123"
  ↓
useEffect triggers API call with new appliedFilter
  ↓
Backend receives itemId query parameter
  ↓
Backend filters and returns only matching items
  ↓
Filtered items displayed in table with correct pagination
```

### API Query Parameters
```typescript
// In listAllGroundTruths:
const params = {
  status: appliedFilter.status !== "all" ? appliedFilter.status : undefined,
  dataset: appliedFilter.dataset !== "all" ? appliedFilter.dataset : undefined,
  tags: appliedFilter.tags.length > 0 ? appliedFilter.tags : undefined,
  itemId: appliedFilter.itemId || undefined,  // NEW
  sortBy: sortByParam,
  sortOrder: sortByParam ? appliedFilter.sortDirection : undefined,
  page: safePage,
  limit: itemsPerPage,
};
```

### Backend API Call
```
GET /v1/ground-truths?itemId=item-123&status=draft&page=1&limit=25
```

### UI Layout
Position the Item ID filter between Dataset selector and Status filters:
```
Dataset: [dropdown]
Item ID: [text input] [Clear button if text exists]
Status: [All] [Draft] [Approved] [Skipped] [Deleted]
```

## Constraints and Assumptions
- Backend will implement itemId as a query parameter
- Backend will handle partial/exact matching logic
- Backend will handle case-sensitivity (recommend case-insensitive)
- Pagination counts will reflect filtered results from backend
- Filter applies on "Apply Filters" click, not real-time
- Clear button only clears the input, user must click Apply to see effect
- Empty itemId string means no ID filtering applied

## Out of Scope
- Real-time filtering as user types
- Regex or advanced search patterns on frontend
- Separate "exact match" vs "partial match" toggle in UI
- Debouncing or throttling
- Auto-focus on input field
- Keyboard shortcuts for ID search

## Backend Requirements
Backend must implement the following for GET `/v1/ground-truths`:

**Query Parameter:**
- `itemId: Optional[str]` - if provided, filter items by ID
- Recommended: case-insensitive partial match using SQL `ILIKE` or equivalent
- Recommended: trim whitespace from itemId before filtering

**Example Backend Logic:**
```python
if item_id:
    query = query.filter(GroundTruth.id.ilike(f"%{item_id.strip()}%"))
```

**OpenAPI Schema Update:**
Add to `list_all_ground_truths` operation parameters:
```yaml
- name: itemId
  in: query
  required: false
  schema:
    type: string
    nullable: true
```

## Testing Strategy

### Frontend Manual Tests
- **Type ID and apply** - enter full item ID, click Apply, verify item appears
- **Partial match** - enter partial ID like "item-", verify all matching items shown
- **Case insensitive** - enter "ABC", verify matches "abc", "ABC", "AbC" (if backend supports)
- **Clear button** - enter text, click Clear, verify input empties (need Apply to reset table)
- **Combined filters** - use Item ID with status/dataset/tags, verify all filters work together
- **No matches** - enter non-existent ID, verify empty table with appropriate message
- **Empty input** - leave empty and apply, verify shows all items (no filtering)
- **Pagination** - search for item, verify pagination shows correct total count

### Backend Integration Tests
- **Backend returns filtered items** - verify API call includes itemId parameter
- **Pagination counts match** - verify total count reflects filtered results
- **Combined filters** - verify itemId works with status, dataset, tags filters
- **Whitespace handling** - verify leading/trailing spaces don't break search

### Edge Cases
- Very long ID strings (shouldn't break API or UI)
- Special characters in ID (-, _, numbers)
- Whitespace handling (leading/trailing spaces)
- Filter persists when switching between pages
- Unapplied changes indicator shows when ID changes
- Empty string vs null vs undefined handling

## Acceptance Criteria
- ✅ Text input visible in filter section
- ✅ Clear button appears when text entered
- ✅ Filter integrates with "Apply Filters" button
- ✅ itemId parameter sent to backend API
- ✅ Backend filtering works (partial match, case-insensitive)
- ✅ Combined with other filters (status, dataset, tags)
- ✅ Empty input shows all results
- ✅ No errors when special characters entered
- ✅ Unapplied changes detection includes itemId
- ✅ Pagination counts reflect filtered results
- ✅ Results persist across page navigation

## Implementation Order
1. Backend implements itemId query parameter support
2. Run `npm run api:types` to regenerate TypeScript types
3. Update `ListAllGroundTruthsParams` interface in services
4. Update `listAllGroundTruths()` to pass itemId to query
5. Add UI state and input field in QuestionsExplorer
6. Update filter state management logic
7. Test combined filters and pagination
8. Verify unapplied changes detection

## Notes
- Backend should implement case-insensitive partial matching for best UX
- Consider trimming whitespace on backend to avoid user confusion
- Frontend will send whatever user types; backend handles validation
- No client-side validation needed (backend will return empty array if invalid)
- This approach scales well with large datasets (filtering happens in database)
