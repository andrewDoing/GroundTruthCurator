<!-- markdownlint-disable-file -->
# Release Changes: Tag Glossary Inline Editing (TG-06)

**Related Plan**: IMPLEMENTATION_PLAN.md (Priority 4: Documentation > Tag Glossary)
**Implementation Date**: 2026-01-23

## Summary

Added inline editing capabilities for custom tag definitions in the TagGlossaryModal. SMEs can now create, edit, and delete custom tag definitions directly from the glossary UI without needing to interact with the backend API manually.

## Changes

### Added

* `frontend/src/services/tags.ts` - Added `createTagDefinition()` and `deleteTagDefinition()` API client functions
* `.copilot-tracking/changes/20260123-tag-glossary-inline-editing-changes.md` - This change log file

### Modified

* `frontend/src/hooks/useTagGlossary.ts` - Added `refresh()` method to GlossaryStore and exposed it in the hook return value
* `frontend/src/components/modals/TagGlossaryModal.tsx` - Implemented complete inline editing UI:
  - Added "New Custom Tag" button to controls section
  - Implemented create form with tag key and description inputs
  - Added Edit (pencil) and Delete (trash) buttons for custom tags
  - Implemented inline editing mode for tag descriptions
  - Added state management for editing/creating operations with loading states
  - Integrated with refresh() to update glossary after mutations
* `frontend/src/api/generated.ts` - Regenerated TypeScript types from updated OpenAPI spec
* `frontend/src/api/openapi.json` - Regenerated from backend API (includes tag definitions endpoints)
* `backend/pyproject.toml` - Updated (via export_openapi.py formatting)

### Removed

None

## Implementation Details

### UI Features

1. **New Custom Tag Creation**:
   - Button in controls section opens inline form
   - Form validates both tag key and description required
   - Cancel button discards changes
   - Success refreshes glossary and closes form

2. **Inline Editing**:
   - Edit button appears only on custom tag entries
   - Switches to inline textarea for description editing
   - Save/Cancel buttons for inline editing mode
   - Disabled state during async operations

3. **Tag Deletion**:
   - Delete button appears only on custom tag entries
   - Confirmation dialog prevents accidental deletion
   - Success refreshes glossary to reflect removal

4. **Error Handling**:
   - Alert dialogs for API errors with descriptive messages
   - Disabled UI during async operations (submitting state)
   - Form validation before submission

### API Integration

- `POST /v1/tags/definitions` - Create or update custom tag definition
- `DELETE /v1/tags/definitions/{tag_key}` - Delete custom tag definition
- Both endpoints use the existing backend infrastructure (TG-04)

### Testing Results

- All 237 frontend tests pass
- All 267 backend unit tests pass
- TypeScript build succeeds with no errors
- Frontend production build succeeds

## Release Summary

**Files Modified**: 5
**Files Added**: 1
**Files Removed**: 0

**Deployment Notes**: 
- Frontend requires rebuild to include new inline editing UI
- Backend API endpoints already exist from TG-04 implementation
- No database migrations required
- Feature is backward compatible with existing glossary functionality
