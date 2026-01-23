<!-- markdownlint-disable-file -->
# Release Changes: Custom Tag Definitions Storage (TG-04)

**Related Plan**: IMPLEMENTATION_PLAN.md (Tag Glossary - TG-04)
**Implementation Date**: 2026-01-23

## Summary

Implemented database storage for SME-created custom tag definitions, enabling users to define and persist custom tags with descriptions that appear in the tag glossary alongside system-defined manual and computed tags. This completes the backend foundation for TG-04, with frontend UI (TG-06) deferred to a future increment.

## Changes

### Added

* `backend/app/adapters/repos/tag_definitions_repo.py` - Repository adapter for Cosmos DB tag definitions storage with CRUD operations (get_definition, list_all, upsert, delete)
* `backend/tests/unit/test_tag_definitions_repo.py` - Unit tests for TagDefinitionsRepo (7 tests covering CRUD operations and error cases)
* `COSMOS_CONTAINER_TAG_DEFINITIONS` config in `backend/app/core/config.py` - Container name constant (default: "tag_definitions")
* `TagDefinition` domain model in `backend/app/domain/models.py` - Fields: id, tag_key (partition key), description, created_by, created_at, updated_at, doc_type
* API endpoint `POST /v1/tags/definitions` in `backend/app/api/v1/tags.py` - Create or update custom tag definition
* API endpoint `DELETE /v1/tags/definitions/{tag_key}` in `backend/app/api/v1/tags.py` - Delete custom tag definition
* Request/response models `TagDefinitionRequest` and `TagDefinitionResponse` in `backend/app/api/v1/tags.py`

### Modified

* `backend/app/container.py` - Wire tag_definitions_repo in container initialization and validation
* `backend/app/api/v1/tags.py` - Extended glossary endpoint to query custom definitions and merge as "custom" type group
* `backend/scripts/cosmos_container_manager.py` - Added --tag-definitions-container flag for container creation (partition key: /tag_key, Hash)
* `backend/tests/unit/test_tags_glossary.py` - Added mock for tag_definitions_repo and test for custom definitions in glossary response (4 tests total)
* `IMPLEMENTATION_PLAN.md` - Marked TG-04 complete, updated with implementation details

### Removed

* None

## Release Summary

**Total Files Affected**: 9 files (639 lines added)
- 2 new files (repository adapter + tests)
- 7 modified files (config, domain model, container, API, script, test, plan)
- 0 removed files

**Test Coverage**: 
- 267 backend unit tests pass (8 new tests: 7 for TagDefinitionsRepo, 1 for glossary endpoint)
- All type checks pass (ty check)

**Deployment Notes**:
- New Cosmos DB container `tag_definitions` must be created using:
  ```bash
  uv run python scripts/cosmos_container_manager.py \
    --endpoint <endpoint> \
    --key <key> \
    --db <database> \
    --tag-definitions-container
  ```
- Container uses partition key `/tag_key` with Hash partitioning
- No frontend changes required (glossary will display empty custom group if no definitions exist)
- TG-06 (inline editing UI) deferred to future increment

**API Changes**:
- `GET /v1/tags/glossary` now includes "custom" group with custom tag definitions from database
- New endpoints: `POST /v1/tags/definitions`, `DELETE /v1/tags/definitions/{tag_key}`
- Authentication for management endpoints uses default "system" user_id (full auth deferred to TG-06)

**Backward Compatibility**: 
- Fully backward compatible
- Glossary endpoint returns empty custom group if tag_definitions container doesn't exist
- No breaking changes to existing API contracts
