<!-- markdownlint-disable-file -->
# Release Changes: Pydantic Alias Type Checker Fix

**Related Plan**: IMPLEMENTATION_PLAN.md (CI Code Quality Gates)
**Implementation Date**: 2026-01-23

## Summary

Fixed type checker warnings for Pydantic v2 models using field aliases. When using `alias` parameter with `populate_by_name=True`, the type checker requires using the alias names (camelCase) when instantiating models, not the field names (snake_case).

## Changes

### Modified

* `backend/app/services/duplicate_detection_service.py` - Changed DuplicateWarning instantiation to use camelCase alias names (itemId, duplicateId, duplicateQuestion, duplicateStatus, matchReason) instead of snake_case field names
* `backend/app/api/v1/ground_truths.py` - Changed ImportBulkResponse instantiation to use camelCase alias names (piiWarnings, duplicateWarnings, validationSummary) instead of snake_case field names

## Release Summary

**Type Checker Status**: All checks passed (0 diagnostics)
**Test Results**: All 267 backend unit tests pass
**Files Modified**: 2

## Deployment Notes

This change fixes type checker warnings without changing runtime behavior or API contracts. The models continue to accept both snake_case and camelCase field names during validation due to `populate_by_name=True`, but the type checker requires using the alias names for proper static analysis.
