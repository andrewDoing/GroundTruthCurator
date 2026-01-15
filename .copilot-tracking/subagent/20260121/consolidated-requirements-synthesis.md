---
title: Consolidated requirements synthesis
description: Consolidated high-level requirements derived from subagent research reports, with primary-source evidence and identified ambiguities.
author: GitHub Copilot (subagent)
ms.date: 2026-01-21
ms.topic: reference
keywords:
  - requirements
  - synthesis
  - ground truth curation
  - backend
  - frontend
estimated_reading_time: 15
---

## Scope

This document consolidates high-level requirements from prior subagent research reports into a single, testable requirements set.

Notes on inputs:

* Two requested inputs were not found at the expected paths:
  * `.copilot-tracking/subagent/20260121/conventions-and-sources-research.md`
  * `.copilot-tracking/subagent/20260121/prd-requirements-research.md`
* Closest available subagent sources used instead:
  * `.copilot-tracking/subagent/20260121/conventions-research.md`
  * `.copilot-tracking/subagent/20260121/backend-requirements-research.md`
  * `.copilot-tracking/subagent/20260121/frontend-requirements-research.md`
  * `.copilot-tracking/subagent/20260121/cosmos-repo-research.md` (constraints only)
  * `.copilot-tracking/subagent/20260121/api-logic-research.md` and `.copilot-tracking/subagent/20260121/synthesis-notes.md` (constraints only)

All requirements below include at least one primary source reference (repo file path plus line range) as cited by the subagent reports.

## Top 10 requirements

1. The system must support an assignment-based curation workflow where users work primarily from an assigned-items queue.
  Evidence: frontend/CODEBASE.md#L128-L148; backend/docs/assign-single-item-endpoint.md#L85-L95.
1. The backend must enforce optimistic concurrency on writes using Cosmos DB ETags, requiring `If-Match` and returning updated ETags.
  Evidence: backend/docs/api-change-checklist-assignments.md#L74-L90; backend/docs/api-change-checklist-assignments.md#L168-L178.
1. The UI must gate approval based on reference completeness (selection, visited state, and minimum key-paragraph length).
  Evidence: frontend/CODEBASE.md#L75-L79; frontend/src/components/app/defaultCurateInstructions.md#L1-L4.
1. The backend must implement soft delete via status transitions and exclude deleted items from lists unless explicitly requested.
  Evidence: backend/CODEBASE.md#L33-L34; frontend/CODEBASE.md#L145-L147.
1. References must support search-and-add and selected-reference management, including de-duplication by URL and visited tracking.
  Evidence: frontend/CODEBASE.md#L136-L144.
1. The system must support multi-turn conversation editing with per-turn metadata and additional approval constraints.
  Evidence: frontend/IMPLEMENTATION_SUMMARY.md#L88-L112; backend/docs/multi-turn-refs.md#L67-L76.
1. Snapshot export must support attachment delivery and artifact delivery with a manifest and stable schema versioning.
  Evidence: backend/docs/export-pipeline.md#L26-L34; backend/docs/export-pipeline.md#L76-L90.
1. Tag storage and behavior must normalize tags into a canonical `group:value` format and enforce known-group behavioral rules.
  Evidence: backend/docs/tagging_plan.md#L3-L10; backend/docs/tagging_plan.md#L60-L66.
1. The backend must be usable with the Cosmos DB Emulator for local development, with documented emulator limitations handled safely.
  Evidence: backend/docs/cosmos-emulator-limitations.md#L5-L27; backend/app/main.py#L56-L85.
1. Telemetry must be opt-in and safe-by-default, and the UI must present a user-friendly error boundary.
  Evidence: frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L18; frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L79-L86.

## Product goals

* Enable curators and SMEs to curate ground-truth items efficiently using an assignment-based workflow with a focused curation workspace.
  * Evidence:
    * frontend/CODEBASE.md#L70-L80.
    * frontend/CODEBASE.md#L128-L148.
* Support both single-turn (Q/A) and multi-turn (conversation history) ground-truth formats.
  * Evidence:
    * frontend/IMPLEMENTATION_SUMMARY.md#L88-L112.
    * backend/docs/multi-turn-refs.md#L67-L76.
* Preserve backward compatibility for existing stored item shapes while introducing multi-turn enhancements.
  * Evidence:
    * backend/docs/multi-turn-refs.md#L67-L73.

## Frontend UX

* Provide a single-page curation workspace with a multi-pane layout (queue, editor/actions, references, stats/modals).
  * Evidence:
    * frontend/CODEBASE.md#L70-L80.
* Provide an assigned-items queue that supports selection, refresh, and visibility of key item attributes.
  * Evidence:
    * frontend/CODEBASE.md#L128-L148.
* Provide a self-serve assignment action with a configurable default limit.
  * Evidence:
    * frontend/README.md#L20-L44.
    * frontend/CODEBASE.md#L128-L148.
* Enable editing of item content, including that saving is not blocked by a “change category” requirement.
  * Evidence:
    * frontend/CODEBASE.md#L86-L95.
* Provide references UX with two experiences: search candidates and manage selected/attached references.
  * Evidence:
    * frontend/CODEBASE.md#L136-L144.
* Prevent duplicate reference additions by URL, including disabling add when URL is already present.
  * Evidence:
    * frontend/CODEBASE.md#L136-L144.
* Support opening references in a new tab and marking visited state, and provide user feedback when popups are blocked.
  * Evidence:
    * frontend/CODEBASE.md#L136-L144.
    * frontend/CODEBASE.md#L215-L233.
* Allow capturing a key paragraph per selected reference and display a length/counter affordance.
  * Evidence:
    * frontend/CODEBASE.md#L136-L144.
* Support removing a reference with an undo window.
  * Evidence:
    * frontend/CODEBASE.md#L136-L144.
    * frontend/CODEBASE.md#L215-L233.
* Gate approval based on reference completeness and item state (deleted items cannot be approved).
  * Evidence:
    * frontend/CODEBASE.md#L75-L79.
    * frontend/CODEBASE.md#L145-L147.
* Provide save semantics that detect no-op updates and communicate “No changes”.
  * Evidence:
    * frontend/CODEBASE.md#L140-L146.
* Support soft-delete and restore workflows with clear UI indicators and approval gating.
  * Evidence:
    * frontend/CODEBASE.md#L145-L147.
* Support export as a backend-driven snapshot download.
  * Evidence:
    * frontend/CODEBASE.md#L145-L146.
* Support applying tags to an item using a known tag schema.
  * Evidence:
    * frontend/docs/MVP_REQUIREMENTS.md#L22-L27.
* Surface curation instructions as user-consumable markdown and support fetch/write per dataset with concurrency control.
  * Evidence:
    * frontend/docs/MVP_REQUIREMENTS.md#L15-L18.
    * frontend/CODEBASE.md#L165-L168.
* Support multi-turn conversation editing with a timeline view, turn operations, and optional context.
  * Evidence:
    * frontend/IMPLEMENTATION_SUMMARY.md#L88-L112.
* Enforce multi-turn approval constraints beyond single-turn, including relevance marking and key-paragraph constraints for relevant references.
  * Evidence:
    * frontend/IMPLEMENTATION_SUMMARY.md#L147-L158.
* Provide keyboard shortcuts for save and approve attempts.
  * Evidence:
    * frontend/CODEBASE.md#L184-L184.
* Provide toast-based feedback for network failures and undo interactions.
  * Evidence:
    * frontend/CODEBASE.md#L215-L233.
* Provide a demo mode that disables telemetry and may use mock providers.
  * Evidence:
    * frontend/README.md#L74-L92.

## Backend and API

* Expose a health endpoint at `GET /healthz`.
  * Evidence:
    * backend/CODEBASE.md#L14-L15.
    * backend/CODEBASE.md#L159-L161.
* Accept snake_case and camelCase inputs but always emit camelCase responses.
  * Evidence:
    * backend/CODEBASE.md#L32-L34.
* Enforce optimistic concurrency using Cosmos ETags on write paths.
  * Evidence:
    * backend/CODEBASE.md#L32-L34.
    * backend/docs/api-change-checklist-assignments.md#L74-L90.
* Require `If-Match` on assignment write paths and return the updated ETag in both response headers and body.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L74-L90.
    * backend/docs/api-change-checklist-assignments.md#L168-L178.
* Return 412 on missing or mismatched ETag with stable error codes and include the current ETag in the response.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L74-L90.
    * backend/docs/api-change-checklist-assignments.md#L168-L178.
* Represent delete via soft delete semantics (`status=deleted`).
  * Evidence:
    * backend/CODEBASE.md#L33-L34.
* Consolidate ground-truth item writes into the SME PUT and Curator PUT endpoints, with reference changes folded into these updates.
  * Evidence:
    * backend/docs/api-write-consolidation-plan.v2.md#L28-L36.
    * backend/docs/api-write-consolidation-plan.v2.md#L64-L66.
* Keep curator import as a create-only flow.
  * Evidence:
    * backend/docs/api-write-consolidation-plan.v2.md#L38-L45.
    * backend/docs/api-write-consolidation-plan.v2.md#L62-L64.
* Enforce assignment ownership on SME mutation routes and return a stable ownership error.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L82-L86.
    * backend/docs/api-change-checklist-assignments.md#L168-L176.
* Clear assignment fields atomically when transitioning to skipped, approved, or deleted.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L10-L12.
    * backend/docs/api-change-checklist-assignments.md#L175-L178.
* Use timezone-aware UTC timestamps for assignment time fields.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L13-L14.
    * backend/docs/api-change-checklist-assignments.md#L182-L184.
* Include `etag` in JSON bodies for assignment responses.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L19-L24.
    * backend/docs/api-change-checklist-assignments.md#L35-L38.
* Provide a single-item assign endpoint that rejects items already draft-assigned to another user and sets status to draft upon successful assignment.
  * Evidence:
    * backend/docs/assign-single-item-endpoint.md#L22-L29.
    * backend/docs/assign-single-item-endpoint.md#L33-L43.
* Create or upsert a secondary assignment document (materialized view) to enable fast per-user assigned-item queries.
  * Evidence:
    * backend/docs/assign-single-item-endpoint.md#L85-L95.

## Data and storage

* Support Cosmos DB as a persistence backend with a storage-layer abstraction.
  * Evidence:
    * backend/CODEBASE.md#L24-L30.
    * backend/app/adapters/repos/base.py#L1-L55.
* Support a Cosmos emulator mode for local development, without blocking app startup if the emulator is not ready.
  * Evidence:
    * backend/app/main.py#L56-L85.
    * backend/CODEBASE.md#L11-L14.
* Handle Cosmos emulator query limitations, including lack of `ARRAY_CONTAINS`, by adjusting behavior and skipping tests where appropriate.
  * Evidence:
    * backend/docs/cosmos-emulator-limitations.md#L5-L27.
* Support a safe workaround for Cosmos emulator Unicode/backslash parsing bugs when configured.
  * Evidence:
    * backend/README.md#L104-L121.
    * backend/docs/cosmos-emulator-unicode-workaround.md#L35-L39.
* Preserve backward compatibility for stored ground-truth fields while extending the multi-turn model (optional refs and tags in history).
  * Evidence:
    * backend/docs/multi-turn-refs.md#L67-L76.

## Export

* Support snapshot export with `attachment` and `artifact` delivery modes, with stable defaults when the request is empty.
  * Evidence:
    * backend/docs/export-pipeline.md#L26-L34.
* Return JSON document payloads for snapshot download endpoints.
  * Evidence:
    * backend/docs/export-pipeline.md#L33-L38.
* For artifact delivery, write a deterministic set of per-item files plus a manifest that includes a stable `schemaVersion`.
  * Evidence:
    * backend/docs/export-pipeline.md#L76-L90.
* Run export processors before formatting and support merging tag fields into a single exported `tags` array.
  * Evidence:
    * backend/docs/export-pipeline.md#L116-L128.

## Observability and operations

* Include a per-request user identifier in logs.
  * Evidence:
    * backend/README.md#L334-L341.
* Provide opt-in telemetry that is disabled by default and safely no-ops when disabled or in demo mode.
  * Evidence:
    * frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L18.
    * frontend/README.md#L74-L92.
* Provide a UI error boundary that catches render failures and optionally reports exceptions when telemetry is enabled.
  * Evidence:
    * frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L79-L86.

## Security and privacy

* In dev mode, support user simulation via `X-User-Id` to drive per-user behaviors.
  * Evidence:
    * backend/README.md#L334-L341.
    * frontend/README.md#L20-L44.
* Enforce ownership for assignment mutation endpoints to prevent unauthorized changes.
  * Evidence:
    * backend/docs/api-change-checklist-assignments.md#L82-L86.
    * backend/docs/api-change-checklist-assignments.md#L168-L176.
* Keep telemetry safe-by-default and opt-in.
  * Evidence:
    * frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L18.

## Quality and testing

* Maintain deterministic tag normalization behavior to support stable comparisons, exports, and tests.
  * Evidence:
    * backend/docs/tagging_plan.md#L54-L60.
* Skip or adjust tests in emulator mode when the emulator does not support required query capabilities.
  * Evidence:
    * backend/docs/cosmos-emulator-limitations.md#L5-L27.
    * backend/README.md#L248-L259.

## Cross-cutting constraints and notes

These items are implementation-adjacent but reflect constraints or invariants documented in sources.

* Prefer a layered architecture where API routes remain thin and workflow/state validation occurs in services rather than repository implementations.
  * Evidence:
    * backend/CODEBASE.md#L24-L30.
    * backend/docs/assign-single-item-endpoint.md#L78-L87.
* Treat emulator compatibility as a first-class constraint for local development.
  * Evidence:
    * backend/docs/cosmos-emulator-limitations.md#L5-L27.
    * backend/README.md#L104-L121.

## Conflicts and ambiguities to resolve

* Reference search and LLM endpoints appear inconsistent between frontend docs.
  * Evidence:
    * frontend/docs/MVP_REQUIREMENTS.md#L28-L36.
    * frontend/CODEBASE.md#L136-L145.
* Tag semantics differ between “canonical group:value tags” and permissive per-history tags, and it is unclear which UI validations apply to which fields.
  * Evidence:
    * backend/docs/tagging_plan.md#L3-L10.
    * backend/docs/history-tags-feature.md#L140-L150.
* Tag registry write support is unclear from the frontend requirements: it mentions “create new tags” while also stating no write endpoints for tags.
  * Evidence:
    * frontend/docs/MVP_REQUIREMENTS.md#L22-L27.
* Cosmos emulator unicode workaround coverage has potential drift for non-ground-truth containers.
  * Evidence:
    * backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L111-L128.
    * backend/app/adapters/repos/tags_repo.py#L93-L124.

