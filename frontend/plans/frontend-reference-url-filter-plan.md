# Frontend Reference URL Filter Plan

## Overview

Add a reference URL filter to the QuestionsExplorer component that allows users to filter ground truth items by reference URLs. The filter will be placed horizontally on the same row as the Item ID search field and will leverage the backend's `refUrl` query parameter to filter items that contain references (at item level or turn level) matching the provided URL substring.

## Files to Modify

### 1. `src/components/app/QuestionsExplorer.tsx`
- Add state variable for reference URL filter
- Add handler function for reference URL filter changes
- Update UI to add reference URL input field on same row as Item ID search
- Pass `refUrl` parameter to `listAllGroundTruths` API call
- Update filter sync logic to include reference URL filter

### 2. `src/services/groundTruths.ts`
- Update `listAllGroundTruths` function signature to accept optional `refUrl` parameter
- Pass `refUrl` parameter to backend API call

## Detailed Implementation

### Step 1: Update `groundTruths.ts` Service

**File:** `src/services/groundTruths.ts`

Add `refUrl` parameter to the `listAllGroundTruths` function:

```typescript
export async function listAllGroundTruths(
  status?: string | null,
  dataset?: string | null,
  tags?: string | null,
  itemId?: string | null,
  refUrl?: string | null,  // NEW PARAMETER
  sortBy: string = "updatedAt",
  sortOrder: string = "desc",
  page: number = 1,
  limit: number = 50
): Promise<GroundTruthListResponse> {
  const params = new URLSearchParams();
  
  if (status) params.append("status", status);
  if (dataset) params.append("dataset", dataset);
  if (tags) params.append("tags", tags);
  if (itemId) params.append("itemId", itemId);
  if (refUrl) params.append("refUrl", refUrl);  // NEW PARAMETER
  params.append("sortBy", sortBy);
  params.append("sortOrder", sortOrder);
  params.append("page", page.toString());
  params.append("limit", limit.toString());

  // ... rest of function
}
```

### Step 2: Update `QuestionsExplorer.tsx` Component

**File:** `src/components/app/QuestionsExplorer.tsx`

#### 2.1 Add State Variable

Add state for reference URL filter (around line 70, near other filter state):

```typescript
const [referenceUrlFilter, setReferenceUrlFilter] = useState<string>("");
```

#### 2.2 Add Handler Function

Add handler for reference URL filter changes (around line 140, near other handlers):

```typescript
const handleReferenceUrlChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  const value = e.target.value;
  setReferenceUrlFilter(value);
  setCurrentPage(1); // Reset to first page when filter changes
}, []);
```

#### 2.3 Update fetchItems Function

Update the `fetchItems` function to pass `refUrl` parameter (around line 180):

```typescript
const fetchItems = useCallback(async () => {
  try {
    setLoading(true);
    setError(null);
    
    const response = await listAllGroundTruths(
      selectedStatus,
      selectedDataset,
      selectedTags.join(",") || null,
      itemIdFilter || null,
      referenceUrlFilter || null,  // NEW PARAMETER
      sortField,
      sortOrder,
      currentPage,
      itemsPerPage
    );
    
    // ... rest of function
  } catch (err) {
    // ... error handling
  }
}, [
  selectedStatus,
  selectedDataset,
  selectedTags,
  itemIdFilter,
  referenceUrlFilter,  // NEW DEPENDENCY
  sortField,
  sortOrder,
  currentPage,
  itemsPerPage,
]);
```

#### 2.4 Update URL Sync Logic

Update the effect that syncs filters with URL parameters (around line 110):

```typescript
useEffect(() => {
  const params = new URLSearchParams(location.search);
  
  // ... existing filter syncs
  
  const refUrlParam = params.get("refUrl");
  if (refUrlParam !== null) {
    setReferenceUrlFilter(refUrlParam);
  }
}, [location.search]);
```

Update the effect that syncs filters to URL (around line 130):

```typescript
useEffect(() => {
  const params = new URLSearchParams();
  
  // ... existing filter params
  
  if (referenceUrlFilter) {
    params.set("refUrl", referenceUrlFilter);
  }
  
  // ... rest of URL update logic
}, [
  selectedStatus,
  selectedDataset,
  selectedTags,
  itemIdFilter,
  referenceUrlFilter,  // NEW DEPENDENCY
  sortField,
  sortOrder,
  currentPage,
]);
```

#### 2.5 Update UI Layout

Update the filters section to add reference URL input on the same row as Item ID search (around line 640):

```tsx
{/* Filter Controls - Horizontal Layout */}
<div className="bg-white p-4 border-b border-gray-200">
  <div className="flex flex-wrap gap-4 items-end">
    {/* Item ID Search */}
    <div className="flex-1 min-w-[200px]">
      <label
        htmlFor="item-id-filter"
        className="block text-sm font-medium text-gray-700 mb-1"
      >
        Item ID
      </label>
      <input
        id="item-id-filter"
        type="text"
        value={itemIdFilter}
        onChange={handleItemIdChange}
        placeholder="Filter by item ID..."
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
      />
    </div>

    {/* Reference URL Filter - NEW */}
    <div className="flex-1 min-w-[200px]">
      <label
        htmlFor="reference-url-filter"
        className="block text-sm font-medium text-gray-700 mb-1"
      >
        Reference URL
      </label>
      <input
        id="reference-url-filter"
        type="text"
        value={referenceUrlFilter}
        onChange={handleReferenceUrlChange}
        placeholder="Filter by reference URL..."
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
        title="Filter items that contain references (item-level or turn-level) matching this URL substring"
      />
    </div>

    {/* Other existing filters (Status, Dataset, Tags) */}
    {/* ... */}
  </div>
</div>
```

## Testing Strategy

### Unit Tests

1. **Service Layer Test** (`src/services/groundTruths.test.ts`):
   - Test that `refUrl` parameter is correctly passed to API call
   - Test that `refUrl` is properly encoded in query string

2. **Component Test** (`tests/unit/components/app/QuestionsExplorer.test.tsx`):
   - Test that reference URL filter state updates correctly
   - Test that filter resets to page 1 when changed
   - Test that `fetchItems` is called with correct `refUrl` parameter
   - Test URL sync for reference URL filter

### E2E Tests

1. **Filter Interaction Test** (`tests/e2e/queue-and-editor.spec.ts`):
   - Enter a reference URL in filter input
   - Verify table shows only items with matching references
   - Verify URL parameters are updated
   - Clear filter and verify all items return
   - Test combined filters (e.g., status + reference URL)

2. **URL Persistence Test** (`tests/e2e/queue-and-editor.spec.ts`):
   - Apply reference URL filter
   - Refresh page
   - Verify filter is restored from URL
   - Verify filtered results are maintained

3. **Multi-turn Reference Test** (`tests/e2e/references-search-and-selected.spec.ts`):
   - Filter by a URL that only appears in turn-level references
   - Verify items with turn-level references are included
   - Filter by a URL that appears at item level
   - Verify items with item-level references are included

## Key Design Decisions

1. **Backend Integration**: Use backend's `refUrl` query parameter instead of client-side filtering to ensure:
   - Consistent filtering logic between frontend and backend
   - Better performance for large datasets
   - Accurate pagination with filtered results

2. **Filter Placement**: Place reference URL filter horizontally on same row as Item ID to:
   - Maintain consistent visual hierarchy
   - Save vertical space
   - Group similar text-based filters together

3. **URL Synchronization**: Sync reference URL filter with URL query parameters to:
   - Enable bookmark-able filtered views
   - Support browser back/forward navigation
   - Maintain filter state across page refreshes

4. **Case Sensitivity**: Use case-sensitive substring matching (as implemented by backend) to:
   - Provide precise filtering
   - Match exact URL patterns
   - Align with backend behavior

5. **Multi-level Reference Support**: Backend handles filtering across both item-level and turn-level references, so frontend only needs to pass the filter value without special handling.

## Implementation Notes

- The backend's `refUrl` parameter performs case-sensitive substring matching on reference URLs at both item level and history/turn level
- The filter input provides a tooltip explaining the filtering behavior
- The filter automatically resets pagination to page 1 when changed
- The filter is debounced by user interaction (no automatic debouncing needed as it triggers on blur/enter)
- Empty filter value means no filtering (shows all items)
- The filter works in combination with other filters (status, dataset, tags, itemId)
