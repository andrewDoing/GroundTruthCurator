---
title: Synthesis — Refactor recommendations (API/service/repo boundaries + Cosmos emulator repo)
description: Consolidated, line-cited recommendations based on prior research notes.
author: GitHub Copilot (subagent)
ms.date: 2026-01-21
ms.topic: reference
---

## 1) Consolidated responsibility boundary proposal (API vs service vs repo)

### API layer (FastAPI routers)
**Owns:** HTTP surface area only: authn/authz, request parsing, basic request-shape validation, and mapping typed service errors to HTTP responses.

**Concrete examples (current violations):**
- The SME update endpoint contains a full workflow: ownership enforcement, partial update semantics, approval/status transitions that clear assignment, history parsing (including embedded refs), ETag enforcement, computed tag application, persistence, and best-effort deletion of the assignment document — all inside the router handler in [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L78-L232).
- The general ground truth update endpoint repeats many of the same workflow concerns: status coercion, explicit business rules rejecting `computedTags` and legacy `tags`, history parsing, ETag enforcement, computed tag application, persistence, and then re-fetch for fresh ETag in [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L232-L369).

**Good existing pattern to emulate:**
- Snapshot routes delegate domain work to `container.snapshot_service` and keep the handler thin in [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L105-L154).

### Service layer
**Owns:** domain workflows/state transitions, cross-endpoint invariants, and shared parsing/normalization.

**Recommended service boundaries (aligned to existing code):**
- **`GroundTruthUpdateService` (new):** consolidate “update item” workflows used by both the SME update route and the general update route.
  - Should own: partial update policy, history parsing, tag-field acceptance policy, computed tag recomputation policy, and ETag policy (requirement + mismatch translation).
  - Justification: the routers currently duplicate logic and apply tags/ETags similarly in [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L104-L198) and [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L241-L363).
- **`AssignmentService` (existing):** own assignment workflows; keep repo calls as persistence/atomic update primitives.
  - Today `AssignmentService.self_assign` orchestrates retries and uses `repo.assign_to` + assignment-doc materialization in [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L44-L146).
  - Repo currently owns a large “sampling allocation + quota + selection + shuffle” algorithm in `sample_unassigned` and `_compute_quotas`, which is domain workflow rather than persistence and should move into the service layer ([backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1409-L1609), [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1649-L1680)).
- **`GroundTruthDerivationsService` (new) OR domain model responsibility:** derived-field computation currently lives in the Cosmos adapter.
  - The repo computes and mutates `totalReferences` during persistence (`_compute_total_references` and `_to_doc`) in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L389-L443). This is a business definition ("history refs win") and should be owned above the storage adapter.

### Repo layer (Cosmos adapters)
**Owns:** persistence mechanics only: Cosmos client/container I/O, query construction, paging, concurrency primitives (ETag usage), and minimal storage-centric validations.

**Concrete repo responsibilities (current examples):**
- Interface surface is already formalized via `GroundTruthRepo` in [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py#L1-L55).
- Storage-centric query construction with safe parameterization belongs in the repo (e.g., tag and ref-url clauses, including emulator limitations) in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L500-L590).
- Cosmos pagination uses a direct SQL path with `ORDER BY` and a separate emulator path with in-memory filtering when needed in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L660-L911).

**What should move out of the repo:**
- Domain validation of `user_id` currently happens inside `assign_to` (regex) in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1689-L1714). That rule is an API/service contract; repo should assume validated input.

## 2) Recommended `cosmos_emulator.py` design (inherit vs wrapper) + override seams

### Recommendation: subclass (inherit) a production repo
Create `CosmosEmulatorGroundTruthRepo(CosmosGroundTruthRepo)` in a new module `backend/app/adapters/repos/cosmos_emulator.py`.

**Why inherit (vs wrapper) in this codebase:**
- The container currently constructs a concrete `CosmosGroundTruthRepo` and wires services immediately afterward in [backend/app/container.py](backend/app/container.py#L83-L161). Keeping a compatible constructor minimizes DI churn.
- Many emulator differences are already expressed as “same public method, different internal behavior” toggled by `is_cosmos_emulator_in_use()` in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L644-L647). A subclass can make that decision structural (class-level) instead of conditional branches in production code.

### Exact override seams (methods/properties) to isolate emulator behavior

1) **`is_cosmos_emulator_in_use()`**
- Base currently detects emulator via endpoint string in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L644-L647).
- Emulator subclass override: return `True` unconditionally.

2) **`list_gt_paginated()` routing + emulator pagination path**
- Base method conditionally routes to `_list_gt_paginated_with_emulator` when tags/ref_url are present and emulator is in use in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L674-L707).
- Emulator subclass override: simplify to always use `_list_gt_paginated_with_emulator` when `tags` or `ref_url` are provided, eliminating endpoint checks from production.
- The emulator path explicitly disables SQL tag/ref_url filters and performs in-memory filtering due to emulator limitations in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L806-L911).

3) **Query filter construction for prod-only SQL features**
- The `EXISTS(...)` ref-url filter is only injected when `include_ref_url=True` in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L565-L585).
- Emulator subclass should avoid ref-url SQL filters (continue doing in-memory filtering as implemented) by ensuring `include_ref_url=False` for emulator list operations.

4) **`assign_to()` (patch vs read-modify-replace)**
- Base currently:
  - validates `user_id` with a regex
  - chooses patch vs read-modify-replace based on emulator detection
  in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1689-L1714).
- Emulator subclass override:
  - delegate validation to service (stop duplicating API contract here)
  - always execute read-modify-replace (compatibility path) and avoid `patch_item` filter predicates.

5) **Write-path normalization + emulator-specific retries (`upsert_gt`)**
- Base uses `COSMOS_DISABLE_UNICODE_ESCAPE` gating and applies `_ensure_utf8_strings` before upsert/replace in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1099-L1117).
- Base also includes emulator-specific retry behavior keyed off `is_cosmos_emulator_in_use()` and message matching for invalid JSON payload and intermittent jsonb errors in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1120-L1216).
- Emulator subclass override: keep these retries (and optionally strengthen them), while production base can be simplified over time to rely on SDK retry policy.

6) **Delete-path retries (`delete_dataset`)**
- Base has emulator-only retry logic for intermittent errors and HTTP-format issues in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1235-L1360).
- Emulator subclass override: keep retries local to emulator repo.

### Consolidating the Unicode/backslash/base64 workaround into the emulator repo
Right now the workaround is spread across:
- Normalization + base64 helpers (`_normalize_unicode_for_cosmos`, `_restore_unicode_from_cosmos`) in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L45-L176).
- A repo-level wrapper `_ensure_utf8_strings()` in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L361-L377).
- Multiple call sites (import, curation upsert, GT upsert) that apply the wrapper in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L448-L479) and [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1079-L1117).
- Read-path restore inside `_from_doc()` in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L446-L459).

**Recommendation:** define explicit “transform seams” in the base class and override them in the emulator subclass.
- Base adds two protected methods:
  - `_transform_doc_for_write(doc: dict[str, Any]) -> dict[str, Any]`
  - `_transform_doc_for_read(doc: dict[str, Any]) -> dict[str, Any]`
- Base default implementations are identity.
- Emulator subclass overrides them to apply `_normalize_unicode_for_cosmos` / `_restore_unicode_from_cosmos` (and thus base64 encode/decode of `refs[*].content`). These behaviors already exist in the module and are gated by `settings.COSMOS_DISABLE_UNICODE_ESCAPE` in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L99-L176).

This turns today’s scattered per-method checks into a single, testable seam.

## 3) Step-by-step migration plan (minimize risk, 6–10 steps)

1) **Introduce typed domain exceptions for stable HTTP mapping**
   - Replace substring-based ValueError parsing in the assign endpoint with typed errors (router currently maps substrings) in [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L255-L323).

2) **Add `GroundTruthUpdateService` with a single “update workflow” entrypoint**
   - Start by moving the shared logic (ETag requirement + mismatch mapping, history parsing, computed tags application) out of both routes.
   - Current duplicated workflow lives in [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L104-L198) and [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L241-L363).

3) **Switch routers to call the service (thin handlers)**
   - Keep request parsing/validation in the handlers; move the workflow and repo calls into the service.
   - Use the snapshot route pattern as precedent (service-first) in [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L105-L154).

4) **Extract parsing helpers into a shared module**
   - Create reusable helpers for history parsing (including refs and expectedBehavior) since both handlers implement near-identical loops in [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L152-L187) and [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L300-L338).

5) **Move assignment sampling logic out of the repo into service**
   - Shift the allocation/quota/selection algorithm from `CosmosGroundTruthRepo.sample_unassigned` to `AssignmentService` (or a dedicated `AssignmentSamplingService`).
   - Current algorithm is in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1409-L1609), with quota math in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1649-L1680).

6) **Move derived-field computation (`totalReferences`) out of the repo**
   - Stop mutating `GroundTruthItem.totalReferences` inside `_to_doc` and compute it in a derivations service before persistence.
   - Current mutation happens in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L410-L443).

7) **Introduce `CosmosEmulatorGroundTruthRepo` and select it in the container**
   - Container already derives an emulator/non-TLS condition via `USE_COSMOS_EMULATOR` and endpoint scheme in [backend/app/container.py](backend/app/container.py#L110-L119).
   - Add a class selection branch there (keep constructor signature compatible).
   - Emulator flag is defined in settings in [backend/app/core/config.py](backend/app/core/config.py#L28-L45).

8) **Centralize the document transform seam**
   - Implement `_transform_doc_for_write/_transform_doc_for_read` and route existing `_ensure_utf8_strings` usage through it.
   - Grounding: normalization functions and wrapper already exist in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L45-L176) and [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L361-L377).

9) **Update tests to target the new seams (keep behavior identical first)**
   - Keep production behavior unchanged; emulator behavior should remain behind `USE_COSMOS_EMULATOR` or localhost endpoint detection initially.

## 4) Alternatives considered (brief)

- **Flags-in-repo (status quo):** simplest, but keeps production and emulator concerns entangled (e.g., emulator routing in `list_gt_paginated`) in [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L674-L707).
- **Subclass (recommended):** isolates emulator-only behavior while keeping constructor + protocol stable (container wiring remains straightforward) in [backend/app/container.py](backend/app/container.py#L83-L161).
- **Strategy object / wrapper:** cleanest purity-wise (inject a “capabilities/transforms” strategy), but higher churn because many internal calls and helper methods aren’t easily intercepted without adding new seams.
