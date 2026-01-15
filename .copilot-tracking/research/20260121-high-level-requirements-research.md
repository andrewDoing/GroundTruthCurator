<!-- markdownlint-disable-file -->
# Task Research: High-Level Requirements Extraction (Frontend + Backend)

Extract product/system requirements that match the *existing system* and keep them high-level (behavioral), avoiding implementation details. Cover both frontend and backend.

## Task Implementation Requests

* Extract high-level requirements already present in the repo (docs + PRD artifacts)
* Ensure requirements reflect current frontend and backend capabilities
* Avoid implementation-specific constraints (frameworks, file structure, concrete endpoints) unless required for behavior

## Scope and Success Criteria

* Scope: Requirements derived from existing repo artifacts (PRD JSON/TXT, README/CODEBASE docs, backend docs, frontend docs).
* Exclusions: New feature ideation not supported by evidence in repo; low-level implementation steps.
* Success Criteria:
  * Requirements are grouped (Product, Frontend UX, Backend/API, Data/Storage, Export, Observability, Testing/Quality)
  * Each requirement is backed by at least one repo source reference (file + line range)
  * Requirements are written in “shall/should/may” language and are implementation-agnostic

## Outline

1. Evidence log (what was read)
2. Consolidated requirement set
3. Gaps/ambiguities where docs conflict
4. Recommended next validation questions

## Supporting Research

Detailed extractions and audits used to build this document:

- PRD extraction + match-to-system flags: [.copilot-tracking/subagent/20260121/prd-requirements-research.md](.copilot-tracking/subagent/20260121/prd-requirements-research.md)
- Frontend capability extraction: [.copilot-tracking/subagent/20260121/frontend-requirements-research.md](.copilot-tracking/subagent/20260121/frontend-requirements-research.md)
- Backend capability extraction: [.copilot-tracking/subagent/20260121/backend-requirements-research.md](.copilot-tracking/subagent/20260121/backend-requirements-research.md)
- Repo conventions + sources-of-truth: [.copilot-tracking/subagent/20260121/conventions-and-sources-research.md](.copilot-tracking/subagent/20260121/conventions-and-sources-research.md)
- Requirements synthesis working doc: [.copilot-tracking/subagent/20260121/consolidated-requirements-synthesis.md](.copilot-tracking/subagent/20260121/consolidated-requirements-synthesis.md)
- Citation validation for this note: [.copilot-tracking/subagent/20260121/citation-validation.md](.copilot-tracking/subagent/20260121/citation-validation.md)
- Reference audit (present vs linked): [.copilot-tracking/subagent/20260121/subagent-reference-audit.md](.copilot-tracking/subagent/20260121/subagent-reference-audit.md)

### Potential Next Research

* Identify which PRD items are intentionally deferred vs removed
  * Reasoning: PRD contains capabilities not currently reflected in frontend/backend docs
  * Reference: [prd.json](prd.json)

## Research Executed

### Evidence log (sources reviewed)
- Primary requirements sources: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md), [prd.json](prd.json), [prd-genericize.json](prd-genericize.json), [ralph/ralph-prd.txt](ralph/ralph-prd.txt), [BUSINESS_VALUE.md](BUSINESS_VALUE.md)
- Frontend behavior and UX invariants: [frontend/CODEBASE.md](frontend/CODEBASE.md#L70-L180), [frontend/README.md](frontend/README.md#L25-L92), [frontend/IMPLEMENTATION_SUMMARY.md](frontend/IMPLEMENTATION_SUMMARY.md#L84-L165)
- Backend behavior and API semantics: [backend/CODEBASE.md](backend/CODEBASE.md#L14-L35), [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md#L7-L113), [backend/docs/api-write-consolidation-plan.v2.md](backend/docs/api-write-consolidation-plan.v2.md#L62-L67)
- Assignment workflow (single-item + materialized assignment doc): [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md#L20-L95), [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py#L47-L65)
- Multi-turn backend compatibility: [backend/docs/multi-turn-refs.md](backend/docs/multi-turn-refs.md#L5-L75)
- Export/snapshot behavior: [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L24-L40), [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L72-L93), [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L117-L127)
- Tag rules and normalization: [backend/docs/tagging_plan.md](backend/docs/tagging_plan.md#L5-L13), [backend/docs/tagging_plan.md](backend/docs/tagging_plan.md#L54-L61)
- Cosmos emulator operational constraints + workarounds: [backend/app/main.py](backend/app/main.py#L60-L82), [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md#L1-L25), [backend/docs/cosmos-emulator-unicode-workaround.md](backend/docs/cosmos-emulator-unicode-workaround.md#L35-L38)
- Observability/telemetry expectations: [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L17), [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L79-L86)
- Dev user simulation header: [backend/README.md](backend/README.md#L336-L338), [frontend/README.md](frontend/README.md#L27-L32)

### Research executed summary
- Extracted behavioral requirements from primary requirement sources and current codebase docs (frontend + backend) and selected “contract” docs in backend `docs/`.
- Validated concurrency, assignment, and emulator constraints against code-level sources where available (repo protocol + app startup).
- Identified doc conflicts where frontend requirements docs diverge from current implemented flows.

## Consolidated Requirements

### Product / User Goals
- The system shall support an assignment-based curation workflow where users work from a queue of assigned items and can request more assignments (“self-serve”). [frontend/CODEBASE.md](frontend/CODEBASE.md#L124-L149)
- The system should support explicitly assigning a specific item to oneself, including conflict protection when another user already holds a draft assignment. [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md#L20-L39)
- The system shall support both single-turn (Q/A) and multi-turn (conversation history) ground-truth editing while preserving backward compatibility for existing item shapes. [frontend/IMPLEMENTATION_SUMMARY.md](frontend/IMPLEMENTATION_SUMMARY.md#L104-L165), [backend/docs/multi-turn-refs.md](backend/docs/multi-turn-refs.md#L5-L75)

### Frontend UX Requirements
- The UI shall provide a single-page curation workspace with distinct queue, editor/actions, and references areas. [frontend/CODEBASE.md](frontend/CODEBASE.md#L79-L80)
- The UI shall gate approval on reference completeness: at least one selected reference; all references visited; selected references include a key paragraph with minimum length (≥40 chars); deleted items cannot be approved. [frontend/CODEBASE.md](frontend/CODEBASE.md#L79-L79), [frontend/CODEBASE.md](frontend/CODEBASE.md#L119-L122), [frontend/src/components/app/defaultCurateInstructions.md](frontend/src/components/app/defaultCurateInstructions.md#L1-L4)
- The UI shall support reference workflows including search, adding selected references, URL de-duplication, visited tracking (open-in-new-tab), and key-paragraph editing with a counter. [frontend/CODEBASE.md](frontend/CODEBASE.md#L141-L143), [frontend/CODEBASE.md](frontend/CODEBASE.md#L152-L165)
- The UI should support removing a reference with an undo window and provide toast-based feedback for key actions and failures. [frontend/CODEBASE.md](frontend/CODEBASE.md#L136-L136), [frontend/CODEBASE.md](frontend/CODEBASE.md#L164-L165)
- The UI shall support soft delete + restore semantics and prevent approval of deleted items. [frontend/CODEBASE.md](frontend/CODEBASE.md#L147-L147), [frontend/CODEBASE.md](frontend/CODEBASE.md#L79-L79)
- The UI should detect no-op saves and report “No changes” rather than issuing an update that changes nothing. [frontend/CODEBASE.md](frontend/CODEBASE.md#L145-L145)
- The UI shall support snapshot export by downloading a backend-provided JSON snapshot. [frontend/CODEBASE.md](frontend/CODEBASE.md#L146-L146)
- The UI shall support multi-turn editing features (timeline, turn add/delete/edit, mode toggle), plus multi-turn approval constraints requiring reference relevance marking and key-paragraph constraints for “relevant” references. [frontend/IMPLEMENTATION_SUMMARY.md](frontend/IMPLEMENTATION_SUMMARY.md#L86-L151)
- The UI should support a demo mode that disables or safely no-ops telemetry and can use mock providers. [frontend/README.md](frontend/README.md#L73-L92), [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L17)
- The UI should support dataset-level curation instructions fetch/update (including concurrency via ETag on update). [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L15-L18)

### Backend / API Requirements
- The backend shall expose a health endpoint at `GET /healthz`. [backend/CODEBASE.md](backend/CODEBASE.md#L14-L15), [backend/app/main.py](backend/app/main.py#L147-L149)
- The backend shall accept both snake_case and camelCase inputs and always emit camelCase outputs. [backend/CODEBASE.md](backend/CODEBASE.md#L31-L32)
- The backend shall enforce optimistic concurrency on write paths using ETags: updates require `If-Match` (or equivalent request ETag) and return HTTP 412 on missing/mismatch with stable error semantics. [backend/CODEBASE.md](backend/CODEBASE.md#L33-L33), [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md#L75-L113)
- Assignment mutation endpoints shall enforce assignment ownership and return a stable ownership error when violated. [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md#L82-L86)
- Assignment state transitions (approve/skip/delete) shall clear assignment fields atomically with the status change, and assignment timestamps shall be timezone-aware UTC. [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md#L7-L14), [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md#L154-L156)
- Assignment list responses shall include `etag` in the JSON body (even if per-item `ETag` headers are optional). [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md#L31-L35)
- The backend shall provide a single-item self-assign flow where assignment sets status to draft (even from approved/deleted/skipped) and rejects assignment of items draft-assigned to a different user. [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md#L29-L39)
- The backend should maintain a secondary assignment document (materialized view) keyed for fast per-user assignment queries. [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md#L88-L95), [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py#L55-L65)
- Ground-truth item writes should be consolidated into SME PUT and Curator PUT flows (with import remaining create-only). [backend/docs/api-write-consolidation-plan.v2.md](backend/docs/api-write-consolidation-plan.v2.md#L62-L65)

### Data & Storage Requirements
- The backend shall abstract persistence behind a repository protocol to support multiple backends (Cosmos as production backend). [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py#L17-L45), [backend/CODEBASE.md](backend/CODEBASE.md#L24-L30)
- The backend shall support local development using the Cosmos DB Emulator and should not block startup if Cosmos initialization fails (e.g., emulator not ready). [backend/app/main.py](backend/app/main.py#L60-L82)
- The system shall account for Cosmos DB Emulator query limitations (e.g., lack of `ARRAY_CONTAINS`) by adjusting behavior and/or skipping incompatible tests. [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md#L5-L25)
- The system may support a Cosmos emulator-specific Unicode escape workaround when configured (to avoid emulator-only invalid escape failures). [backend/docs/cosmos-emulator-unicode-workaround.md](backend/docs/cosmos-emulator-unicode-workaround.md#L35-L38)

### Export / Snapshot Requirements
- The backend shall support snapshot export in `attachment` (single JSON) and `artifact` (per-item JSON + manifest) modes with defined defaults when no request body is provided. [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L24-L33)
- The snapshot download endpoint shall return a JSON document payload (not artifacts). [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L34-L40)
- Artifact exports shall include a manifest with a stable `schemaVersion` and related snapshot metadata. [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L81-L93)
- Export processors shall run before formatting and may merge tag fields into a single exported `tags` array. [backend/docs/export-pipeline.md](backend/docs/export-pipeline.md#L117-L127)

### Observability & Operations Requirements
- Client telemetry shall be opt-in, disabled by default, and safe-by-default (no-op in demo mode or when configuration is missing). [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L17), [frontend/README.md](frontend/README.md#L82-L92)
- The UI shall provide an error boundary that catches rendering errors and renders a user-friendly fallback (and may integrate with telemetry when enabled). [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L79-L86)

### Security & Privacy Requirements
- In development, the system should support user simulation via an `X-User-Id` header to drive per-user assignment behavior and testing. [backend/README.md](backend/README.md#L336-L338), [frontend/README.md](frontend/README.md#L27-L32)

### Quality / Testing Requirements
- Tag normalization should be deterministic (normalize + deduplicate + sort) to ensure stable storage and comparisons. [backend/docs/tagging_plan.md](backend/docs/tagging_plan.md#L54-L57)
- Emulator-incompatible tests (or behaviors) should be gated or skipped to avoid false failures in local/emulator workflows. [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md#L9-L12)

## Gaps and Conflicts

- Reference search capability conflicts across frontend docs: MVP doc claims no backend search API endpoint, while the codebase guide describes a backend `searchReferences` flow used by the UI. [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L27-L31), [frontend/CODEBASE.md](frontend/CODEBASE.md#L141-L142)
- Tag semantics/validation scope is ambiguous between “canonical `group:value` tags” and per-history optional tags (unclear whether the same normalization/validation rules apply). [backend/docs/tagging_plan.md](backend/docs/tagging_plan.md#L5-L13), [backend/docs/history-tags-feature.md](backend/docs/history-tags-feature.md#L3-L6)
- Tag registry write expectations conflict: MVP doc states “allow the user to create new tags” while also stating “no write endpoints for tags.” [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L22-L24)
- Cosmos emulator Unicode workaround coverage may be inconsistent: workaround doc claims it is applied to tag storage, but the tags repo upsert path shown does not indicate any special encoding/sanitization. [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L111-L123), [backend/app/adapters/repos/tags_repo.py](backend/app/adapters/repos/tags_repo.py#L131-L141)

## Next Validation Questions

- Should reference search be treated as a required capability (backend API exists/should exist), or is it optional/stubbed for now? [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L27-L31), [frontend/CODEBASE.md](frontend/CODEBASE.md#L141-L142)
- For tags: are users allowed to create new tags end-to-end, and if so, what is the intended write path (if “no write endpoints” remains true)? [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L22-L24), [backend/app/adapters/repos/tags_repo.py](backend/app/adapters/repos/tags_repo.py#L131-L154)
- For multi-turn: is backend persistence expected to include reference relevance fields (relevant/neutral/irrelevant), or is that currently frontend-only state? [frontend/IMPLEMENTATION_SUMMARY.md](frontend/IMPLEMENTATION_SUMMARY.md#L93-L151)
- For assignments: confirm intended semantics for listing “my assignments” (draft-only vs broader statuses) and how single-item assignment should interact with those semantics. [backend/CODEBASE.md](backend/CODEBASE.md#L154-L156), [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md#L29-L39)
- For Cosmos emulator Unicode handling: should tag registry writes also apply the configured workaround (as docs imply), or should the docs be updated to reflect current behavior? [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L111-L123), [backend/app/adapters/repos/tags_repo.py](backend/app/adapters/repos/tags_repo.py#L131-L141)

## PRD Items Not Yet Supported (Tracked Separately)

> These appear in PRD artifacts but are not clearly supported by the existing frontend/backend system behaviors today.

- AI-powered reference retrieval (attach/detach, query orchestration) and LLM-generated artifacts. Source PRD artifacts: [prd.json](prd.json), [ralph/ralph-prd.txt](ralph/ralph-prd.txt)
- Dedicated tag administration endpoints/UI beyond current normalization + selection behaviors. Source PRD artifacts: [prd.json](prd.json)
- Full auth/RBAC integration (e.g., Entra) beyond the dev `X-User-Id` simulation mechanism. Source PRD artifacts: [prd.json](prd.json)

For a fuller breakdown (with evidence + “matches existing system” flags), see: [.copilot-tracking/subagent/20260121/prd-requirements-research.md](.copilot-tracking/subagent/20260121/prd-requirements-research.md)
