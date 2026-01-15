---
title: Batch Validation
description: The batch validation system provides structured error feedback and proper data integrity checks during bulk imports
jtbd: JTBD-004
author: spec-builder
ms.date: 2026-01-22
status: draft
stories: [SA-241]
---

# Batch Validation

## Overview

Enhanced validation and error reporting for bulk import operations, providing structured error objects with row-level context and field-specific feedback.

**Parent JTBD:** Help administrators ensure data integrity and security

## Problem Statement

The current bulk import system has significant gaps in error reporting and validation:

1. **Unstructured errors**: Errors are plain strings with no programmatic structure, making automated error handling impossible
2. **No row context**: When imports fail, there's no indication of which row number failed
3. **Limited field information**: Errors don't specify which field caused the failure
4. **No error codes**: Clients can't programmatically distinguish between error types
5. **Limited validation scope**: Only `manualTags` are validated; other fields bypass validation
6. **No summary statistics**: No aggregate view of total/succeeded/failed counts
7. **Sequential processing**: Individual Cosmos `create_item()` calls instead of batch operations

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Structured error objects | Must | Each error includes `index`, `itemId`, `field`, `code`, and `message` |
| FR-002 | Row index tracking | Must | Errors reference the 0-based index of the item in the request array |
| FR-003 | Field-level errors | Must | Validation failures specify which field caused the error |
| FR-004 | Error codes | Must | Each error has a code (e.g., `INVALID_TAG`, `DUPLICATE_ID`, `MISSING_FIELD`) |
| FR-005 | Validation summary | Must | Response includes `total`, `imported`, and `failed` counts |
| FR-006 | Backward-compatible response | Should | Existing `errors` list format remains available for compatibility |
| FR-007 | Extended validation | Should | Validate required fields beyond just `manualTags` |
| FR-008 | Cosmos batch operations | Could | Use transactional batch instead of sequential creates |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | Batch import throughput | Equal or better than current sequential approach |
| NFR-002 | Reliability | Error completeness | 100% of failures produce structured errors |
| NFR-003 | Usability | Error clarity | Errors actionable without documentation lookup |
| NFR-004 | Compatibility | API versioning | No breaking changes to existing response consumers |

## User Stories

### Story 1: Admin imports data with actionable error feedback

**As** a data administrator  
**I want** structured error information when batch imports fail  
**So that** I can quickly identify and fix issues in my import data

**Acceptance Criteria:**

- When I import a batch with invalid records, each error shows the row number
- Errors specify which field failed validation
- Errors include a code I can use in automated retry logic
- I see a summary of how many records succeeded vs failed

### Story 2: Developer handles errors programmatically

**As** a developer integrating with the bulk import API  
**I want** error codes and structured error objects  
**So that** I can build automated error handling and user feedback

**Acceptance Criteria:**

- Errors have a consistent schema with typed fields
- Error codes are documented and stable
- I can filter errors by code or field

## Technical Considerations

### New Error Model

```python
class BulkImportError(BaseModel):
    """Structured error for bulk import failures."""
    index: int                    # 0-based position in request array
    item_id: str | None           # ID of the failed item (if available)
    field: str | None             # Field that caused the error (if applicable)
    code: str                     # Error code: INVALID_TAG, DUPLICATE_ID, etc.
    message: str                  # Human-readable error description
```

### Enhanced Response Model

```python
class ValidationSummary(BaseModel):
    """Summary statistics for bulk import."""
    total: int                    # Total items in request
    succeeded: int                # Items successfully imported
    failed: int                   # Items that failed

class ImportBulkResponse(BaseModel):
    """Enhanced response with structured errors."""
    imported: int                 # Count of successful imports
    failed: int                   # Count of failures
    errors: list[BulkImportError] # Structured error objects
    uuids: list[str]              # IDs in request order
    validation_summary: ValidationSummary
```

### Error Codes

| Code | Source | Description |
|------|--------|-------------|
| `INVALID_TAG` | Tag validation | Tag doesn't exist in registry or violates format |
| `DUPLICATE_ID` | Cosmos 409 | Item with this ID already exists |
| `CREATE_FAILED` | Cosmos error | Generic persistence failure |
| `MISSING_FIELD` | Validation | Required field is missing |
| `INVALID_FORMAT` | Validation | Field value doesn't match expected format |

### Implementation Notes

1. **Maintain backward compatibility**: Keep `errors` as a list but populate with structured objects
2. **Track index during iteration**: Pass index through validation and persistence flows
3. **Consider Cosmos transactional batch**: For items in the same partition, batch operations reduce latency and RU cost
4. **Pydantic 422 handling**: Intercept Pydantic validation errors to convert to structured format

### Affected Files

| File | Change |
|------|--------|
| `app/domain/models.py` | Add `BulkImportError`, `ValidationSummary` models |
| `app/api/v1/ground_truths.py` | Update `ImportBulkResponse`, modify endpoint logic |
| `app/services/validation_service.py` | Return structured errors with index and field |
| `app/adapters/repos/cosmos_repo.py` | Return structured errors from persistence |
| `tests/unit/test_bulk_import*.py` | Update tests for new response format |

## Open Questions

1. **Partial success handling**: Should there be an option for "all-or-nothing" mode where any failure rolls back all changes?
2. **Error limit**: Should we cap the number of errors returned (e.g., first 100) for very large imports?
3. **Cosmos batch scope**: Transactional batch is limited to items in the same partition - how should cross-partition imports be handled?
4. **Deprecation timeline**: When can we deprecate the plain string error format?

## References

- **Story:** SA-241 - Enhanced error information for batch import
- **Research:** [batch-validation-research.md](../.copilot-tracking/subagent/20260122/batch-validation-research.md)
- **Related code:** [ground_truths.py](../backend/app/api/v1/ground_truths.py), [validation_service.py](../backend/app/services/validation_service.py)
