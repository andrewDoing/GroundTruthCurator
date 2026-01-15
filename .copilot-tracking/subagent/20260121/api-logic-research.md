---
title: API logic research
description: Candidates for moving business logic out of FastAPI handlers into service-layer modules
author: GitHub Copilot
ms.date: 2026-01-21
ms.topic: reference
keywords:
  - fastapi
  - service layer
  - refactor
  - concurrency
  - etag
  - tags
estimated_reading_time: 8
---

## Goal

Identify backend API endpoints that contain business logic beyond orchestration, and map that logic to service-layer boundaries.

## Summary of findings

* Several handlers in `backend/app/api/v1/*` perform domain workflows directly against `container.repo`.
* The heaviest duplication centers on:
  * Partial-update semantics across multiple fields
  * ETag enforcement and error mapping
  * Tag constraints and computed-tag recomputation
  * History parsing (including references embedded in history)
* Services already exist for several chunks of this logic (`AssignmentService`, `TaggingService`, `ValidationService`, `TagRegistryService`, `SnapshotService`, `ChatService`), but handlers still own cross-cutting workflow steps.

## Service boundary guidance

* API layer responsibilities
  * Authenticate and authorize
  * Parse inputs, perform lightweight request-shape validation
  * Translate service errors to HTTP status codes
* Service layer responsibilities
  * Domain workflows and state transitions
  * Concurrency rules (ETag requirements) and retryable failures
  * Tag normalization, manual tag constraints, computed-tag recomputation
  * Shared parsing/normalization of payload fields that appear across endpoints

## Endpoint candidates

### 1) SME assignment update workflow

File: `backend/app/api/v1/assignments.py`

Excerpt: [backend/app/api/v1/assignments.py#L72-L255](backend/app/api/v1/assignments.py#L72-L255)

What is happening in the handler:

* Joins multiple concerns:
  * Ownership enforcement (`assignedTo` must match caller)
  * Partial-update semantics driven by `model_fields_set`
  * Approval/status transitions that clear assignment and set review metadata
  * Parsing and validating `history` with embedded `refs`
  * ETag enforcement via `If-Match` or body `etag` and mapping mismatch to HTTP 412
  * Computed tag application before persisting
  * Best-effort deletion of the assignment document after completion

Service extraction candidates:

* Move domain workflow into `AssignmentService` or a new `GroundTruthUpdateService`
  * `update_assigned_item(dataset: str, bucket: UUID, item_id: str, user_id: str, update: AssignmentUpdateRequest, if_match: str | None) -> GroundTruthItem`
  * Keep the API handler responsible for request parsing only
* Extract shared helpers for use by both assignments and ground-truth CRUD:
  * `parse_history(payload_history: list[dict[str, Any]] | None) -> list[HistoryItem] | None`
  * `require_etag(if_match: str | None, body_etag: str | None) -> str`

Notes on existing services:

* `apply_computed_tags` already exists in `app/services/tagging_service.py` and is called here from the handler
* The handler still owns the workflow steps and error mapping that are likely to be repeated elsewhere

### 2) Single-item assignment orchestration

File: `backend/app/api/v1/assignments.py`

Excerpt: [backend/app/api/v1/assignments.py#L257-L323](backend/app/api/v1/assignments.py#L257-L323)

What is happening in the handler:

* Delegates assignment to `container.assignment_service.assign_single_item`
* Contains business-ish translation logic that likely belongs in a consistent error mapper:
  * Converts different `ValueError` message substrings to 404 vs 409 vs 400

Service extraction candidates:

* Keep `AssignmentService.assign_single_item` as-is, but standardize errors:
  * Prefer typed exceptions (e.g., `NotFoundError`, `AlreadyAssignedError`, `InvalidStateError`) so HTTP mapping is stable and not substring-based

### 3) Bulk import workflow

File: `backend/app/api/v1/ground_truths.py`

Excerpt: [backend/app/api/v1/ground_truths.py#L54-L127](backend/app/api/v1/ground_truths.py#L54-L127)

What is happening in the handler:

* Implements a full workflow, not just orchestration:
  * Generates IDs for missing items using `randomname`
  * Validates all items via `validate_bulk_items` and filters invalid items
  * Optionally applies approval metadata for all surviving items
  * Applies computed tags for each item (fetches registry once)
  * Persists through `container.repo.import_bulk_gt`

Service extraction candidates:

* Move into a dedicated import service (or a `GroundTruthService`):
  * `import_bulk(items: list[GroundTruthItem], *, buckets: int | None, approve: bool, user_id: str | None) -> ImportBulkResponse`
* Explicitly separate concerns:
  * ID generation and order preservation
  * Validation and error aggregation
  * Approval metadata policy
  * Tag recomputation policy

Notes on existing services:

* `validate_bulk_items` is in `app/services/validation_service.py`
* Computed-tag logic is in `app/services/tagging_service.py`
* The handler currently coordinates all these pieces and should become a thin wrapper

### 4) Ground-truth list query validation

File: `backend/app/api/v1/ground_truths.py`

Excerpt: [backend/app/api/v1/ground_truths.py#L160-L252](backend/app/api/v1/ground_truths.py#L160-L252)

What is happening in the handler:

* Implements query normalization and validation rules:
  * Coerces `status` string into `GroundTruthStatus`
  * Validates `limit` and `page`
  * Trims `itemId` and `refUrl`, enforces max lengths
  * Parses comma-separated `tags` with max tag count and max length

Service extraction candidates:

* Keep low-level validation here if it stays purely request-level, but consider extracting for reuse:
  * `normalize_list_query(status: str | None, item_id: str | None, ref_url: str | None, tags: str | None, page: int, limit: int) -> NormalizedQuery`

### 5) Ground-truth update workflow

File: `backend/app/api/v1/ground_truths.py`

Excerpt: [backend/app/api/v1/ground_truths.py#L283-L394](backend/app/api/v1/ground_truths.py#L283-L394)

What is happening in the handler:

* Repeats many of the same concerns as the assignments update endpoint:
  * Partial updates across multiple fields (including status coercion)
  * Reference parsing from list payloads
  * Explicit rejection of `computedTags` and legacy `tags` (business rule)
  * Manual tag update, mapped through domain validation
  * History parsing, including parsing `refs` and `expectedBehavior`
  * ETag requirement and mismatch mapping to HTTP 412
  * Computed tag application before persisting
  * Re-fetching to return latest ETag

Service extraction candidates:

* Create a shared update service used by both SME and admin-like updates:
  * `update_item(dataset: str, bucket: UUID, item_id: str, payload: dict[str, Any], *, if_match: str | None, user_id: str | None) -> GroundTruthItem`
* Consolidate shared parsing/validation helpers with the SME update handler:
  * History parsing and reference parsing
  * ETag policy enforcement and mismatch translation
  * Tag-field acceptance policy (manual-only)

### 6) Bulk recompute computed tags

File: `backend/app/api/v1/ground_truths.py`

Excerpt: [backend/app/api/v1/ground_truths.py#L408-L504](backend/app/api/v1/ground_truths.py#L408-L504)

What is happening in the handler:

* Implements a batch domain workflow:
  * Fetches items based on filter criteria
  * Applies computed tags for each item and diffs tag sets
  * On changes and `dry_run=false`, bypasses ETag and upserts
  * Aggregates errors and logs a summary

Service extraction candidates:

* Move into `TaggingService` or a dedicated maintenance service:
  * `recompute_computed_tags(*, dataset: str | None, status: GroundTruthStatus | None, dry_run: bool) -> RecomputeTagsResponse`
* Centralize the “bypass ETag for maintenance” rule in one place

## Additional candidates

### Chat endpoint input and error policy

File: `backend/app/api/v1/chat.py`

Excerpt: [backend/app/api/v1/chat.py#L29-L158](backend/app/api/v1/chat.py#L29-L158)

Notes:

* Message sanitation and validation are largely request-layer concerns.
* The handler owns error-to-status mapping and correlation ID propagation. If this pattern repeats, it could be centralized (for example, a shared exception-to-response utility), but it is not urgent compared to GT/assignment workflows.

### Tags endpoint config precedence

File: `backend/app/api/v1/tags.py`

Excerpt: [backend/app/api/v1/tags.py#L66-L106](backend/app/api/v1/tags.py#L66-L106)

Notes:

* The handler determines the source of truth for manual tags based on `settings.ALLOWED_MANUAL_TAGS` vs persisted registry.
* This is a domain/config decision and is a good candidate for `TagRegistryService`:
  * `list_manual_tags_with_computed_filtered() -> tuple[list[str], list[str]]`

## Container and DI observations

* API handlers frequently depend on the global `container` singleton and call `container.repo.*` directly.
* When extracting services, prefer constructor-injected dependencies (repo protocols, registry providers) to reduce implicit coupling and make unit testing easier.

## Suggested next steps

* Extract shared “ground truth update” workflow into a single service method used by both assignments and ground-truth CRUD.
* Replace substring-based error mapping with typed domain exceptions to stabilize HTTP status codes.
* Keep handler functions thin: authentication, request parsing, and response formatting only.
