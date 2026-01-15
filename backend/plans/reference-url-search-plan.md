# Reference URL Search Plan

## Overview
Add a new **optional** query parameter `refUrl` to GET `/v1/ground-truths` endpoint that filters ground truth items containing references with matching URLs. The search will check both item-level refs and history/turn-level refs, performing case-sensitive partial matching on the URL field. When omitted or empty, no URL filtering is applied.

## Implementation Strategy
Keep it simple: Add a single optional query parameter that searches for reference URLs across both item-level and history-level references using Cosmos DB SQL's ARRAY operations. Empty values are treated as no filter.

---

## Files to Change

### 1. `app/api/v1/ground_truths.py`
**Function:** `list_all_ground_truths()`
- Add optional `ref_url` query parameter (alias: `refUrl`, default: `None`)
- Validate ref_url: trim whitespace, treat empty string as None (no filtering)
- Max 500 characters when non-empty
- Pass validated ref_url to repository layer

### 2. `app/adapters/repos/cosmos_repo.py`
**Function:** `list_gt_paginated()`
- Add `ref_url: str | None = None` parameter
- Pass ref_url to `_build_query_filter()` and `_get_filtered_count()`

**Function:** `_list_gt_paginated_with_tags()`
- Add `ref_url: str | None = None` parameter
- Pass ref_url to filtering logic

**Function:** `list_gt_by_dataset()`
- Add `ref_url: str | None = None` parameter
- Pass ref_url to query building

**Function:** `_build_query_filter()`
- Add `ref_url: str | None = None` parameter
- Build WHERE clause using `EXISTS` with subqueries:
  - Check item-level refs: `EXISTS(SELECT VALUE r FROM r IN c.refs WHERE CONTAINS(r.url, @refUrl))`
  - Check history-level refs: `EXISTS(SELECT VALUE h FROM h IN c.history WHERE EXISTS(SELECT VALUE r FROM r IN h.refs WHERE CONTAINS(r.url, @refUrl)))`
  - Combine with OR: `(item_refs_exists OR history_refs_exists)`
- Add @refUrl parameter to params list

**Function:** `_get_filtered_count()`
- Add `ref_url: str | None = None` parameter
- Pass ref_url to `_build_query_filter()`

---

## Test Coverage

### `tests/integration/test_ground_truths_reference_search.py`

**test_ref_url_search_matches_item_level_refs**
- Item with ref url containing "example.com/page1" → search "page1" returns item

**test_ref_url_search_matches_history_level_refs**
- Item with history turn refs containing "docs.example.com/article" → search "article" returns item

**test_ref_url_search_matches_both_levels**
- Item with item-level ref "foo.com/bar" and history ref "baz.com/bar" → search "bar" returns item

**test_ref_url_search_case_sensitive**
- Item with ref "Example.COM" → search "example.com" returns nothing (case-sensitive)

**test_ref_url_search_partial_match**
- Item with ref "https://docs.example.com/guide" → searches "docs.example" or "/guide" return item

**test_ref_url_search_no_matches**
- Items with various refs → search "nonexistent-url" returns empty list

**test_ref_url_search_multiple_refs_per_item**
- Item with 5 refs, only one matches → search finds item

**test_ref_url_search_combined_with_other_filters**
- Multiple items, different datasets/statuses → refUrl + dataset + status filters work together

**test_ref_url_search_with_pagination**
- 50 items with matching refs → page=1, limit=10 returns first 10, total=50

**test_ref_url_search_empty_string_ignored**
- Search with empty/whitespace refUrl → behaves like no filter, returns all items (no error)

**test_ref_url_search_omitted_parameter**
- Request without refUrl parameter → returns all items (parameter truly optional)

---

## Technical Details

### Cosmos DB Query Pattern
```sql
WHERE (
  EXISTS(SELECT VALUE r FROM r IN c.refs WHERE CONTAINS(r.url, @refUrl))
  OR EXISTS(
    SELECT VALUE h FROM h IN c.history 
    WHERE EXISTS(SELECT VALUE r FROM r IN h.refs WHERE CONTAINS(r.url, @refUrl))
  )
)
```

### Query Parameter Validation
- Optional parameter (default: None)
- Trim whitespace
- Empty string after trim → treat as None (no filtering applied)
- Max length when non-empty: 500 characters
- Case-sensitive partial matching (CONTAINS)

### Edge Cases
- Items without refs array → excluded (refs required in schema, defaults to empty list)
- History items without refs → ignored (refs optional on HistoryItem)
- Multiple history turns with refs → any match returns item
- URL with special characters → passed as-is to CONTAINS

---

## API Example

### Request
```http
GET /v1/ground-truths?refUrl=docs.example.com&dataset=sample-kb&page=1&limit=25
```

### Response
```json
{
  "items": [
    {
      "id": "item-123",
      "datasetName": "sample-kb",
      "synthQuestion": "How do I configure X?",
      "refs": [
         {"url": "https://docs.example.com/help/product/config"}
      ],
      "history": [
        {
          "role": "assistant",
          "msg": "Here's the answer...",
          "refs": [
             {"url": "https://docs.example.com/support/article-456"}
          ]
        }
      ],
      "totalReferences": 2
    }
  ],
  "pagination": {...}
}
```

---

## Implementation Notes

1. **Optional parameter**: `refUrl` is completely optional; when omitted or empty, no URL filtering occurs
2. **Performance**: Cosmos DB handles EXISTS subqueries efficiently; indexes on refs arrays help
3. **Case sensitivity**: CONTAINS is case-sensitive in Cosmos DB; matches production behavior
4. **Partial matching**: CONTAINS allows flexible searches (domain, path segments, full URL)
5. **Backward compatibility**: Optional parameter, existing queries unchanged
6. **Tag filter compatibility**: Works with existing tag-based filtering path
