# Batch Validation Research

**Date:** 2026-01-22
**Story:** SA-241 - Enhanced error information for batch import
**Status:** Complete

## Research Questions Answered

### 1. How does the current bulk import validate individual records?

**Location:** [validation_service.py](../../../backend/app/services/validation_service.py)

The validation flow has two stages:

#### Stage 1: Pre-persistence validation (validation_service.py)

```python
async def validate_bulk_items(items: list[GroundTruthItem]) -> dict[str, list[str]]:
```

- **Tag validation only**: Currently validates only `manualTags` against the tag registry
- **Concurrent validation**: Uses `asyncio.gather()` to validate all items concurrently
- **Caching**: Fetches tag registry once and passes to all validation calls
- **Error collection**: Returns `dict[item_id, list[errors]]` mapping

**Current validation checks:**

| Check | Field | Implementation |
|-------|-------|----------------|
| Tag existence | `manualTags` | Tags must exist in tag registry |
| Tag format | `manualTags` | Must match `group:value` pattern |
| Tag rules | `manualTags` | TAG_SCHEMA rules (e.g., uniqueness within group) |

#### Stage 2: Persistence-time validation (cosmos_repo.py)

```python
async def import_bulk_gt(self, items: list[GroundTruthItem], buckets: int | None = None) -> BulkImportResult:
```

- **409 Conflict**: Catches duplicate ID errors from Cosmos
- **Other Cosmos errors**: Generic error message with article URL and ID

### 2. What error information is returned when records fail validation?

**Response model:** `ImportBulkResponse` in [ground_truths.py#L30](../../../backend/app/api/v1/ground_truths.py#L30)

```python
class ImportBulkResponse(BaseModel):
    imported: int       # Number of items successfully imported
    errors: list[str]   # List of error messages
    uuids: list[str]    # IDs in request order (includes failed items)
```

**Current error message formats:**

| Source | Format | Example |
|--------|--------|---------|
| Tag validation | `"Item '{item_id}': Error {message}"` | `"Item 'test-2': Error Unknown tag 'invalid:tag'."` |
| Duplicate (409) | `"exists (article: {url}, id: {id})"` | `"exists (article: http://..., id: abc-123)"` |
| Cosmos error | `"create_failed (article: {url}, id: {id}): {message}"` | `"create_failed (article: unknown, id: xyz): RU exceeded"` |

**Gaps identified:**

1. No structured error format - errors are strings, not objects
2. No field-level error information
3. No row/index reference for correlation
4. No error code for programmatic handling
5. Pydantic validation errors (if any bypass) would return 422, not included in errors array

### 3. Is Cosmos batch/transactional batch being used, or individual creates?

**Answer: Individual creates (1-by-1)**

**Location:** [cosmos_repo.py#L486](../../../backend/app/adapters/repos/cosmos_repo.py#L486)

```python
# sequential create to keep simple and clear errors
for it in items:
    doc = self._to_doc(it)
    try:
        await gt.create_item(doc)  # Individual create
        success += 1
    except CosmosHttpResponseError as e:
        # Error handling...
```

**Current behavior:**

- Items are created **sequentially** in a loop
- No transactional batch support
- Partial success is possible (some items succeed, some fail)
- No rollback capability

**Cosmos SDK batch capabilities NOT used:**

- `container.execute_batch()` - not used
- `TransactionalBatch` - not used
- Bulk executor - not used

### 4. What's the current ImportBulkResponse structure?

**Location:** [models.py#L182](../../../backend/app/domain/models.py#L182)

```python
class BulkImportResult(BaseModel):  # Internal model
    imported: int = 0
    errors: list[str] = Field(default_factory=list)

class ImportBulkResponse(BaseModel):  # API response
    imported: int       # Number of items successfully imported
    errors: list[str]   # List of error messages for failed items
    uuids: list[str]    # IDs in same order as request
```

**Example successful response:**

```json
{
  "imported": 2,
  "errors": [],
  "uuids": ["item-1", "item-2"]
}
```

**Example partial failure response:**

```json
{
  "imported": 1,
  "errors": ["Item 'item-2': Error Unknown tag 'bad:tag'."],
  "uuids": ["item-1", "item-2"]
}
```

## Current Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                       import_bulk()                              │
├─────────────────────────────────────────────────────────────────┤
│ 1. Generate IDs for items missing them (randomname)              │
│ 2. validate_bulk_items() ─► Tag validation                       │
│    ├─ Fetch tag registry once                                    │
│    ├─ Validate each item's manualTags                            │
│    └─ Return dict[item_id, errors]                               │
│ 3. Filter out invalid items                                      │
│ 4. Apply computed tags to valid items                            │
│ 5. container.repo.import_bulk_gt() ─► Cosmos persistence         │
│    ├─ Loop: create_item() for each                               │
│    ├─ Catch 409: append "exists" error                           │
│    └─ Catch other: append "create_failed" error                  │
│ 6. Merge validation errors + persistence errors                  │
│ 7. Return ImportBulkResponse                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Identified Gaps for SA-241

### Gap 1: Unstructured error messages

**Current:** Plain strings  
**Needed:** Structured error objects with:

- `index`: Row number in original request
- `itemId`: The item's ID
- `field`: Which field failed (if applicable)
- `code`: Error code for programmatic handling
- `message`: Human-readable message

### Gap 2: No batch processing

**Current:** Sequential `create_item()` calls  
**Needed:** Cosmos transactional batch for:

- Better performance (single network round-trip)
- Atomic operations within partition
- RU efficiency

### Gap 3: Limited validation scope

**Current:** Only manualTags validated  
**Needed:** Consider validating:

- Required fields
- Field length limits
- Reference URL format
- Custom business rules

### Gap 4: No partial rollback capability

**Current:** Items persist as they succeed  
**Needed:** Consider all-or-nothing mode option

### Gap 5: No validation summary

**Current:** Just error list  
**Needed:** Summary stats:

- Total items received
- Validation failures count
- Persistence failures count
- By-field error breakdown

## Recommendations for SA-241

1. **Define structured error model:**

   ```python
   class ImportError(BaseModel):
       index: int
       itemId: str | None
       field: str | None
       code: str  # e.g., "INVALID_TAG", "DUPLICATE_ID"
       message: str
   ```

2. **Enhance ImportBulkResponse:**

   ```python
   class ImportBulkResponse(BaseModel):
       imported: int
       failed: int
       total: int
       errors: list[ImportError]  # Structured errors
       uuids: list[str]
   ```

3. **Consider Cosmos batch operations** for performance (separate story)

4. **Add validation for additional fields** as needed

## Files Analyzed

| File | Purpose |
|------|---------|
| [ground_truths.py](../../../backend/app/api/v1/ground_truths.py) | API endpoint, response models |
| [validation_service.py](../../../backend/app/services/validation_service.py) | Pre-persistence validation |
| [cosmos_repo.py](../../../backend/app/adapters/repos/cosmos_repo.py) | Database operations |
| [models.py](../../../backend/app/domain/models.py) | Domain models |
| [tagging_service.py](../../../backend/app/services/tagging_service.py) | Tag validation logic |
| [test_bulk_import_tag_validation.py](../../../backend/tests/unit/test_bulk_import_tag_validation.py) | Test coverage |
