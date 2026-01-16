---
title: Manual Tags Design Details
description: Detailed specifications and execution notes for manual tags design work
ms.date: 2026-01-16
---
<!-- markdownlint-disable-file -->

# Task Details: Manual Tags Design

## Research Reference

* Source research: `.copilot-tracking/research/20260116-manual-tags-design-research.md`
* Design context: `docs/computed-tags-design.md`
* Existing tagging constraints: `backend/docs/tagging_plan.md`

## Phase 1: Confirm requirements and align policy

### Task 1.1: Decide manual tag validation mode(s) (MVP)

MVP requirement (confirmed): enforce **mutual exclusivity within a tag group**, and make that enforcement **configurable (true/false)**.

Define the desired validation policy for manual tags across these write paths:

* Interactive edits (`PUT /v1/ground-truths/...`)
* Assignment updates (`PUT /v1/assignments/...`)
* Bulk import validation

Current state is already exclusivity-aware for **known** groups via `TAG_SCHEMA` + `ExclusiveGroupRule`, but enforcement is not currently configurable.

* Model validation is relaxed (unknown groups/values allowed).
* Bulk import uses a strict allow-set from the global tag registry.

Specify the exclusivity enforcement semantics:

* Scope of the toggle:
  * Global toggle (recommended MVP): enable/disable enforcement of `exclusive=True` groups
  * Optional later: per-group overrides (in `TAG_SCHEMA` or config)
* Default:
  * Recommended: `true` (keep current correctness; allow disabling in dev/experiments)
* Contract with the frontend:
  * Decide whether `/v1/tags/schema` should continue to report per-group `exclusive` even when enforcement is disabled server-side.
    * Recommended: keep reporting `exclusive` so the UI can still guide the user, while backend can be relaxed if needed.

* Files:
  * `backend/app/domain/validators.py` (model-level coercion + validation)
  * `backend/app/services/validation_service.py` (bulk import strict validation)
  * `backend/app/api/v1/ground_truths.py` and `backend/app/api/v1/assignments.py` (write paths)
* Success:
  * A single documented policy for exclusivity enforcement (enabled/disabled)
  * A clear statement whether the backend or frontend is authoritative when the toggle is off
* Research references:
  * `.copilot-tracking/research/20260116-manual-tags-design-research.md` (Current behavior summary + decision points)

### Task 1.2: Decide the source of truth for “allowed manual tags” (optional / follow-up)

This is useful, but not required for the exclusivity MVP. Capture the intended direction so future work is scoped.

Choose the authoritative source for the tag picker (manual tags list):

* Static config (`GTC_ALLOWED_MANUAL_TAGS`)
* Global registry (Cosmos-backed list)
* A combined approach (seed from schema, allow extensions via registry)

Also decide whether the source must vary by dataset/tenant in the future.

* Files:
  * `backend/app/api/v1/tags.py` (current: allowlist overrides registry)
  * `backend/app/core/config.py` (existing settings surface)
  * `backend/app/adapters/repos/tags_repo.py` (Cosmos shape for global registry)
* Success:
  * A single selection mechanism that the backend implements and the frontend can rely on
  * Clear behavior when `GTC_ALLOWED_MANUAL_TAGS` is set

## Phase 2: Implement configurable exclusivity (backend)

### Task 2.1: Add a config flag to enable/disable exclusivity enforcement

Add a settings flag (e.g., `GTC_TAGS_ENFORCE_EXCLUSIVITY: bool`) that controls whether the backend enforces mutual exclusivity for groups marked `exclusive=True`.

Implementation approach options:

* Toggle rule execution:
  * Build `RULES` dynamically at runtime based on settings
  * Or: keep `RULES` constant but gate `ExclusiveGroupRule.check()` behind the flag

Ensure the flag is applied consistently anywhere `validate_tags()` is used for manual tags.

* Files:
  * `backend/app/core/config.py` (new setting)
  * `backend/app/domain/tags.py` (rule wiring / schema)
  * `backend/app/services/tagging_service.py` (validation flow)
  * `backend/app/domain/validators.py` (model validation uses `validate_tags()`)
  * `backend/app/api/v1/ground_truths.py` and `backend/app/api/v1/assignments.py` (write path validation behavior)
* Success:
  * When enabled: multiple tags from an exclusive group are rejected everywhere manual tags are accepted
  * When disabled: multiple tags from an exclusive group are accepted (still requiring canonical `group:value` format)

### Task 2.2: Document and expose the exclusivity flag (if needed)

Decide whether the flag should be:

* Backend-only (env setting), or
* Also exposed to the frontend via `/v1/config` so the UI can mirror server policy.

* Files:
  * `backend/app/core/config.py`
  * `backend/app/api/v1/config.py` (if exposing to frontend)
* Success:
  * The configured behavior is discoverable and documented

## Phase 3: Validation and normalization improvements

### Task 3.1: Ensure exclusivity toggle does not affect computed-tags invariants

Ensure the exclusivity flag only controls exclusivity checks, and does not regress:

* Canonicalization (`group:value`, lowercase, etc.)
* Computed-tags stripping from manual tags (write path)

* Files:
  * `backend/app/services/tagging_service.py`
  * `backend/app/services/validation_service.py` (bulk import)
* Success:
  * Exclusivity can be toggled independently without breaking other tag guarantees

### Task 3.2: Confirm computed tag stripping remains authoritative

Ensure that manual tags cannot be used to persist computed tags:

* Manual tags are cleaned via computed-tag registry matching before save
* Reject client writes to `computedTags`

This should remain true for all write paths.

* Files:
  * `backend/app/services/tagging_service.py`
  * `backend/app/api/v1/ground_truths.py`
  * `backend/app/api/v1/assignments.py`
* Success:
  * Tests cover attempts to submit computed tags in `manualTags`

## Phase 4: API contracts and frontend expectations

### Task 4.1: Confirm `/v1/tags/schema` and frontend behavior under the toggle

When exclusivity enforcement is disabled server-side, decide whether the frontend should:

* Still enforce exclusivity based on `/v1/tags/schema` (recommended default), or
* Also disable client-side exclusivity when the backend flag is off (requires exposing flag to frontend)

* Files:
  * `backend/app/api/v1/tags.py` (schema endpoint)
  * `frontend/src/services/tags.ts` (exclusive-group validation)
  * `backend/app/api/v1/config.py` (if exposing flag)
* Success:
  * Frontend and backend behave consistently (or intentionally diverge, but documented)

### Task 4.2: Confirm `/v1/tags` response contract (optional / follow-up)

This is not required for the exclusivity MVP, but keep this as a follow-up if API payload cleanup is desired.

* Files:
  * `backend/app/api/v1/tags.py`
  * `backend/app/domain/tags.py`
  * `frontend/src/services/tags.ts`
* Success:
  * No frontend breaking changes when new tags are introduced

## Phase 5: Verification and documentation

### Task 5.1: Add/adjust tests for exclusivity toggle

Cover the chosen policy with tests:

* Unit tests for exclusivity enabled vs disabled
* Integration tests for write paths (ground truths + assignments) when exclusivity is disabled
* Frontend test/behavior note: ensure UX does not unexpectedly diverge from backend

* Files:
  * `backend/tests/unit/`
  * `backend/tests/integration/`
* Success:
  * Tests clearly assert which flows allow unknown tags vs require registry membership

### Task 5.2: Document configuration and operations

Add docs describing:

* How to configure allowed manual tags
* How tag registry should be managed in dev/test/prod
* How strict validation affects bulk import and interactive edits

* Files:
  * `backend/README.md` (or a new doc under `backend/docs/`)
* Success:
  * A new team member can configure tags without reading code
