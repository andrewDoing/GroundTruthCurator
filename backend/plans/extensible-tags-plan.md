# Extensible Tags Plan

## Overview

We will replace the hard-coded, enum-driven tag schema with a configuration-driven, runtime-extendible taxonomy. Built-in defaults will live in the repo as JSON. Runtime-extended tags will be DATASET-SCOPED and stored alongside each dataset’s documents in the same Cosmos container as ground-truth items, using the NIL UUID bucket (`00000000-0000-0000-0000-000000000000`) just like curation instructions. Validation and tag editing will read the authoritative schema from Cosmos each time (no server-side caching); clients may cache locally but must re-fetch to read the source of truth. We’ll enforce exclusivity and simple dependencies. Minimal API/service surface will allow adding tags at runtime; no legacy fallback paths.

## Implement only what we need right now

Implement the following minimal scope:
- Load default tag groups/values/constraints from a repo JSON file.
- Read a DATASET tag-extension document from the Ground Truth Cosmos container; merge with defaults.
- Validate tags (group:value) using merged schema; enforce exclusive groups and simple dependencies.
- Upsert tags honoring exclusivity with the merged schema.
- Allow runtime extension to add a new value to an existing group and to create a new group (mutates the dataset-scoped extension document). Use optimistic concurrency via Cosmos ETag.
- Do not implement server-side caching; always read from Cosmos on validation and on API GET. Clients can cache their view but must re-fetch to obtain the authoritative schema.

Defer (not implemented now): UI, authorization model, complex dependency logic, multi-tenant isolation beyond datasetName, bulk migrations, and tag deletion.

## Files to change or create

Change (refactor to schema-based):
- `app/domain/tags.py`: Keep `TagGroupSpec`, `Rule`s, but remove hard-coded `TAG_SCHEMA`. Add parse-from-JSON helpers.
- `app/services/tagging_service.py`: Switch to DATASET-SCOPED schema provider (dataset is required to determine allowed values); keep normalize/parse/upsert logic.
- `app/domain/validators.py`: Validate using dataset-scoped schema service (requires datasetName).
- `app/domain/models.py`: Ensure datasetName is available wherever tags are validated; thread datasetName into validator calls if not already present.

Create:
- `app/adapters/repos/tags_repo.py`: Repository interface and Cosmos implementation for the DATASET-SCOPED tag extension document stored in the existing Ground Truth container.
- `app/domain/tag_schema.defaults.json`: Default groups/values/exclusive/depends_on (ported from current enums/schema), kept minimal.
- `app/services/tag_schema_provider.py`: Provider with merge (no cache); surface `get_schema(dataset: str)` and extension methods that require dataset.
- `app/api/v1/datasets/tags.py` (minimal): Read-only list endpoint and POST to extend tags (value or group) for a dataset.
- `tests/unit/test_tag_schema_provider.py`, `tests/unit/test_tagging_service_dynamic.py`, `tests/unit/test_validators_dataset_tags.py`.
- `tests/integration/test_tags_repo_cosmos.py` (emulator-backed or using existing test harness).

## Data model and merge rules

Defaults JSON (repo): Keep very small and stable. Only foundational groups remain in defaults; most existing groups/values will be moved to the dataset extension document.
```
{
  "schemaVersion": "v1",
  "groups": [
    {"name": "source", "exclusive": true, "values": ["sme", "sa", "synthetic", "sme_curated", "user", "other"]},
    {"name": "split", "exclusive": true, "values": ["validation", "test"]},
    {"name": "judge_training", "exclusive": true, "values": ["train", "validation"], "depends_on": [["split", "validation"]]},
    {"name": "answerability", "exclusive": true, "values": ["answerable", "not_answerable", "should_not_answer"]},
    {"name": "topic", "exclusive": false, "values": ["general", "compatibility", "part_modeling", "fundamentals", "sketcher", "welding", "simulation", "cabling", "other"]},
    {"name": "reference_type", "exclusive": false, "values": ["article", "document"]},
    {"name": "question_length", "exclusive": true, "values": ["short", "medium", "long"]},
    {"name": "retrieval_behavior", "exclusive": true, "values": ["no_refs", "single", "two_refs", "rich"]},
    {"name": "intent", "exclusive": false, "values": ["informational", "action", "feedback", "clarification", "other"]},
    {"name": "answer_type", "exclusive": false, "values": ["factual", "procedural", "policy", "other"]},
    {"name": "expertise", "exclusive": true, "values": ["expert", "novice"]},
    {"name": "turns", "exclusive": true, "values": ["singleturn", "multiturn"]},
    {"name": "difficulty", "exclusive": true, "values": ["easy", "medium", "hard"]}
  ]
}
```

Dataset extension document (Cosmos, same container as ground-truth items):
```
{
  "id": "tags|{datasetName}",
  "datasetName": "{datasetName}",
  "bucket": 0,
  "docType": "tags",
  "schemaVersion": "v1",
  "groups": [
    // Move most current groups/values here for each dataset; may introduce new groups or add values
    {"name": "topic", "values": ["general", "compatibility", "part_modeling", "fundamentals", "sketcher", "welding", "simulation", "cabling", "other", "assembly", "manufacturing"]},
    {"name": "customer_specific", "exclusive": false, "values": ["acme", "contoso"]}
  ],
  "updatedAt": "...",
  "updatedBy": "...",
  "_etag": "..."
}
```

Merge strategy:
- Start with defaults. Overlay DATASET extension groups/values:
  - If the group exists in defaults: union values; extension cannot flip `exclusive` for existing groups (attempt rejected now for simplicity).
  - If the group does not exist: create it with provided `values`, `exclusive`, and optional `depends_on`.
- Dependencies: union any `depends_on` provided by extension for existing groups; no removal in this phase.

## Function and class contracts

Service/provider layer (new in `app/services/tag_schema_provider.py`):
- class TagSchemaProvider
  - get_schema(dataset: str) -> dict[str, TagGroupSpec]
    Returns merged, authoritative DATASET schema; loads defaults + dataset extension from Cosmos every call (no caching).
  - extend_value(dataset: str, group: str, value: str, actor: str) -> dict
    Adds value to an existing (or creates a new) group in the DATASET extension doc; returns updated document. Optimistic concurrency with ETag.
  - extend_group(dataset: str, spec: TagGroupSpec, actor: str) -> dict
    Adds a brand-new group (name, values, exclusive, depends_on) to the DATASET extension doc.
  - load_defaults() -> dict[str, TagGroupSpec]
    Reads `tag_schema.defaults.json` and converts to in-memory schema.
  - merge(defaults, extension) -> dict[str, TagGroupSpec]
    Deterministic merge per rules above.

Repository (new in `app/adapters/repos/tags_repo.py`):
- interface TagsRepo
  - get_dataset_extension(dataset: str) -> (doc: dict | None, etag: str | None)
    Fetch DATASET extension document (`id = "tags|{dataset}"`, `bucket = 0`, `docType = "tags"`) from the Ground Truth container; returns current ETag.
  - upsert_dataset_extension(dataset: str, mutate: callable, expected_etag: str | None) -> (doc: dict, etag: str)
    Apply mutation to groups atomically via Cosmos replace/upsert with If-Match; raise on ETag conflict.

Tagging service (`app/services/tagging_service.py`):
- normalize_tag(tag: str) -> str
  Normalize case/whitespace and enforce group:value format.
- parse_tag(tag: str) -> tuple[str, str]
  Split normalized tag into (group, value).
- validate_tags_dataset(dataset: str, tags: Iterable[str]) -> list[str]
  Validate using DATASET schema from provider; enforce exclusivity and dependencies; raise on unknowns.
- upsert_tag_dataset(dataset: str, tags: Iterable[str], group: str, value: str) -> list[str]
  Add/replace tag respecting exclusivity; revalidate via DATASET schema.
- allowed_tag_groups(dataset: str) -> dict[str, set[str]]
  Return groups->values for UI/help from DATASET schema.

Validators (`app/domain/validators.py`):
- GroundTruthItemTagValidators._validate_tags(dataset: str, ...) -> list[str]
  Change to call `validate_tags_dataset` (requires dataset parameter).

API (minimal; `app/api/v1/datasets/tags.py`):
- GET /api/v1/datasets/{dataset}/tags
  Returns DATASET groups and values. Supports conditional GET via `If-None-Match` to leverage client caching.
- POST /api/v1/datasets/{dataset}/tags/extend-value
  Body: { group, value }; calls provider.extend_value(dataset,...). Uses ETag for optimistic concurrency when header `If-Match` is provided.
- POST /api/v1/datasets/{dataset}/tags/extend-group
  Body: { name, exclusive, values, depends_on? }.

## Tests to add (names and brief coverage)

Unit: `tests/unit/test_tag_schema_provider.py`
- test_merge_adds_values_existing_group — adds values to default group.
- test_merge_creates_new_group — new group created with properties.
- test_no_flip_exclusive_existing_group — reject exclusive change on existing.
- test_dependencies_union_behavior — extension adds new dependency entries.
- test_reads_authoritative_each_call — provider does not cache between calls.

Unit: `tests/unit/test_tagging_service_dynamic.py`
- test_validate_known_default_tags — defaults accept current tags in defaults.
- test_reject_unknown_value_without_extension — unknown value rejected initially.
- test_accept_value_after_extension — dataset extension enables new value.
- test_exclusive_rule_enforced_dataset_scope — only one value in exclusive within dataset.
- test_dependency_rule_enforced — requires split:train with judge_training.

Unit: `tests/unit/test_validators_dataset_tags.py`
- test_model_validator_uses_dataset_schema — dataset provider used for validation.
- test_invalid_tags_raise_value_error — user error surfaced clearly.

Integration: `tests/integration/test_tags_repo_cosmos.py`
- test_upsert_extension_etag_conflict — concurrent write conflict detected.
- test_read_write_roundtrip_extension_doc — extension persists and loads correctly using `bucket=0` and `id="tags|{dataset}"`.

API (optional minimal): `tests/integration/test_api_tags.py`
- test_list_tags_returns_merged_schema — GET returns merged groups/values for dataset.
- test_extend_value_writes_and_lists — POST extends then GET reflects change for dataset; validates ETag/If-Match behavior.

## Storage: dataset-scoped tags in existing Ground Truth container

- Reuse the existing Ground Truth Cosmos container (same as ground-truth items and curation instructions).
- Partitioning: use the standard datasetName + bucket partitioning. Store the dataset-level tags document with `bucket = 0` (NIL UUID) for MultiHash PK compatibility.
- Document identity: `id = "tags|{datasetName}", docType = "tags", datasetName = {datasetName}`.
- Consistency and concurrency: use ETag optimistic concurrency; writes include `If-Match` on current ETag; clients retry on 412.

## Moving current tags into the dataset extension

- Keep defaults minimal (e.g., only structural/system groups if any). Move most of the currently defined groups/values from `app/domain/enums.py`/`app/domain/tags.py` into each dataset’s extension document on initialization/migration (or seed per dataset on first access):
  - source, split, judge_training, answerability, topic, reference_type, question_length, retrieval_behavior, intent, answer_type, expertise, turns, difficulty.
- Provide a one-time migration script to seed the dataset extension document from the current schema for existing datasets (idempotent: unions with existing values).

## Edge cases and decisions now

- Group naming/normalization: groups/values are lowercase, trimmed, and normalized; identical to tag normalization rules.
- Exclusive flips: disallowed for existing default groups to avoid breaking semantics; allowed only for groups created in extension doc.
- Deletions: not supported now (plan to add tombstones later); validation will accept tags only present in merged schema.
- Concurrency: one-writer-wins via If-Match ETag; client retries.
- Caching: none on the server; always read from Cosmos. Clients may use conditional GET with ETag for efficiency.

## Out of scope / next steps

- Admin/role checks for who can extend tags.
- UI flows and bulk import/export of tag taxonomies.
- Dataset-level “lock”/freeze of taxonomy for reproducibility.
- Tag removal and migration tooling.
