<!-- markdownlint-disable-file -->
# Task Research: Cosmos Repo / Service Layer Refactor

Build refactoring research for:

* Logic currently in `cosmos_repo.py` that should live in the service layer instead.
* Logic currently in API routes/handlers that should live in the service layer instead.
* A new `cosmos_emulator.py` that inherits from (or wraps) `cosmos_repo.py` and overrides emulator-specific behavior, instead of intermixing emulator conditionals inside `cosmos_repo.py`.

## Task Implementation Requests

* Identify and classify responsibilities currently in `cosmos_repo.py` (pure persistence vs domain/service logic vs emulator quirks).
* Identify API-layer business logic candidates to move into services.
* Propose a repo/service/emulator class/module structure, including the specific seams to override for the emulator.
* Provide actionable refactor steps with exact file references (paths and line ranges).

## Scope and Success Criteria

* Scope:
  * Backend Python code only.
  * Focus on Cosmos DB repository + emulator behavior + API handlers.
* Out of scope:
  * Frontend changes.
  * Large behavioral changes; this is a refactor plan.
* Assumptions:
  * There is an existing Cosmos repository abstraction used by services and API.
  * Emulator-specific behavior is currently mixed into production Cosmos codepaths.
* Success Criteria:
  * A concrete, evidence-backed map of what to move and where.
  * One recommended design for `cosmos_repo.py` + `cosmos_emulator.py` and service boundaries.
  * Refactor steps that minimize risk and avoid breaking dependency injection.

## Outline

1. Convention discovery (repo-specific guidelines, layering conventions)
2. Current-state inventory
   * `cosmos_repo.py` responsibilities
   * Emulator-specific branching points
   * API endpoints containing business logic
   * Service layer responsibilities today
3. Target architecture
   * Repository interface vs implementation
   * Emulator-specific subclass/adapter
   * Service boundaries and orchestration
4. Migration plan
   * Mechanical steps
   * High-risk areas
   * Suggested tests/verification steps

## Research Executed

### Project Conventions

* Layering is documented as API → Services → Repos/Adapters, composed via a singleton container ([backend/CODEBASE.md](backend/CODEBASE.md#L20-L29)).
* DI wiring follows a global `container` with an async `startup_cosmos()` initialization path ([backend/app/container.py](backend/app/container.py#L83-L161)).
* There is existing, explicitly documented emulator/conditional behavior inside the Cosmos repo (e.g., the conditional patch implementation for `assign_to`) ([backend/CONDITIONAL_PATCH_IMPLEMENTATION.md](backend/CONDITIONAL_PATCH_IMPLEMENTATION.md#L11-L22), [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1409-L1609)).
* Emulator limitations are already recognized and sometimes require alternate query behavior (notably `ARRAY_CONTAINS`) ([backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md#L5-L36)).
* Emulator Unicode/backslash issues are handled via a feature flag (base64 encoding of `refs[*].content`) ([backend/docs/cosmos-emulator-unicode-workaround.md](backend/docs/cosmos-emulator-unicode-workaround.md#L35-L39)).

### File Analysis

* Repository implementation:
  * Cosmos repo: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L389-L443)
  * Repo interface/base: [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py#L1-L55)
* API endpoints with notable workflow logic:
  * Assignments: [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L78-L232)
  * Ground truths: [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L105-L154), [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L232-L369)
* Existing service boundary:
  * Assignment service: [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L44-L146)
* DI wiring:
  * Container composition: [backend/app/container.py](backend/app/container.py#L83-L161)

### Code Search Results

* Emulator/compat toggles and fallbacks exist in the repo and influence query shape and/or write behavior:
  * Pagination/query logic and limitations: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L660-L911)
  * Unicode/emulator workarounds and retry behavior are present in the repo write-paths (see transform/retry regions): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L500-L590)
* Conditional patch vs read-modify-replace assignment semantics are implemented in the repo today:
  * Assignment patch implementation: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1409-L1609)
  * Assignment fallback path: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1649-L1680)

## Key Discoveries

## Research Inputs

* Conventions: [.copilot-tracking/subagent/20260121/conventions-research.md](.copilot-tracking/subagent/20260121/conventions-research.md)
* API hotspots: [.copilot-tracking/subagent/20260121/api-logic-research.md](.copilot-tracking/subagent/20260121/api-logic-research.md)
* Cosmos repo deep dive: [.copilot-tracking/subagent/20260121/cosmos-repo-research.md](.copilot-tracking/subagent/20260121/cosmos-repo-research.md)
* Consolidated synthesis: [.copilot-tracking/subagent/20260121/synthesis-notes.md](.copilot-tracking/subagent/20260121/synthesis-notes.md)

### Project Structure

* The backend already has an explicit `services/` layer, but some orchestration/workflow logic remains in routers and in the Cosmos repo.
* The Cosmos repo currently contains both production Cosmos behavior and emulator compatibility behavior.

### Implementation Patterns

* API handlers perform multi-step update workflows (parse → read existing → compute changes → write → post-processing) that are better owned by services to keep business rules testable and reusable.
* The repo includes conditional patch logic for assignments (optimized for Cosmos) that is known to be incompatible with emulator behavior; this is the clearest subclass override seam.

### Emulator Split Findings

The currently mixed emulator-specific behavior clusters into three themes:

* Query limitations (emulator does not support some predicates/constructs): [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md#L5-L36)
* Write-path transforms to avoid Unicode/backslash issues: [backend/docs/cosmos-emulator-unicode-workaround.md](backend/docs/cosmos-emulator-unicode-workaround.md#L35-L39)
* Assignment update semantics (patch vs read-modify-replace): [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1409-L1609)

## Technical Scenarios

### Scenario: Split persistence vs service logic

**Requirements:**

* Keep persistence code (query building, paging, RU/diagnostics, container interactions) in repo.
* Move domain decisions, validation, and orchestration to services.

**Preferred Approach:**

* Keep `cosmos_repo.py` as the production implementation of the existing repo interface.
* Move workflow/domain decisions into services (thin repo; services orchestrate).
* Add `cosmos_emulator.py` that subclasses the production repo and overrides only emulator-specific seams.

Recommended override seams for `cosmos_emulator.py` (inheritance-based):

* `is_cosmos_emulator_in_use()`
* `list_gt_paginated(...)` (force emulator-safe filtering strategy) ([backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L660-L911))
* `assign_to(...)` (force read-modify-replace; avoid patch predicates) ([backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1409-L1609), [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1649-L1680))
* `upsert_gt(...)` / `delete_dataset(...)` (centralize emulator-specific retry policy)
* `_transform_doc_for_write(...)` and `_transform_doc_for_read(...)` (unicode/base64 workaround seam)

Target file tree (conceptual):

```text
backend/app/adapters/repos/
  base.py
  cosmos_repo.py          # production implementation
  cosmos_emulator.py      # emulator implementation (subclass)
```

_TBD once we see the actual code structure._

#### Considered Alternatives

* Keep emulator conditionals in `cosmos_repo.py` with flags:
  * Pros: fewer new files/classes.
  * Cons: continued intermixing; harder to reason about production behavior and to test.
* Strategy object injected into repo (instead of subclass):
  * Pros: explicit seam without inheritance.
  * Cons: more plumbing and indirection than needed if only a handful of methods differ.

### Scenario: Move API logic to services

**Requirements:**

* API handlers should do: auth/identity extraction, request parsing/validation, response shaping.
* Services should do: cross-entity workflows, domain decisions, idempotency semantics, event-ish side effects.

Current hotspots (examples) where routers exceed orchestration:

* Assignments workflow logic in the router: [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L78-L232)
* Ground truth update workflow logic in the router: [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L232-L369)
* Ground truth list/import validation and workflow logic: [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L105-L154)

Proposed service extraction:

* Introduce a `GroundTruthUpdateService` responsible for the end-to-end update workflow used by multiple endpoints (read, validate, normalize, write, post-process).
* Move assignment selection/sampling rules fully into the assignment service layer (building on [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L44-L146)).

## Recommended Migration Plan (Low-Risk)

1) Introduce typed domain exceptions (stable API-level mapping).
2) Add `GroundTruthUpdateService` with a single “update workflow” entrypoint.
3) Switch routers to call the service (handlers become thin orchestration).
4) Extract request parsing helpers into a shared module (router/service reuse).
5) Move assignment sampling/selection logic out of the repo into services.
6) Move derived-field computation (e.g., `totalReferences`) out of the repo into services/domain normalization.
7) Add `cosmos_emulator.py` (subclass) and select it in the container wiring ([backend/app/container.py](backend/app/container.py#L83-L161)).
8) Centralize document transforms behind `_transform_doc_for_write/_transform_doc_for_read` seam.
9) Update tests to target seams (behavior-preserving refactor first).
