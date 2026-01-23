<!-- markdownlint-disable-file -->
# Release Changes: Tag Glossary Implementation

**Related Plan**: N/A (standalone feature)
**Implementation Date**: 2026-01-23

## Summary

Implemented tag glossary system to provide human-readable descriptions for all tags via tooltip UI. Users can now hover over any TagChip to see a definition, improving tag understanding and consistency.

## Changes

### Added

* `backend/app/api/v1/tags.py` - Added `/v1/tags/glossary` endpoint returning comprehensive tag definitions from manual and computed sources
* `backend/tests/unit/test_tags_glossary.py` - Unit tests for glossary endpoint (3 tests covering manual tags, computed tags, and response structure)
* `frontend/src/hooks/useTagGlossary.ts` - React hook to fetch and cache tag glossary data, providing lookup map of tag key -> description
* Tag definitions to `backend/app/domain/manual_tags.json` - Extended schema to include group descriptions and per-tag descriptions for all 6 tag groups (source, answerability, topic, intent, expertise, difficulty)

### Modified

* `backend/app/domain/manual_tags_provider.py` - Extended `ManualTagGroup` dataclass to support optional `description` and `tag_definitions` fields; updated parser to handle both old (string list) and new (object list) tag formats
* `backend/tests/unit/test_manual_tags_provider.py` - Updated test assertions to match new data structure with `tag_definitions` field
* `frontend/src/components/common/TagChip.tsx` - Enhanced component to fetch and display tag descriptions via CSS tooltip on hover (using `useTagDescription` hook)
* `frontend/src/api/openapi.json` - Regenerated OpenAPI spec to include glossary endpoint schema
* `frontend/src/api/generated.ts` - Regenerated TypeScript types for glossary response models

### Removed

* None

## Technical Details

### Backend Implementation

- **Backward compatibility**: Manual tags JSON parser accepts both old format (`tags: ["value"]`) and new format (`tags: [{"value": "...", "description": "..."}]`)
- **Data model**: Extended `ManualTagGroup` with optional `description` (group-level) and `tag_definitions` (tag-level) fields
- **API response**: Glossary endpoint merges manual tags from config file and computed tags from plugin registry into unified response
- **Computed tags**: Phase 1 includes computed tags in glossary without descriptions (descriptions deferred to future phase)

### Frontend Implementation

- **No dependencies added**: Used native CSS tooltips instead of Radix UI to avoid adding dependencies
- **Plain React state**: Implemented `useTagGlossary` hook with useState/useEffect instead of React Query (not installed)
- **Tooltip UX**: Tooltips appear on hover with 200ms transition, positioned above tag with arrow pointer
- **Fallback behavior**: Tags without definitions show no tooltip (graceful degradation)

## Test Coverage

- **Backend**: 3 new unit tests for glossary endpoint, all 256 backend unit tests passing
- **Frontend**: All 226 frontend tests passing, build succeeds

## Manual Testing Required

1. Start dev server: `cd backend && uv run uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to Questions Explorer
4. Hover over tags to verify tooltips appear with descriptions
5. Verify tooltips for manual tags (e.g., "source:sme") show descriptions
6. Verify computed tags show generic "no description" behavior or empty tooltip

## Release Summary

**Files Added**: 2
**Files Modified**: 7
**Files Removed**: 0

**Deployment Notes**:
- No database migrations required
- No environment variable changes needed
- Backend API is backward compatible (glossary endpoint is additive)
- Frontend gracefully handles missing glossary data
