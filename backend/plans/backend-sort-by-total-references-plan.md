# Backend Sort by totalReferences Performance Plan

## Overview
Implement database-level sorting for `totalReferences` field in the GET `/v1/ground-truths` endpoint to avoid memory-intensive in-memory sorting. This will add `totalReferences` as a stored computed field in Cosmos DB and update the sorting infrastructure to support it.

## Current State Analysis
- `totalReferences` is currently a Pydantic `@computed_field` that calculates reference count at runtime
- Sorting is done in-memory using Python's `_sort_key()` method after retrieving all matching items
- Performance bottleneck: Large datasets require loading all items into memory for sorting
- Current supported sort fields: `id`, `updated_at`, `reviewed_at`, `has_answer`

## Implementation Strategy
1. **Store totalReferences in database** - Add computed field to Cosmos DB documents
2. **Update domain model** - Replace computed field with stored field  
3. **Modify repository layer** - Add totalReferences calculation and storage logic
4. **Extend sorting infrastructure** - Add totalReferences to SortField enum and sorting logic
5. **Add migration logic** - Backfill existing documents with totalReferences values

## Files to Change

### Core Domain & Enum Changes
- `app/domain/enums.py` - Add `totalReferences = "totalReferences"` to `SortField` enum
- `app/domain/models.py` - Replace `@computed_field` with stored `totalReferences: int` field

### Repository Layer Changes  
- `app/adapters/repos/cosmos_repo.py` - Add totalReferences computation, storage, and sorting support

### API Layer Changes
- `app/api/v1/ground_truths.py` - No changes needed (already supports dynamic SortField values)

### Migration & Utilities
- `scripts/backfill_total_references.py` - New script to update existing documents

## Function Implementation Details

### `app/domain/models.py`
**replace_computed_field_with_stored_field()**
- Remove `@computed_field totalReferences` property
- Add `totalReferences: int = Field(default=0, alias="totalReferences")` as regular field
- Maintains backward compatibility with existing API consumers

### `app/domain/enums.py`  
**add_total_references_sort_field()**
- Add `totalReferences = "totalReferences"` to `SortField` enum
- Enables API consumers to sort by this new field

### `app/adapters/repos/cosmos_repo.py`
**compute_total_references(item: GroundTruthItem) -> int**
- Calculate total reference count from item.refs and item.history[].refs
- Replicate exact logic from current computed field
- Used during document creation/update

**update_to_doc_with_total_references()**
- Modify `_to_doc()` method to calculate and store totalReferences in document
- Ensure field is always present and up-to-date on document save

**add_total_references_sorting_support()**
- Add `SortField.totalReferences: "c.totalReferences"` to COSMOS_SORT_FIELDS mapping
- Add totalReferences case to `_sort_key()` method for emulator fallback
- Support both database-level and in-memory sorting

**create_migration_methods()**
- `backfill_total_references_batch()` - Update documents in batches
- `get_documents_missing_total_references()` - Query for documents needing updates

### `scripts/backfill_total_references.py`
**create_migration_script()**
- Standalone script to update existing documents with totalReferences field
- Process documents in batches to avoid memory issues
- Progress reporting and error handling
- Can be run safely multiple times (idempotent)

## Test Coverage

### Unit Tests
**test_total_references_field_storage()** - Verify totalReferences stored correctly in documents
**test_total_references_computation()** - Validate reference counting logic matches old computed field  
**test_sort_by_total_references()** - Confirm sorting works with new field
**test_total_references_migration()** - Test backfill logic for existing documents
**test_backward_compatibility()** - Ensure API responses remain unchanged

### Integration Tests  
**test_sort_total_references_api_endpoint()** - End-to-end sorting via API
**test_total_references_cosmos_query()** - Database-level sorting performance
**test_migration_script_execution()** - Full migration workflow testing

## Performance Benefits
- **Database-level sorting**: Eliminate need to load all documents into memory
- **Indexed sorting**: Cosmos DB can use indexes for efficient totalReferences ordering
- **Reduced memory usage**: Only requested page of results loaded into application memory
- **Better scalability**: Performance remains constant regardless of dataset size

## Migration Strategy
1. **Deploy code changes**: New field will be populated on all new/updated documents
2. **Run backfill script**: Update existing documents with totalReferences values  
3. **Verify data consistency**: Ensure all documents have totalReferences field
4. **Monitor performance**: Confirm improved query performance on large datasets

## Rollback Plan
- Remove `SortField.totalReferences` enum value to disable API sorting option
- Computed field logic can be restored if needed
- Migration script can identify and remove totalReferences fields if rollback required