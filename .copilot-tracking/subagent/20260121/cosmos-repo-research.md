# Cosmos repo + emulator mixing research (2026-01-21)

## Scope

Primary file: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py)

Related emulator/config wiring:
- [backend/app/container.py](backend/app/container.py)
- [backend/app/core/config.py](backend/app/core/config.py)
- [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md)
- [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md)
- [backend/app/adapters/repos/tags_repo.py](backend/app/adapters/repos/tags_repo.py)
- [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py)

Goal: produce an inventory of code blocks inside cosmos_repo.py, classify into A/B/C, and propose concrete override seams for a new emulator-specific repo module (`cosmos_emulator.py`) that subclasses (or wraps) the production repo.

---

## High-level finding

`CosmosGroundTruthRepo` currently mixes:

- Production Cosmos persistence concerns (SDK client creation, query construction, container calls, concurrency via ETags)
- Assignment/business workflow logic (sampling allocation, quota math, selection + de-biasing, user id validation)
- Emulator compatibility hacks (unicode sanitization, backslash sentinel, base64 refs encoding, EXISTS/ARRAY_CONTAINS workarounds, intermittent delete/upsert retries, conditional assignment via read-modify-replace)

This makes it hard to reason about “production correctness” separately from “emulator survivability”, and it forces emulator constraints (like no `EXISTS` in SQL) into the default repo surface.

---

## Inventory by category (line-cited)

### A) Pure persistence concerns

These blocks are “Cosmos adapter” responsibilities (query construction, paging/container calls, error mapping), and should remain in the repo layer.

1) Cosmos client/connection policy setup and async loop binding
- Connection policy + retry options built from settings: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L260-L300)
- Async client initialization and container client acquisition: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L302-L356)

2) Container existence validation with actionable error messages
- DB/container validation flow: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L358-L428)

3) Document serialization/deserialization and schema compatibility
- `_to_doc()` converts model to JSON-safe dict, sets UUID bucket string, ensures updatedAt, persists computed `totalReferences`: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L386-L454)
- `_from_doc()` normalizes fetched doc, handles legacy `history=None`, validates to model: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L456-L474)

4) Query construction primitives and safe sort clause construction
- Filter builder (status/dataset/item_id/tags/ref_url): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L526-L605)
- Sort resolution + stable in-memory sort key: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L607-L671)
- ORDER BY clause constructed via fixed mapping (no raw user input): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L679-L724)

5) Paginated read path (production Cosmos)
- Direct query path with ORDER BY + OFFSET/LIMIT, then a second query for total count: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L726-L814)

6) Counting logic
- Tag-aware count (SQL count for prod, in-memory tag check for emulator): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L913-L1043)
- Non-tag count uses `SELECT VALUE COUNT(1)` to avoid the “NonValueAggregate” plan issue: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1045-L1107)

7) Basic CRUD paths
- List-by-dataset query (includes docType exclusion for curation docs): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1109-L1135)
- `get_gt()` read-item by hierarchical partition key: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1137-L1154)
- Curation instruction upsert with conditional replace by ETag: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1188-L1275)
- Assignment document CRUD in secondary container: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1841-L1989)


### B) Business/service logic (should be moved out)

These blocks encode *workflow rules* and *domain-level decisions* rather than storage mechanics. They can be preserved, but should move to service layer(s).

1) Total reference semantics are domain/business logic
- `totalReferences` is derived from either history refs or item refs, and the repo mutates the model during persistence: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L367-L385) and [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L386-L413)

Why this is service logic:
- It encodes a product/business definition (“history refs take priority”) and impacts UI/filters.
- The adapter shouldn’t be responsible for deciding business meaning; it should persist what it’s given.

Suggested owner:
- A new `GroundTruthDerivationsService` (or fold into existing `CurationService` / “ground truth service” if present).

Suggested signatures:
- `class GroundTruthDerivationsService:`
  - `def compute_total_references(self, item: GroundTruthItem) -> int`
  - `def apply_derived_fields(self, item: GroundTruthItem) -> GroundTruthItem` (sets `totalReferences`, possibly `questionLength`, etc.)

2) Sampling allocation, quotas, and selection are assignment workflow
- The repo contains a full sampling/selection algorithm including:
  - fetching already-assigned items first
  - reading sampling allocation config
  - quota computation via largest remainder
  - per-dataset candidate queries
  - round-robin interleave + final global fill
  - shuffling to debias query ordering
  [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1388-L1600)
- Quota computation helper is pure allocation math: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1681-L1716)

Why this is service logic:
- These are product-level rules about how to distribute assignment opportunities.
- It is hard to test in isolation when buried in the persistence adapter.

Suggested owner:
- `AssignmentService` already exists and is the natural owner. It currently orchestrates `self_assign()` and retries by excluding seen IDs: [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L44-L152)

Suggested refactor:
- Move sampling algorithm out of repo into `AssignmentService` (or a new `AssignmentSamplingService` used by `AssignmentService`).

Suggested signatures:
- `class AssignmentSamplingService:`
  - `async def sample_candidates(self, *, user_id: str, limit: int, exclude_ids: list[str] | None = None) -> list[GroundTruthItem]`
  - `def compute_quotas(self, weights: dict[str, float], k: int) -> dict[str, int]`

Repository then exposes *only* persistence queries:
- `async def list_unassigned_candidates_global(self, *, user_id: str, limit: int, exclude_ids: list[str] | None) -> list[GroundTruthItem]`
- `async def list_unassigned_candidates_by_dataset_prefix(self, *, dataset_prefix: str, user_id: str, limit: int, exclude_ids: list[str] | None) -> list[GroundTruthItem]`

3) Input validation of `user_id` belongs in API/service
- Repo rejects user IDs not matching a regex: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1718-L1743)

Why this is service logic:
- Validation semantics (“allowed chars”) are part of API contract; the repo should not have to know.

Suggested owner:
- `AssignmentService` (or API layer) should validate `user_id` before calling repository.

Suggested signature:
- `def validate_user_id(self, user_id: str) -> None` (raise a typed error) or return `bool`.


### C) Emulator / compatibility hacks

These blocks exist specifically because the emulator’s behavior differs from production Cosmos DB.

1) Unicode/control-char sanitization, invalid backslash escaping, and restoration
- Smart punctuation replacements + escape/backslash handling helpers: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L29-L118)
- Recursive normalization (emulator-only) and restore (sentinel back to backslash): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L121-L219)
- The public “intent wrapper” `_ensure_utf8_strings()` used by writes: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L430-L454)

Note: The repo also adds a *second* workaround by base64-encoding `refs[*].content` to avoid emulator rejection of “certain character sequences”: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L53-L104) and [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L148-L176)

2) SQL feature gaps: emulator incompatibilities drive in-memory filtering
- `list_gt_paginated()` routes to emulator path when `tags` or `ref_url` are present and endpoint is localhost: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L748-L770)
- Emulator pagination path disables SQL tag/ref_url filters (no ARRAY_CONTAINS strategy / no EXISTS) then filters in memory: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L816-L912)

This is consistent with the emulator limitations doc:
- [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md#L1-L39)

3) Conditional assignment: patch in production, read-modify-replace in emulator
- Environment detection: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L671-L677)
- `assign_to()` routes to emulator vs production implementation: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1718-L1752)
- Production implementation uses `patch_item` with non-parameterized filter_predicate (string interpolation): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1754-L1838)
- Emulator implementation uses read-modify-replace: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1840-L1980)

Related design note:
- [backend/CONDITIONAL_PATCH_IMPLEMENTATION.md](backend/CONDITIONAL_PATCH_IMPLEMENTATION.md#L1-L52)

4) Retry logic for emulator intermittent errors + payload sanitization retry
- `upsert_gt()` includes special retry paths for:
  - `etag_mismatch` mapping
  - intermittent emulator “jsonb type as object key” errors
  - emulator invalid JSON payload errors triggering a sanitize-and-retry
  [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1277-L1402)
- `delete_dataset()` includes emulator-only retry for jsonb/HTTP-format errors, plus retry on deleting curation doc: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1422-L1525)

---

## Related emulator knobs and behaviors (outside cosmos_repo.py)

1) Settings flags and Cosmos knobs
- Emulator flags + unicode escape toggle live in Settings: [backend/app/core/config.py](backend/app/core/config.py#L28-L56)

2) DI container currently always uses `CosmosGroundTruthRepo`
- Repo wiring picks `CosmosGroundTruthRepo` and only uses endpoint scheme / `USE_COSMOS_EMULATOR` to decide AAD vs key auth, not to change repo class: [backend/app/container.py](backend/app/container.py#L86-L138)

3) Tags repo exists separately and does not currently apply the unicode workaround
- `CosmosTagsRepo.save_global_tags()` does a plain upsert without `_ensure_utf8_strings`: [backend/app/adapters/repos/tags_repo.py](backend/app/adapters/repos/tags_repo.py#L93-L124)

This matters because [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L111-L128) claims tags repo applies normalization; code appears to have drifted.

---

## Proposed refactor direction

### Objective

Create a clean production repo with no emulator branches in hot paths, and move emulator constraints into a separate implementation in `backend/app/adapters/repos/cosmos_emulator.py`.

### Recommended shape

1) Production repo remains `CosmosGroundTruthRepo`
- Keep only production-correct Cosmos SQL usage and patch-based assignment.
- Keep generic retry policy based on Cosmos SDK RetryOptions (already configured in connection policy).

2) New emulator repo: `CosmosEmulatorGroundTruthRepo`
- Subclass `CosmosGroundTruthRepo` and override only the minimal behavior differences.
- Keep emulator-only sanitization and retry logic local to emulator class.

3) Move B-category logic into services
- Sampling/quotas to `AssignmentService` (or `AssignmentSamplingService`)
- Derived fields like `totalReferences` to a derivations service

---

## Exact override seams for `cosmos_emulator.py`

### Suggested class name

`CosmosEmulatorGroundTruthRepo`

### Suggested constructor signature

Keep it 1:1 with production to minimize DI churn:

- `def __init__(self, endpoint: str, key: str | None, db_name: str, gt_container_name: str, assignments_container_name: str, connection_verify: bool | str | None = None, test_mode: bool = False, credential: Any | None = None) -> None`

(Optionally add `*, emulator_flags: EmulatorFlags | None = None` only if you want to decouple from global `settings`.)

### Minimal subclass surface (recommended)

Override these methods/properties only:

1) Environment detection
- `def is_cosmos_emulator_in_use(self) -> bool`
  - Return `True` unconditionally in the emulator subclass to eliminate endpoint string checks.

2) Document transforms
- Add hook methods in the *production* base class (or override existing wrapper):
  - `def _pre_write_transform(self, doc: dict[str, Any]) -> dict[str, Any]`
  - `def _post_read_transform(self, doc: dict[str, Any]) -> dict[str, Any]`

In the emulator subclass:
- `_pre_write_transform` applies:
  - unicode/control-char sanitization
  - backslash sentinel substitution
  - base64 refs content encoding
  - (optional) `json.dumps(..., ensure_ascii=True)` roundtrip if needed for emulator
- `_post_read_transform` applies restore + base64 decode

These behaviors are currently spread across:
- [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L53-L219)
- Used in write paths like import/upsert/curation/assignment docs: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L494-L513) and [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1234-L1272) and [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1912-L1934)

3) Pagination capability differences
- `async def list_gt_paginated(...)`
  - Emulator subclass should route to `_list_gt_paginated_with_emulator` whenever `tags` or `ref_url` are present.
  - Production base class keeps the direct SQL path.

Currently: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L748-L770)

4) Assignment method
- `async def assign_to(self, item_id: str, user_id: str) -> bool`
  - Emulator subclass forces read-modify-replace flow.
  - Production base forces patch flow.

Currently: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1718-L1980)

5) Emulator-only retry policy for deletes/upserts
- `async def upsert_gt(...)` and `async def delete_dataset(...)`
  - Emulator subclass retains the intermittent emulator bug retries.
  - Production base can keep ETag handling and rely on SDK retry options, avoiding emulator-specific message matching.

Currently:
- Upsert retry + sanitize retry: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1277-L1402)
- Delete dataset retry: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1422-L1525)

If you want an even smaller surface, introduce a single overridable policy method:
- `def _should_retry_emulator_exception(self, exc: Exception) -> bool`
And keep retry loops in base calling it.

---

## DI container & invariants

### DI wiring change required

`Container.init_cosmos_repo()` currently always constructs `CosmosGroundTruthRepo`: [backend/app/container.py](backend/app/container.py#L86-L138)

To adopt subclassing cleanly, `init_cosmos_repo` should choose:
- `CosmosEmulatorGroundTruthRepo` when `settings.USE_COSMOS_EMULATOR` is true or endpoint is non-TLS local emulator
- `CosmosGroundTruthRepo` otherwise

Invariants to preserve:
- Same constructor args for both repos, so container swap is trivial.
- `await repo._init()` must still be called on startup (lifespan/startup path relies on async client binding).

### Tests likely to be impacted

1) Unicode tests import the private normalization function directly
- [backend/tests/unit/test_unicode_fix.py](backend/tests/unit/test_unicode_fix.py#L10-L12)

If normalization moves to emulator module, either:
- keep `_normalize_unicode_for_cosmos` exported from cosmos_repo.py as a compatibility shim, or
- update tests to import from emulator module.

2) Unit tests validate `_build_query_filter` tag clause uses `ARRAY_CONTAINS`
- [backend/tests/unit/test_cosmos_repo.py](backend/tests/unit/test_cosmos_repo.py#L33-L58)

If you split production vs emulator query builders, keep production semantics in `CosmosGroundTruthRepo._build_query_filter` and put emulator differences behind `list_gt_paginated` routing (recommended), so tests remain valid.

3) Assignment tests may depend on selection behavior
- `AssignmentService` already retries with `exclude_ids`; repo sampling also supports `exclude_ids` via query building. Refactor must maintain that exclusion contract.

---

## Recommendation snapshot

- Move B-category logic out of [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py):
  - `sample_unassigned` + `_compute_quotas` → `AssignmentService` / `AssignmentSamplingService`
  - `totalReferences` derivation → a derivations service (or domain model)
  - `user_id` validation → API/service
- Keep A-category logic in the repo.
- Create `CosmosEmulatorGroundTruthRepo` in `cosmos_emulator.py` and concentrate C-category logic there, with the override seams listed above.
