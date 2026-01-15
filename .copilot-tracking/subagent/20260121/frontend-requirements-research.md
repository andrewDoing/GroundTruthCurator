# Frontend requirements research (from frontend docs)

Date: 2026-01-21
Scope: Research-only inference of **high-level** frontend UX requirements that match the existing system.

## Sources reviewed

- [frontend/README.md](../../frontend/README.md)
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md)
- [frontend/IMPLEMENTATION_SUMMARY.md](../../frontend/IMPLEMENTATION_SUMMARY.md)
- [frontend/BACKEND_API_CHANGES.md](../../frontend/BACKEND_API_CHANGES.md)
- [frontend/docs/MVP_REQUIREMENTS.md](../../frontend/docs/MVP_REQUIREMENTS.md)
- [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](../../frontend/docs/OBSERVABILITY_IMPLEMENTATION.md)
- [frontend/src/components/app/defaultCurateInstructions.md](../../frontend/src/components/app/defaultCurateInstructions.md)

## Inferred high-level UX requirements

### 1) Runtime configuration and local development

- The frontend must support configuring the backend base URL, OpenAPI schema URL, and a dev-only user identifier via environment variables.
- In local development, the frontend should call backend APIs under `/v1/...` and rely on a dev proxy to avoid CORS.
- The UI should support a configurable default “self-serve assignment” limit.

Evidence:
- [frontend/README.md](../../frontend/README.md#L20-L44)

> - `VITE_API_BASE_URL` – backend base URL …
> - `VITE_OPENAPI_URL` – OpenAPI spec URL …
> - `VITE_DEV_USER_ID` – optional dev-only user id sent as `X-User-Id`
> - `VITE_SELF_SERVE_LIMIT` – optional default for self-serve assignments
> … all requests to `/v1/...` are proxied to `VITE_API_BASE_URL` …

### 2) App shape: single-page, multi-pane curation workspace

- The app is a single-page experience (no router required by default) with a multi-pane curation workspace.
- The primary workspace must separate concerns into:
  - Left: queue of items
  - Center: editor and actions
  - Right: references (search vs selected)
  - Additional views: stats, and other overlays/modals.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L70-L80)

> “A single-page React app.”
> “UX separation: Left queue, center editor … right references pane … stats view, and modal overlays.”

### 3) Assignment-based workflows and queue navigation

- The primary worklist must be “assigned items” (the curator’s current work queue).
- The queue should:
  - Display each item’s ID, status, version, and a truncated question.
  - Support selecting an item to edit.
  - Support refreshing/reloading the list.
  - Highlight deleted items.
- The UI should provide a “self-serve assignments” action in/near the queue to request more assigned work, using a configurable limit.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L128-L148)

> “items: list shown in Queue, updated on save/refresh”
> “viewMode: … ‘curate’ … ‘questions’ … ‘stats’”
> “Self-serve assignments – Queue offers a button to request more assignments (limit via `VITE_SELF_SERVE_LIMIT`).”

### 4) Editing flow (single-turn baseline)

- The editor must allow updating question/answer content for the current item.
- “Change category” is no longer required for saving; the UI should not block saving on that.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L86-L95)

> “Change category: previously required when Q/A changed; no longer enforced.”

### 5) References: search, add, select, visit/open, and annotate

- The right panel must provide two distinct reference experiences:
  - Search tab: search for candidate references and add them into the item.
  - Selected tab: manage references already attached to the item.
- Search UX requirements:
  - Display search results and allow adding individual results.
  - Support multi-select add.
  - Prevent duplicate additions by URL (disable add when URL already present; de-dup by URL).
- Selected references UX requirements:
  - List attached references.
  - Allow toggling which references are selected.
  - Allow opening a reference (in a new tab) and marking it as visited.
  - Allow capturing a “key paragraph” per selected reference and show a counter/length affordance.
  - Allow removing a reference and undoing that removal within a time window.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L136-L144)

> “ref opening: marks visited and opens in a new tab …”
> “Search tab: … supports multi-select Add … disabled when URL already present; de-dup by URL.”
> “Selected tab: … visit/open … key paragraph with counter; Remove supports Undo (8s window).”

Additional evidence (curation guidance shown to users):
- [frontend/src/components/app/defaultCurateInstructions.md](../../frontend/src/components/app/defaultCurateInstructions.md#L1-L4)

> “Include references you actually visited; for selected ones, write a key paragraph (≥ 40 chars).”

### 6) Approval gating and validation

- The UI must gate “Approve” based on reference completeness:
  - Requires at least one selected reference.
  - If references exist, all references must be visited.
  - Selected references must have a key paragraph of at least 40 characters.
  - Deleted items cannot be approved.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L75-L79)

> “Approval constraints: … at least one selected reference … all refs visited; selected refs have ≥40 char key paragraph. Deleted items cannot be approved.”

### 7) Save semantics and user feedback

- Save must be idempotent and detect “no-op” updates (avoid re-saving when nothing changed).
- If there are no changes, the UI should communicate “No changes”.
- Status-only updates should not be treated as content changes (no need to present them as version bumps in UX).

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L140-L146)

> “Save – computes state fingerprint; if unchanged: returns ‘No changes’.”

### 8) Soft delete / restore workflows

- Users must be able to soft-delete items and restore them.
- Deleted items should visibly indicate deletion and be non-approvable.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L145-L147)

> “Soft delete – … deleted items show a banner and cannot be approved; restore supported.”

### 9) Export UX

- Export should trigger a backend-driven snapshot download (JSON) rather than an in-app export modal.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L145-L146)

> “Export – triggers backend snapshot download … no in-app JSON modal.”

### 10) Tags: manage existing tags on an item

- The UI must support applying tags to the current ground-truth item.
- Tag creation is not required (and may not be supported by the backend); the UX should focus on selecting from a known set.
- Tag validation may be constrained by a fixed schema.

Evidence:
- [frontend/docs/MVP_REQUIREMENTS.md](../../frontend/docs/MVP_REQUIREMENTS.md#L22-L27)

> “get the known set of existing tags … (`GET /tags/schema`)”
> “allow the user to create new tags (no write endpoints for tags)”
> “apply the tags to the current ground truth …”
> “tag validation … fixed schema”

### 11) Curation instructions

- The UI must surface curation instructions as user-consumable markdown.
- Instructions are expected to be fetchable and writable per dataset (with concurrency control).

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L86-L92)

> `curationInstructions?: string`

- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L165-L168)

> “InstructionsPane … collapsible curation instructions surfaced per item”

- [frontend/docs/MVP_REQUIREMENTS.md](../../frontend/docs/MVP_REQUIREMENTS.md#L15-L18)

> “get curation instructions (`GET /datasets/{datasetName}/curation-instructions`)”
> “write curation instructions (`PUT /datasets/{datasetName}/curation-instructions` with ETag)”

### 12) Multi-turn curation (conversation history)

- The UI must support multi-turn conversation editing in addition to classic single-turn Q/A.
- It must provide:
  - A timeline view of conversation turns.
  - Adding/editing/deleting turns.
  - An optional “context” field for application/product context.
  - A mode toggle (single-turn vs multi-turn) with auto-detection and persistence.
- Multi-turn approval adds requirements beyond single-turn:
  - Must contain at least one user turn and one agent turn.
  - All references must be marked with a relevance state.
  - All “relevant” references must have key paragraphs ≥ 40 characters.

Evidence:
- [frontend/IMPLEMENTATION_SUMMARY.md](../../frontend/IMPLEMENTATION_SUMMARY.md#L88-L112)

> “Mode Toggle … Auto-detection … Persistence: Saves preference to localStorage”
> “Reference Relevance Tracking … Requires all references to be marked before approval …”
> “Application Context … Collapsible Editor …”

- [frontend/IMPLEMENTATION_SUMMARY.md](../../frontend/IMPLEMENTATION_SUMMARY.md#L147-L158)

> “Multi-Turn Approval Requirements … All references marked … All ‘relevant’ references have key paragraphs ≥40 chars …”

### 13) Keyboard shortcuts

- The app should support global shortcuts for primary curation actions:
  - Cmd/Ctrl+S: save draft.
  - Cmd/Ctrl+Enter: attempt approve (still gated by validation).

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L184-L184)

> “Keyboard shortcuts: Cmd/Ctrl+S saves draft; Cmd/Ctrl+Enter attempts approve (gated)”

### 14) Error handling and user feedback surfaces

- The UI should provide toast-based feedback for:
  - Network failures (and keep state consistent).
  - Undo interactions (reference removal undo window).
  - Browser popup blocking when opening references in new tabs.

Evidence:
- [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L215-L233)

> “Undo delete window: 8 seconds via toast action …”
> “Network failures … show toast and keep state consistent”
> “Popup blocked on new tab: info toast prompts user”

### 15) Telemetry / observability (optional, safe-by-default)

- Telemetry must be opt-in, safe, and no-op when disabled (including demo mode).
- The UI should have a user-friendly error boundary for rendering failures, and log exceptions to telemetry when enabled.

Evidence:
- [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](../../frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L13-L18)

> “Opt-in … Telemetry is disabled by default …”
> “Safe: No-ops gracefully in demo mode or when configuration is missing”

- [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](../../frontend/docs/OBSERVABILITY_IMPLEMENTATION.md#L79-L86)

> “Error Boundary … Catches rendering errors … Renders a user-friendly fallback UI …”

### 16) Demo mode

- The UI must support a “demo mode” that toggles behavior at startup via environment variables.
- Demo mode should disable telemetry and may use mock providers/services.

Evidence:
- [frontend/README.md](../../frontend/README.md#L74-L92)

> “VITE_DEMO_MODE … to enable demo behavior”
> “Telemetry automatically no-ops in demo mode …”

## Noted doc drift / open questions (for follow-up)

- Search + generation backend availability appears inconsistent across docs:
  - [frontend/docs/MVP_REQUIREMENTS.md](../../frontend/docs/MVP_REQUIREMENTS.md#L28-L36) states no backend search/LLM endpoints.
  - [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L136-L145) describes search and generation flows calling backend (`searchReferences`, `callAgentChat`).
  - This may be historical vs current behavior; confirm actual endpoints and desired UX when offline/backends are missing.

- Export behavior differs by context:
  - [frontend/CODEBASE.md](../../frontend/CODEBASE.md#L145-L146) states Export triggers snapshot download.
  - Multi-turn export expansion is described as part of model/export logic in [frontend/IMPLEMENTATION_SUMMARY.md](../../frontend/IMPLEMENTATION_SUMMARY.md#L110-L112). Confirm whether export expansion is implemented in frontend, backend, or both.
