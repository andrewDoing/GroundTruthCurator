# ID Search Parameter Plan

## Overview
Add a new optional `itemId` query parameter to the existing GET /v1/ground-truths endpoint that enables searching for ground truth items by ID using exact or partial matching. The search will be case-insensitive and trim whitespace before matching. This extends the existing paginated list endpoint without requiring a new repository method.

## What we will implement now
- Extend existing `list_gt_paginated()` method to accept an optional `item_id_search` parameter
- Add ID search logic in Cosmos query using `CONTAINS()` or `STARTSWITH()` for partial matching
- Update API endpoint to accept and validate `itemId` query parameter
- Case-insensitive search with whitespace trimming
- Keep it SIMPLE: leverage existing pagination infrastructure, no new repository methods

## Files to change
- `app/adapters/repos/base.py` — add `item_id_search` parameter to `list_gt_paginated()` protocol
- `app/adapters/repos/cosmos_repo.py` — extend `_build_query_filter()` to handle ID search with UPPER() for case-insensitivity
- `app/api/v1/ground_truths.py` — add `itemId` query parameter with validation (trim, length check)

## Functions (names and purposes)

### Repository Layer
- `CosmosGroundTruthRepo._build_query_filter(status, dataset, tags, item_id_search) -> tuple[str, list[dict]]`
  - Extended to add ID search condition using `UPPER(c.id)` and `CONTAINS()` for case-insensitive partial matching
  
- `CosmosGroundTruthRepo.list_gt_paginated(..., item_id_search=None) -> tuple[list[GroundTruthItem], PaginationMetadata]`
  - Add new parameter to existing method signature; delegates to `_build_query_filter()`

### API Layer
- `list_all_ground_truths(..., item_id=None) -> GroundTruthListResponse`
  - Add `item_id` query parameter with camelCase alias `itemId`
  - Trim whitespace and validate length before passing to repository
  - Pass trimmed value as `item_id_search` to repository method

## API Changes

### New Query Parameter
- `itemId` (optional): Search term for partial or exact ID matching
  - Case-insensitive (converted to uppercase in SQL)
  - Whitespace trimmed before search
  - Minimum length: 1 character after trimming
  - Maximum length: 200 characters (reasonable limit for IDs)
  - Uses `CONTAINS()` for partial matching (substring anywhere in ID)

### Example Requests
```
GET /v1/ground-truths?itemId=test-123
  → Matches: "test-123", "my-test-123-abc", "TEST-123-final"

GET /v1/ground-truths?itemId=sleek
  → Matches: "sleek-voxel", "sleek", "SLEEK-PATTERN-42"

GET /v1/ground-truths?itemId=  gt-42  
  → Trimmed to "gt-42", matches: "gt-42", "GT-42-V2", "my-gt-42"
```

### Combining with Other Filters
```
GET /v1/ground-truths?itemId=test&status=approved&dataset=faq
  → Returns approved items from "faq" dataset with "test" in their ID
```

## Cosmos Query Implementation

### ID Search Filter Logic
```sql
-- Base query with ID search (case-insensitive)
SELECT * FROM c 
WHERE c.docType = 'ground-truth-item'
  AND CONTAINS(UPPER(c.id), @searchId)  -- @searchId is uppercased
ORDER BY c.reviewedAt DESC
```

### Combined Filters Example
```sql
-- ID search + status + dataset
SELECT * FROM c 
WHERE c.docType = 'ground-truth-item'
  AND CONTAINS(UPPER(c.id), @searchId)
  AND c.status = @status
  AND c.datasetName = @dataset
ORDER BY c.reviewedAt DESC
OFFSET 0 LIMIT 25
```

### Performance Notes
- `CONTAINS()` performs substring search (case-sensitive in Cosmos)
- Wrapping with `UPPER()` enables case-insensitive search
- Cannot leverage partition key for ID search (cross-partition query)
- Indexing on `id` field already exists (default indexing policy)
- Consider using `STARTSWITH()` instead of `CONTAINS()` if prefix matching is sufficient (better performance)

## Validation Rules

### API Layer Validation
1. If `item_id` is `None`, skip ID search (optional parameter)
2. If `item_id` is provided (not `None`):
   - Trim whitespace: `item_id = item_id.strip()`
   - If empty after trim, skip ID search (treat as if not provided)
   - Check maximum length: `len(item_id) <= 200`
   - Return 400 Bad Request only if exceeds max length

### Error Responses
```json
// Too long (only validation error)
{
  "detail": "itemId must be 200 characters or less"
}
```

## Tests (names and scope)

### Integration Tests (test_ground_truths_explorer.py or new file)
- `test_list_ground_truths_search_by_id_exact_match`
  - Search finds exact ID match (case-insensitive)

- `test_list_ground_truths_search_by_id_partial_match`
  - Search finds items with ID containing search term

- `test_list_ground_truths_search_by_id_case_insensitive`
  - Search matches regardless of case (UPPER/lower/MiXeD)

- `test_list_ground_truths_search_by_id_with_whitespace_trimming`
  - Leading/trailing whitespace is trimmed before search

- `test_list_ground_truths_search_by_id_whitespace_only_returns_all`
  - Whitespace-only itemId is treated as omitted (returns all items)

- `test_list_ground_truths_search_by_id_combined_with_other_filters`
  - ID search works with status, dataset, tags filters

- `test_list_ground_truths_search_by_id_empty_results`
  - Returns empty list when no IDs match search term

- `test_list_ground_truths_search_by_id_pagination`
  - Pagination works correctly with ID search (multiple matches)

- `test_list_ground_truths_search_by_id_too_long_returns_400`
  - Returns 400 when itemId exceeds 200 characters

- `test_list_ground_truths_search_by_id_no_param_returns_all`
  - Omitting itemId parameter returns all items (existing behavior unchanged)

## Implementation Considerations

### Case Sensitivity
- Cosmos DB `CONTAINS()` is case-sensitive by default
- Use `UPPER()` on both column and search value for case-insensitive matching
- Alternative: `LOWER()` works equally well

### Performance
- Cross-partition query required (ID not part of partition key)
- `CONTAINS()` cannot use index efficiently (full scan)
- Consider adding `STARTSWITH()` option in future for prefix-only search (better index utilization)
- For now, keep simple with `CONTAINS()` for flexibility

### Search Strategy Options
1. **CONTAINS (chosen)**: Substring anywhere in ID
   - Most flexible for users
   - Slowest performance (cannot use index)
   
2. **STARTSWITH (alternative)**: Prefix matching only
   - Better performance (can use index)
   - Less flexible for users
   
3. **Exact match (not chosen)**: Full ID match only
   - Best performance
   - Least flexible (users must know full ID)

### Whitespace Handling
- Trim at API layer before passing to repository
- Ensures consistent behavior across all clients
- If empty after trim, treat as if parameter was omitted (no ID filter applied)
- Prevents searches with only whitespace characters

### Backward Compatibility
- All existing tests should pass (itemId is optional)
- No changes to existing endpoint behavior when itemId omitted
- No breaking changes to response schema

## Out of Scope (Future Work)
- Regex pattern matching for advanced ID searches
- Fuzzy matching / Levenshtein distance for typo tolerance
- Search by other fields (question text, answer text) — use separate search endpoint
- Highlighting matched portion of ID in response
- Multiple ID searches (e.g., `itemId=id1,id2,id3`)
- Caching search results for common queries
- Search analytics/metrics
- Alternative search methods (STARTSWITH vs CONTAINS) as query parameter

## Simple Step Sequence
1. Update `app/adapters/repos/base.py` protocol signature
2. Extend `_build_query_filter()` in `cosmos_repo.py` to handle `item_id_search` parameter
3. Add `item_id` query parameter to `list_all_ground_truths()` in `ground_truths.py`
4. Add validation logic (trim, length checks) at API layer
5. Write integration tests covering all search scenarios
6. Run existing test suite to ensure no regressions
7. Test manually with various ID patterns (exact, partial, case variations)

## Code Snippets

### Cosmos Query Filter Addition
```python
# In _build_query_filter()
if item_id_search:
    search_upper = item_id_search.upper()
    clauses.append("CONTAINS(UPPER(c.id), @searchId)")
    params.append({"name": "@searchId", "value": search_upper})
```

### API Parameter Validation
```python
# In list_all_ground_truths()
if item_id is not None:
    item_id = item_id.strip()
    if not item_id:
        # Empty after trim - treat as if parameter not provided
        item_id = None
    elif len(item_id) > 200:
        raise HTTPException(
            status_code=400,
            detail="itemId must be 200 characters or less"
        )
```

## Minimal Behavior Notes
- Default behavior unchanged when `itemId` omitted or empty after trim
- Search is always case-insensitive (no case-sensitive option)
- Search is always substring match (no exact-match-only option)
- Whitespace always trimmed; empty after trim = parameter omitted
- Works with all existing filters (status, dataset, tags)
- Works with all sorting options
- Works with pagination (search results are paginated normally)
