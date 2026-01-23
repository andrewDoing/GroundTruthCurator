<!-- markdownlint-disable-file -->
# Release Changes: Assignment Error Feedback

**Related Plan**: IMPLEMENTATION_PLAN.md (Priority 1 - Data Integrity)
**Implementation Date**: 2026-01-23

## Summary

Enhanced assignment conflict responses with structured payload that includes current assignee information (`assignedTo`, `assignedAt`). When attempting to assign an item already assigned to another user, the 409 response now provides structured JSON with assignment details instead of just a plain error message, enabling better UI feedback and conflict resolution workflows.

## Changes

### Added

* `backend/app/core/errors.py` - Added `AssignmentConflictError` exception class with `assigned_to` and `assigned_at` attributes
* `backend/tests/integration/test_assignments_assign_single_cosmos.py` - Added test assertions to verify structured 409 payload (lines 87-105)

### Modified

* `backend/app/services/assignment_service.py` - Import `AssignmentConflictError` from core.errors module
* `backend/app/services/assignment_service.py` - Changed line 207 to raise `AssignmentConflictError` instead of `ValueError` with assignment details (assigned_to, assigned_at)
* `backend/app/api/v1/assignments.py` - Import `AssignmentConflictError` and `JSONResponse`
* `backend/app/api/v1/assignments.py` - Updated `assign_item` endpoint return type to `GroundTruthItem | JSONResponse` with `response_model=None`
* `backend/app/api/v1/assignments.py` - Added `except AssignmentConflictError` handler (lines 280-293) that returns structured JSON response with `detail`, `assignedTo`, and `assignedAt` fields
* `backend/tests/integration/test_assignments_assign_single_cosmos.py` - Updated test docstring and added assertions for structured response verification

### Removed

* None

## Release Summary

**Total files affected**: 4 files modified

**API Changes**:
- `POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign` now returns structured JSON on 409 conflict:
  ```json
  {
    "detail": "Item is already assigned to another user",
    "assignedTo": "user@example.com",
    "assignedAt": "2026-01-23T12:34:56.789012+00:00"
  }
  ```

**Error Response Structure**:
- `detail` (str): Human-readable error message
- `assignedTo` (str): Email/ID of user who currently has the assignment
- `assignedAt` (str | undefined): ISO 8601 timestamp of when assignment was made (if available)

**Exception Hierarchy**:
- New `AssignmentConflictError` exception carries structured data through service → API layer
- Replaces generic `ValueError("Item is already assigned to another user")`
- Enables consistent structured responses across all assignment conflict scenarios

**Testing**: 
- All 225 unit tests passing
- Integration test updated to verify structured response fields
- Type checking passes with `ty check`

**Backward Compatibility**:
- HTTP status code remains 409 (no change)
- Response structure changed from simple `detail` string to structured JSON object
- Clients expecting only `detail` field will still work but won't utilize new assignment info
- Frontend should update to display `assignedTo` information in conflict dialogs

**Deployment Notes**: 
- No database migrations required
- No configuration changes required
- Backend-only changes
- Recommended: Update frontend to display assignee info when assignment conflicts occur
- Enables future "Assignment Takeover" feature (force parameter) with better UX
