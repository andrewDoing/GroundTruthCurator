# Global tag registry (Cosmos-backed) — minimal plan

## Overview

We’ll add a single, global tags registry persisted as one Cosmos DB document in a new Cosmos DB container dedicated to tags. Provide three endpoints to list, add, and remove tags. Keep it simple: use the existing tag canonicalization (group:value, lowercase/trim), store a deduped/sorted list, and skip advanced validation or dataset-specific logic for now.

- Only implement what we need now: global tags list/add/remove.
- No legacy fallbacks, no dataset scoping, no rule engine changes.
- Simple, initial working versions with minimal new code.

- Reference to current tagging model (for awareness):
  - Schema and rules live in `app/domain/tags.py` (TAG_SCHEMA, rules)
  - Enumerated values live in `app/domain/enums.py`
  - Canonicalization helper lives in `app/services/tagging_service.py#normalize_tag`

## Data model (Cosmos)

- Container: new Cosmos container for tags, configured via `COSMOS_CONTAINER_TAGS` (env var `GTC_COSMOS_CONTAINER_TAGS`).
- Partition key: `/pk` with a single logical partition value `"global"` (sufficient for a single-document registry and consistent with existing patterns that use `pk`).
- Document id: `tags|global`
- `docType`: `"tags"`
- Shape:
  ```json
  {
    "id": "tags|global",
    "docType": "tags",
    "pk": "global",
    "tags": ["source:sme", "topic:science"]  // canonical, deduped, sorted
  }
  ```
- Provisioning: created on startup if `COSMOS_CREATE_IF_NOT_EXISTS` is true; ensure DB and the new tags container exist.
- Concurrency: keep v1 simple with last-write-wins (no ETag flow).

## Existing tagging model — groups and values (reference only)

The application already defines a tag schema and rule engine used elsewhere. We won’t enforce these in v1 of the global registry endpoints (see “Out of scope”), but clients should prefer these groups/values for consistency. Sources:

- Schema: `app/domain/tags.py` (TAG_SCHEMA)
- Enums: `app/domain/enums.py`
- Normalization: `app/services/tagging_service.py` (normalize_tag)

Defined groups and values (E = exclusive, M = multi-select):

- source (E): sme, sa, synthetic, sme_curated, user, other
- split (E): validation, test
- judge_training (E, depends on split:train): train, validation
- answerability (E): answerable, not_answerable, should_not_answer
- topic (M): general, compatibility, part_modeling, fundamentals, sketcher, welding, simulation, cabling, other
- reference_type (M): article, document
- question_length (E): short, medium, long
- retrieval_behavior (E): no_refs, single, two_refs, rich
- intent (M): informational, action, feedback, clarification, other
- answer_type (M): factual, procedural, policy, other
- expertise (E): expert, novice
- turns (E): singleturn, multiturn
- difficulty (E): easy, medium, hard

Note: The rule engine includes exclusivity checks and a dependency that `judge_training` requires `split:train`. These are not validated by the new registry endpoints in this v1.

## Scope now

- List all global tags.
- Add one or more new tags.
- Remove one or more tags.
- Canonicalize format via existing helper; no schema/rule validation.

## Out of scope (explicitly deferred)

- Dataset-scoped schemas, extensions, or merges.
- TAG_SCHEMA-based validation and rule enforcement.
- Optimistic concurrency (ETags), caching, or pagination.
- Audit trails, per-group settings, or OpenAPI schema for rules.

## Files to add/change

- New: `app/adapters/repos/tags_repo.py`
  - Minimal Cosmos adapter for a single global tags document.
- New: `app/services/tag_registry_service.py`
  - Business logic: list/add/remove with canonicalization and dedupe/sort.
- Change: `app/api/v1/tags.py`
  - Add endpoints:
    - `GET /v1/tags` — list tags
    - `POST /v1/tags` — add tags
    - `DELETE /v1/tags` — remove tags
  - Keep existing `/v1/tags/schema` as-is.
- Change: `app/core/config.py`
  - Add `COSMOS_CONTAINER_TAGS: str` setting (env: `GTC_COSMOS_CONTAINER_TAGS`, e.g., `"tags"`).
- Change: `app/container.py`
  - Wire a Cosmos client handle for the new tags container; on startup `_init()`, create the container with partition key `/pk` when `COSMOS_CREATE_IF_NOT_EXISTS` is true.
- Change: `environments/.dev.env`, `environments/integration-tests.env`
  - Add `GTC_COSMOS_CONTAINER_TAGS=tags` (or project-specific name) for local/dev and tests.

## API additions

- DTOs
  - TagListResponse
    - `tags: list[str]`
  - AddTagsRequest
    - `tags: list[str]`
  - RemoveTagsRequest
    - `tags: list[str]`

- Handlers
  - GET `/v1/tags` -> TagListResponse
    - Return the current canonical global tag list (sorted).
  - POST `/v1/tags` -> TagListResponse
    - Add one or more tags; canonicalize, dedupe, persist; return updated list.
  - DELETE `/v1/tags` -> TagListResponse
    - Remove one or more tags; persist; return updated list.

- Errors
  - 400 on invalid tag format (missing colon or empty group/value).

## Functions and purposes

### Repository — `app/adapters/repos/tags_repo.py`

- get_global_tags() -> list[str]
  - Fetch the global tags document by `id="tags|global"`. If not found, return an empty list (do not create).
- save_global_tags(tags: list[str]) -> list[str]
  - Create or replace the global document with the provided list. Returns the saved list.
- upsert_add(tags_to_add: list[str]) -> list[str]
  - Read-modify-write: merge provided tags with stored tags (caller supplies canonical list); save and return updated list.
- upsert_remove(tags_to_remove: list[str]) -> list[str]
  - Read-modify-write: remove provided tags (caller supplies canonical list); save and return updated list.

### Service — `app/services/tag_registry_service.py`

- list_tags() -> list[str]
  - Return the canonical global tag list from the repo; ensure deterministic sort for stability.
- add_tags(tags: list[str]) -> list[str]
  - Normalize each tag via existing helper (`normalize_tag`), drop invalids with 400 at API boundary, dedupe and merge with existing, sort, persist, and return updated list.
- remove_tags(tags: list[str]) -> list[str]
  - Normalize inputs, filter existing set, sort, persist, and return updated list.
- normalize_and_canonicalize(tags: Iterable[str]) -> list[str]
  - Use `app.services.tagging_service.normalize_tag` to enforce `group:value` format, lowercase, trim; dedupe and sort.

### API — `app/api/v1/tags.py` (additions)

- get_tags() -> TagListResponse
  - Calls service.list_tags(); returns `{ "tags": [...] }`.
- post_tags(req: AddTagsRequest) -> TagListResponse
  - Calls service.add_tags(req.tags); returns `{ "tags": [...] }`.
- delete_tags(req: RemoveTagsRequest) -> TagListResponse
  - Calls service.remove_tags(req.tags); returns `{ "tags": [...] }`.

## Tests

### Unit — `tests/unit/test_tag_registry_service.py`
- test_list_initially_empty
  - Empty when document does not yet exist.
- test_add_single_tag_canonicalized_and_sorted
  - Whitespace/case normalized; appears once; sorted.
- test_add_duplicates_are_deduped
  - Adding same tag twice remains single instance.
- test_add_multiple_tags_merge_existing
  - Merge with stored set; deterministic ordering.
- test_remove_existing_tag
  - Present tag removed; list updated correctly.
- test_remove_nonexistent_tag_noop
  - Removing absent tag keeps state unchanged.
- test_invalid_format_rejected_by_service
  - Missing colon or empty group/value triggers error.

### Integration — `tests/integration/test_tags_registry_api.py`
- test_get_tags_empty_on_fresh_store
  - GET returns empty list initially.
- test_post_adds_and_returns_updated_list
  - POST adds; GET reflects new tags.
- test_delete_removes_and_returns_updated_list
  - DELETE removes; GET reflects removal.
- test_post_rejects_invalid_format_with_400
  - Bad tag strings yield client error.
- test_idempotency_add_remove_sequences
  - Repeated operations stay stable and deterministic.

## Keep it simple — implementation notes

- Reuse `app.services.tagging_service.normalize_tag` for consistent canonical form.
- Always sort the stored list lexicographically to stabilize responses and diffs.
- No reliance on TAG_SCHEMA or rule checks in v1 to avoid coupling.
- Store everything in a single document inside the new tags container to minimize round-trips and complexity.
- Security and auth: follow existing router patterns if already in place; otherwise defer to a later pass.
