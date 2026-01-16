---
title: Manual Tags Design Research
description: Verified findings and references for implementing manual-tags design in GroundTruthCurator
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

## Scope

This research covers the current and intended design for **manual tags** in Ground Truth Curator, including:

* Storage shape and validation rules
* Manual tag discovery (schema + registry + optional allowlist)
* API surface consumed by the frontend
* Cosmos DB persistence model for global tag registry
* Known interaction points with computed tags

## Workspace reconnaissance (verified)

### Tool usage (evidence collection)

The findings above were collected using repository-wide searches and direct file inspection:

* `grep_search` for `manualTags`, `computedTags`, `ALLOWED_MANUAL_TAGS`, `TagValidator`, and related symbols
* `read_file` of the concrete implementations and tests listed below
* `fetch_webpage` for the external FastAPI/Pydantic/Cosmos DB references

### Key backend files

* `backend/app/domain/models.py`
  * `GroundTruthItem.manual_tags` stored as `manualTags`.
  * `GroundTruthItem.computed_tags` stored as `computedTags`.
  * `GroundTruthItem.tags` is a computed union for reads.

* `backend/app/domain/validators.py`
  * Pydantic v2 field validators coerce `manual_tags` and validate via `validate_tags()`.
  * `computed_tags` are coerced only (no user validation).

* `backend/app/services/tagging_service.py`
  * Canonicalization rules (`normalize_tag`) enforce `group:value` format.
  * `validate_tags()` enforces exclusivity/dependency rules for **known** groups.
  * Unknown groups/values are allowed (format still required).
  * `validate_tags_with_cache()` provides a stricter mode: manual tags must exist in a provided allow-set.

* `backend/app/domain/tags.py`
  * Defines `TAG_SCHEMA` for known groups and value sets.
  * Defines rule plugins (`ExclusiveGroupRule`, `DependencyRule`) applied by `validate_tags()`.

* `backend/app/api/v1/tags.py`
  * `GET /v1/tags/schema` returns `TAG_SCHEMA` for frontend rendering and client-side validation.
  * `GET /v1/tags` returns manual tags in `tags` plus computed tag keys in `computedTags`.
  * When `GTC_ALLOWED_MANUAL_TAGS` is set, `GET /v1/tags` uses it as the manual-tag source-of-truth.

* `backend/app/services/tag_registry_service.py`
  * Implements add/remove/list over a single global tag list.

* `backend/app/adapters/repos/tags_repo.py`
  * Cosmos implementation stores a single document `id="tags|global"` in the tags container.
  * Partition key `/pk` uses constant value `"global"`.

* `backend/app/main.py`
  * Startup fails fast if `GTC_ALLOWED_MANUAL_TAGS` overlaps static computed tag keys.

### Key frontend files

* `frontend/src/services/tags.ts`
  * Fetches `GET /v1/tags/schema` and validates exclusive groups client-side.
  * Fetches `GET /v1/tags` and uses `tags` as manual tags and `computedTags` as computed tags.

### Tests demonstrating current behavior

* `backend/tests/unit/test_groundtruthitem_tags_validation.py`
  * Confirms unknown groups are allowed for `manualTags`.
  * Confirms exclusive groups (e.g., `source:*`) reject multiple values.

* `backend/app/services/validation_service.py`
  * Bulk import validation uses `validate_tags_with_cache()` and the tag registry as the allow-set.

## Current behavior summary (evidence-based)

### Code excerpts (current patterns)

Pydantic v2 validators on `manual_tags` enforce normalization + rule checks:

```python
@field_validator("manual_tags", mode="before")
@classmethod
def _coerce_manual_tags(_cls, v: Any) -> list[str]:
  return coerce_tags(v)

@field_validator("manual_tags", mode="after")
@classmethod
def _validate_manual_tags(_cls, v: list[str]) -> list[str]:
  return validate_tags(v)
```

The tags API returns manual tags and computed tag keys separately, with an env override for manual tags:

```python
if settings.ALLOWED_MANUAL_TAGS:
  manual_tags = [t.strip() for t in settings.ALLOWED_MANUAL_TAGS.split(",") if t and t.strip()]
else:
  manual_tags = await container.tag_registry_service.list_tags()

computed_tag_keys = sorted(get_default_registry().get_static_keys())
return TagListResponse(tags=sorted(manual_tags), computedTags=computed_tag_keys)
```

### Canonical format

* Tags must be `group:value`.
* Canonicalization lowercases, trims whitespace, normalizes `group : value` to `group:value`, and removes empty group/value.

### Validation policy (two-tier)

* **Default API/model validation (relaxed):**
  * Accepts unknown groups and unknown values.
  * Enforces exclusivity/dependency rules only for known groups in `TAG_SCHEMA`.

* **Bulk import validation (strict allow-set):**
  * Requires all manual tags to exist in the global tag registry set.
  * Still enforces exclusivity/dependency rules.

### Manual tag discovery sources

Manual tags shown to the UI come from one of:

* `GTC_ALLOWED_MANUAL_TAGS` (CSV) when set.
* Otherwise, the global tag registry (`TagRegistryService` backed by memory or Cosmos).

Known schema groups/values are also provided independently via `GET /v1/tags/schema`.

### Global tag registry storage

* Cosmos tags container stores a single global doc:
  * `id = "tags|global"`
  * `pk = "global"`
  * `tags = ["group:value", ...]`

This is intentionally simple and matches current API semantics (global tags, not per-dataset).

## Gaps / decision points to resolve in the manual-tags “design”

These are the key choices that affect implementation work:

1. **Should runtime writes (PUT ground truths / assignments) be strict allow-set, or remain relaxed?**
   * Current behavior is relaxed for normal writes, strict for bulk import.

2. **What is the long-term source of truth for “allowed manual tags”?**
   * Current options: env allowlist or global registry.
   * A provider abstraction is partially implemented via `GTC_ALLOWED_MANUAL_TAGS` override, but not expressed as a formal interface.

3. **Do we need per-dataset or per-tenant tag registries?**
   * Current registry is global.

4. **How should manual tags interact with computed tags?**
   * Startup checks prevent allowlist collisions with computed tags.
   * Write path strips computed tags from manual tags during `apply_computed_tags()`.

## External references (for implementation correctness)

* Pydantic v2 validators (`field_validator`, before/after modes):
  * <https://docs.pydantic.dev/latest/concepts/validators/>

* FastAPI `response_model` behavior and filtering:
  * <https://fastapi.tiangolo.com/tutorial/response-model/>

* Cosmos DB partitioning and logical partition limits (relevant for global tags container design):
  * <https://learn.microsoft.com/azure/cosmos-db/partitioning-overview>
