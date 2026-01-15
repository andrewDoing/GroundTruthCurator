# Questions Explorer Endpoint Plan

Short overview:
- Add a new GET /v1/ground-truths endpoint (without path parameters) that queries across all datasets with support for filtering, sorting, and pagination. This replaces the need to call /v1/ground-truths/{datasetName} multiple times and enables efficient server-side filtering/sorting for the QuestionsExplorer frontend component.

## What we will implement now
- A new repo method that queries across all datasets with filters (status, dataset, tags), sorting (by field and order), and pagination (page + limit).
- A new API endpoint GET /v1/ground-truths with query parameters that returns paginated results with metadata.
- Response models for pagination metadata and the explorer response.
- No analytics fields (views/reuses) in this iteration—those are future enhancements.
- Keep it SIMPLE: support basic filtering and sorting; client can handle advanced scenarios.

## Files to change
- `app/adapters/repos/base.py` — add protocol method for cross-dataset query with pagination.
- `app/adapters/repos/cosmos_repo.py` — implement the new query method with Cosmos SQL queries.
- `app/domain/models.py` — add pagination response models (PaginationMetadata, GroundTruthListResponse).
- `app/domain/enums.py` — add SortField and SortOrder enums.
- `app/api/v1/ground_truths.py` — add new endpoint handler for GET /v1/ground-truths (no dataset path param).
- Tests:
  - `tests/unit/test_cosmos_repo.py` — test query building logic
  - `tests/integration/test_ground_truths_explorer.py` — new integration test file for explorer endpoint

## Functions (names and purposes)

### Repository Layer
- `GroundTruthRepo.list_gt_paginated(status, dataset, tags, sort_by, sort_order, page, limit) -> tuple[list[GroundTruthItem], PaginationMetadata]`
  - Query ground truths across all (or filtered) datasets with pagination and sorting. Returns items and pagination metadata (total count, pages, etc.).

### API Layer
- `list_all_ground_truths(status, dataset, tags, sortBy, sortOrder, page, limit, user) -> GroundTruthListResponse`
  - FastAPI route handler for GET /v1/ground-truths that accepts query parameters, calls repo, and returns paginated response.

### Domain Models
- `PaginationMetadata`
  - Contains page, limit, total, totalPages, hasNext, hasPrev fields for pagination info.
- `GroundTruthListResponse`
  - Contains items (list[GroundTruthItem]) and pagination (PaginationMetadata) fields.

### Cosmos Implementation
- `CosmosGroundTruthRepo._build_query_filter(status, dataset, tags) -> str`
  - Build SQL WHERE clause from filters; handle multiple tags with AND logic.
- `CosmosGroundTruthRepo._build_order_by(sort_by, sort_order) -> str`
  - Build SQL ORDER BY clause from sort field and direction.
- `CosmosGroundTruthRepo._count_matching_items(where_clause) -> int`
  - Execute COUNT query to get total items matching filters (for pagination).

## API shape

### Endpoint
```
GET /v1/ground-truths?status={status}&dataset={dataset}&tags={tag1,tag2}&sortBy={field}&sortOrder={asc|desc}&page={page}&limit={limit}
```

### Query Parameters
- `status` (optional): GroundTruthStatus enum value (draft, approved, deleted, skipped)
- `dataset` (optional): Filter to specific dataset name
- `tags` (optional): Comma-separated tag list; applies AND logic (item must have all specified tags)
- `sortBy` (optional, default: "reviewedAt"): Field to sort by—reviewedAt, updatedAt, id, hasAnswer
- `sortOrder` (optional, default: "desc"): Sort direction—asc or desc
- `page` (optional, default: 1): Page number (1-indexed)
- `limit` (optional, default: 25): Items per page (max 100)

### Response (200 OK)
```json
{
  "items": [
    { /* GroundTruthItem */ },
    { /* GroundTruthItem */ }
  ],
  "pagination": {
    "page": 1,
    "limit": 25,
    "total": 142,
    "totalPages": 6,
    "hasNext": true,
    "hasPrev": false
  }
}
```

### Error Cases
- 400 Bad Request: Invalid query parameter (e.g., invalid status value, limit > 100, page < 1)
- 500 Internal Server Error: Database query failure

## Domain Models

### SortField Enum
```python
class SortField(str, Enum):
    reviewed_at = "reviewedAt"
    updated_at = "updatedAt"
    id = "id"
    has_answer = "hasAnswer"  # virtual field: bool(answer and answer.strip())
```

### SortOrder Enum
```python
class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"
```

### PaginationMetadata Model
```python
class PaginationMetadata(BaseModel):
    page: int = Field(description="Current page number (1-indexed)")
    limit: int = Field(description="Items per page")
    total: int = Field(description="Total number of items matching filters")
    totalPages: int = Field(description="Total number of pages", alias="totalPages")
    hasNext: bool = Field(description="Whether there is a next page", alias="hasNext")
    hasPrev: bool = Field(description="Whether there is a previous page", alias="hasPrev")
    
    model_config = ConfigDict(populate_by_name=True)
```

### GroundTruthListResponse Model
```python
class GroundTruthListResponse(BaseModel):
    items: list[GroundTruthItem]
    pagination: PaginationMetadata
```

## Cosmos Query Implementation Notes

### Filter Building
- Base query: `SELECT * FROM c WHERE c.docType = 'ground-truth-item'`
- Status filter: `AND c.status = @status`
- Dataset filter: `AND c.datasetName = @dataset`
- Tags filter (AND logic): `AND ARRAY_CONTAINS(c.tags, @tag1) AND ARRAY_CONTAINS(c.tags, @tag2) ...`

### Sorting
- Map sortBy to document field:
  - reviewedAt → c.reviewedAt
  - updatedAt → c.updatedAt
  - id → c.id
  - hasAnswer → computed as `(IS_DEFINED(c.answer) AND LENGTH(c.answer) > 0)`
- Order: `ORDER BY {field} {ASC|DESC}`

### Pagination
- Use OFFSET/LIMIT: `OFFSET @offset LIMIT @limit`
- Calculate offset: `(page - 1) * limit`
- Separate COUNT query: `SELECT VALUE COUNT(1) FROM c WHERE {same_filters}`

### Example Cosmos SQL
```sql
-- Query for items
SELECT * FROM c 
WHERE c.docType = 'ground-truth-item' 
  AND c.status = 'draft' 
  AND c.datasetName = 'faq'
  AND ARRAY_CONTAINS(c.tags, 'sme')
ORDER BY c.reviewedAt DESC
OFFSET 0 LIMIT 25

-- Count query
SELECT VALUE COUNT(1) FROM c 
WHERE c.docType = 'ground-truth-item' 
  AND c.status = 'draft' 
  AND c.datasetName = 'faq'
  AND ARRAY_CONTAINS(c.tags, 'sme')
```

## Minimal behavior notes and assumptions
- Default to 25 items per page if limit not specified
- Maximum limit is 100 to prevent excessive data transfer
- Page numbers are 1-indexed (not 0-indexed)
- Empty results return `items: []` with `total: 0`
- Tags filter uses AND logic (item must have ALL specified tags)
- hasAnswer is computed server-side: answer exists and is non-empty after trimming
- No views/reuses fields in this iteration (add in future)
- Query uses existing Cosmos partition key [/datasetName, /bucket] but cannot leverage it for cross-dataset queries (cross-partition query)
- Authentication required via existing get_current_user dependency

## Tests (names and scope)

### Unit Tests (test_cosmos_repo.py)
- `test_build_query_filter_no_filters`
  - Returns base WHERE clause with only docType filter
  
- `test_build_query_filter_with_status`
  - Adds status condition when status parameter provided
  
- `test_build_query_filter_with_dataset`
  - Adds dataset condition when dataset parameter provided
  
- `test_build_query_filter_with_tags_and_logic`
  - Adds ARRAY_CONTAINS conditions for each tag when tags provided
  
- `test_build_query_filter_all_filters_combined`
  - Combines status + dataset + tags filters correctly
  
- `test_build_order_by_default`
  - Returns reviewedAt DESC when no sort params specified
  
- `test_build_order_by_with_field_and_order`
  - Returns correct ORDER BY clause for specified field and direction
  
- `test_build_order_by_has_answer`
  - Handles hasAnswer virtual field with computed expression

### Integration Tests (test_ground_truths_explorer.py)
- `test_list_all_ground_truths_default_params`
  - Returns paginated results with defaults (page=1, limit=25, sortBy=reviewedAt)
  
- `test_list_all_ground_truths_filter_by_status`
  - Returns only items matching status filter
  
- `test_list_all_ground_truths_filter_by_dataset`
  - Returns only items from specified dataset
  
- `test_list_all_ground_truths_filter_by_tags`
  - Returns only items containing all specified tags
  
- `test_list_all_ground_truths_sort_by_updated_at_asc`
  - Returns items sorted by updatedAt in ascending order
  
- `test_list_all_ground_truths_pagination_first_page`
  - Returns first page with hasNext=true, hasPrev=false
  
- `test_list_all_ground_truths_pagination_middle_page`
  - Returns middle page with hasNext=true, hasPrev=true
  
- `test_list_all_ground_truths_pagination_last_page`
  - Returns last page with hasNext=false, hasPrev=true
  
- `test_list_all_ground_truths_empty_results`
  - Returns empty items array with total=0 when no matches
  
- `test_list_all_ground_truths_combined_filters`
  - Correctly applies multiple filters together (status + dataset + tags)
  
- `test_list_all_ground_truths_invalid_limit_exceeds_max`
  - Returns 400 when limit > 100
  
- `test_list_all_ground_truths_invalid_page_zero`
  - Returns 400 when page < 1

## Out of scope (future work)
- Analytics fields (views, reuses) in schema and sorting—requires database migration
- Full-text search on questions/answers—use dedicated search endpoint
- Exporting paginated results—use existing snapshot endpoint
- Streaming results for very large result sets
- Caching query results for performance
- Advanced tag filtering (OR logic, NOT logic)
- Sorting by multiple fields simultaneously
- Filtering by date ranges (reviewedAt, updatedAt)
- Filtering by assignedTo user

## Simple step sequence
1. Add enums to `app/domain/enums.py` (SortField, SortOrder)
2. Add response models to `app/domain/models.py` (PaginationMetadata, GroundTruthListResponse)
3. Add protocol method to `app/adapters/repos/base.py`
4. Implement Cosmos query logic in `app/adapters/repos/cosmos_repo.py` with helper methods
5. Add endpoint handler to `app/api/v1/ground_truths.py`
6. Write unit tests for query building logic
7. Write integration tests for endpoint with various filter/sort/pagination scenarios
8. Verify with existing test suite, ruff, black, and mypy
9. Update API documentation/OpenAPI schema if auto-generation doesn't capture new endpoint

## Implementation considerations
- Cosmos cross-partition queries can be expensive; ensure indexing policy includes frequently filtered/sorted fields
- Use parameterized queries to prevent SQL injection (Cosmos SDK handles this)
- Consider adding request validation for limit (1-100) and page (>= 1) at API layer
- Return 400 for invalid enum values (status, sortBy, sortOrder) rather than 500
- Ensure etag is included in response items for client-side concurrency control
- Test with empty database and large datasets (>1000 items) for performance validation
