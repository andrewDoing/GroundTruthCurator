<!-- markdownlint-disable-file -->
# Release Changes: Batch Validation Improvements

**Related Plan**: IMPLEMENTATION_PLAN.md (Priority 1 - Data Integrity)
**Implementation Date**: 2026-01-23

## Summary

Enhanced bulk import validation with structured error objects that provide programmatic error handling, row-level context, and field-specific feedback. The new error format includes error codes (INVALID_TAG, DUPLICATE_ID, CREATE_FAILED), 0-based index tracking, field names, and validation summaries with total/succeeded/failed counts.

## Changes

### Added

* `backend/app/domain/models.py` - Added `BulkImportError` model with structured fields (index, item_id, field, code, message)
* `backend/app/domain/models.py` - Added `ValidationSummary` model with total/succeeded/failed statistics

### Modified

* `backend/app/api/v1/ground_truths.py` - Updated `ImportBulkResponse` to use structured `BulkImportError` objects instead of plain strings; added `failed` count and `validation_summary` fields
* `backend/app/services/validation_service.py` - Modified `validate_ground_truth_item` to return `BulkImportError` objects with index tracking; updated function signature to accept `item_index` parameter
* `backend/app/services/validation_service.py` - Modified `validate_bulk_items` to pass item index to validator and return structured errors
* `backend/app/api/v1/ground_truths.py` - Updated `import_bulk` endpoint to convert repository errors to structured format and build validation summary
* `backend/tests/unit/test_bulk_import_tag_validation.py` - Updated test assertions to validate structured error objects (code, field, item_id, index, message)

### Removed

* None

## Release Summary

**Total files affected**: 4 files modified

**API Changes**:
- `ImportBulkResponse` now includes:
  - `failed` (int): count of failed items
  - `errors` (list[BulkImportError]): structured error objects instead of strings
  - `validationSummary`: statistics with total/succeeded/failed counts
- `BulkImportError` structure:
  - `index` (int): 0-based position in request array
  - `itemId` (str | null): ID of failed item
  - `field` (str | null): field that caused error
  - `code` (str): error code (INVALID_TAG, DUPLICATE_ID, CREATE_FAILED)
  - `message` (str): human-readable description

**Error Codes**:
- `INVALID_TAG`: Tag doesn't exist in registry or violates format
- `DUPLICATE_ID`: Item with this ID already exists (Cosmos 409)
- `CREATE_FAILED`: Generic persistence failure

**Testing**: 
- All 11 bulk-related unit tests passing
- Tag validation tests updated for structured error format
- DoS prevention tests passing
- Type checking passes with acceptable warnings

**Backward Compatibility**:
- Response structure changed but maintains same HTTP status codes
- Clients expecting string errors will need to update to use structured objects
- All other fields (imported, uuids, piiWarnings) remain unchanged

**Deployment Notes**: 
- No database migrations required
- No configuration changes required
- Backend-only changes
- Clients consuming bulk import API should update error handling logic
