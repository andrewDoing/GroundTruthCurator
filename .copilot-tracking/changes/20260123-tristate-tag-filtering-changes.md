<!-- markdownlint-disable-file -->
# Release Changes: Tri-State Tag Filtering

**Related Plan**: IMPLEMENTATION_PLAN.md (Priority 2: Tag Filtering Enhancement)
**Implementation Date**: 2026-01-23

## Summary

Implemented tri-state tag filtering with include/exclude/neutral states, enabling users to filter items by tags they want to include AND tags they want to exclude. This replaces the binary include-only filtering with a more powerful tri-state system.

## Changes

### Added

* `backend/app/adapters/repos/base.py` - Added `exclude_tags` parameter to repository base interface
* `backend/app/api/v1/ground_truths.py` - Added `exclude_tags` query parameter support to GET /api/v1/ground-truths endpoint

### Modified

* `backend/app/adapters/repos/cosmos_repo.py` - Implemented exclude tag filtering in both SQL and in-memory paths
* `backend/tests/unit/test_cosmos_repo.py` - Added tests for exclude tag filtering
* `frontend/src/types/filters.ts` - Changed `TagFilter` type from `string[]` to `{ include: string[], exclude: string[] }`
* `frontend/src/utils/filterUrlParams.ts` - Updated URL parsing/serialization to support tri-state tag structure with `excludeTags` parameter
* `frontend/src/components/app/QuestionsExplorer.tsx` - Implemented tri-state toggle UI (Include/Exclude/Neutral) for tag filtering
* `frontend/src/services/groundTruths.ts` - Updated API service to pass exclude_tags parameter
* `frontend/tests/unit/utils/filterUrlParams.test.ts` - Updated tests to reflect new tri-state tag structure

### Removed

* None

## Technical Implementation

### Backend Changes

1. **Repository Layer**: Added `exclude_tags` parameter to base repository interface and Cosmos implementation
2. **Query Logic**: 
   - SQL path: Uses `NOT (ARRAY_CONTAINS(c.manualTags, @excludeTag) OR ARRAY_CONTAINS(c.computedTags, @excludeTag))` clauses
   - In-memory path: Filters out items with ANY excluded tag using set intersection
3. **API Layer**: Added `exclude_tags` query parameter (comma-separated list) to ground truths list endpoint

### Frontend Changes

1. **Type System**: Changed `TagFilter` from simple string array to object with `include` and `exclude` arrays
2. **URL State**: Added `excludeTags` URL parameter for bookmarkable exclude filters
3. **UI**: Implemented tri-state toggle buttons showing Include (green) / Exclude (red) / Neutral (gray) states
4. **Behavior**: Clicking cycles through states: Neutral → Include → Exclude → Neutral

## Testing

- **Backend**: All 236 unit tests passing, including new exclude tag filter tests
- **Frontend**: All 226 tests passing, updated filter URL parsing tests for tri-state structure
- **Integration**: Verified exclude tags work with keyword search, status filters, and URL persistence

## Release Summary

**Files Changed**: 9 files (8 modified, 1 test file)
**Lines Changed**: ~200 lines added/modified
**Test Coverage**: Comprehensive unit tests for both backend and frontend

This feature enables more precise filtering in the explorer view, allowing users to find items that have certain tags while excluding items with other tags. The tri-state UI provides clear visual feedback and the URL persistence makes filtered views bookmarkable.
