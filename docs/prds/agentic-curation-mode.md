<!-- markdownlint-disable-file -->
<!-- markdown-table-prettify-ignore-start -->
# Agentic Curation Mode — Product Requirements Document (PRD)
Version 0.4 | Status DRAFT | Owner TBD | Team Ground Truth Curator | Target TBD | Lifecycle Discovery

## Progress Tracker
| Phase | Done | Gaps | Updated |
|-------|------|------|---------|
| Context | ✅ | — | 2026-03-09 |
| Problem & Users | ✅ | Persona validation | 2026-03-09 |
| Scope | ✅ | — | 2026-03-09 |
| Requirements | ✅ | Edge cases, AI-assisted editing details | 2026-03-09 |
| Metrics & Risks | ⬜ | Success metrics, risk owners | — |
| Operationalization | ⬜ | Deployment runbook, monitoring | — |
| Finalization | ⬜ | Stakeholder approval | — |
Unresolved Critical Questions: 3 | TBDs: 4

## 1. Executive Summary
### Context
The Ground Truth Curator platform currently supports a single curation workflow focused on RAG (Retrieval-Augmented Generation) ground truth items — question/answer pairs with reference grounding. A new class of AI system — agentic orchestration — requires a fundamentally different curation approach. Agentic systems involve agents, tool/subagent calls with execution traces, and structured decision-making about which tools were necessary to reach correct answers.

The existing curation UI and data model (v2 schema) cannot accommodate agentic ground truth because the data structures, validation rules, and approval workflows differ at every layer. Rather than forcing agentic data into the RAG model, this initiative creates a dedicated agentic curation mode that runs as an isolated deployment sharing the same codebase.

### Core Opportunity
Enable curators to review, edit, validate, and approve agentic ground truth data — including agent conversations, tool call decisions, and trace evidence — through a purpose-built interface that maintains the same quality standards and operational patterns as the existing RAG curation system.

### Goals
| Goal ID | Statement | Type | Baseline | Target | Timeframe | Priority |
|---------|-----------|------|----------|--------|-----------|----------|
| G-001 | Enable curators to review and approve agentic ground truth items with tool call decision annotation | Business | No agentic curation capability | Full curation workflow operational | TBD | P0 |
| G-002 | Achieve deployment isolation so agentic mode has zero impact on existing RAG curation workflows | Technical | Single-mode system | Two independent deployments from shared codebase | TBD | P0 |
| G-003 | Support the agentic-core/v1 schema (gt_schema_v5_generic.py) for all CRUD and curation operations | Technical | Only v2 RAG schema supported | Full agentic schema support | TBD | P0 |
| G-004 | Provide AI-assisted editing capabilities for agent responses and tool call decisions | Product | Manual-only editing | AI suggestion generation for turn edits and tool decisions | Post-MVP | P2 (Deferred) |
| G-005 | Achieve curation throughput of ≥3 items per curator per hour | Operational | 0 (no agentic curation) | ≥3 items/curator/hour | TBD | P1 |

### Objectives (Optional)
| Objective | Key Result | Priority | Owner |
|-----------|------------|----------|-------|
| Deliver agentic editor MVP | Curators can approve agentic items with tool call decisions | P0 | TBD |
| Zero RAG regression | All existing RAG tests pass, no RAG deployment changes | P0 | TBD |
| Config-gated deployment | Single env var selects mode at deploy time; tree-shaking eliminates unused code | P1 | TBD |

## 2. Problem Definition
### Current Situation
The Ground Truth Curator was built for RAG use cases: curators review synthesized questions, edit answers, validate grounding references, and approve items. The data model (v2) centers on question/answer pairs with per-turn references and expected behaviors.

Agentic AI systems produce fundamentally different artifacts:
- **Agent conversations with flexible roles**: Primarily single-turn (user query → agent response), but the schema supports multi-turn for generic use cases. The `role` field is a free-form string — the system is deliberately unopinionated about role names. In some deployments subagents appear as tool calls rather than distinct conversation turns; in others, agents may perform explicit handoffs as first-class turns. The curation system supports both patterns without prescribing one.
- **Tool call traces**: Ordered sequences of API/tool calls with execution times, parallel groups, and nested subagent calls. Subagents typically surface as tool calls in the primary system this is being built for.
- **Tool decision annotation**: Curators must decide which tool calls were *required*, *optional*, or *not needed* for the correct answer
- **Trace-based evidence**: Evidence comes from execution traces and tool responses, not searchable reference documents
- **Structured context**: Key-value context entries attached to each ground truth, not embedded in reference paragraphs

None of these can be represented in the v2 schema or curated through the existing UI.

### Problem Statement
The Ground Truth Curator cannot ingest, display, or curate agentic ground truth data, blocking the creation of evaluation datasets for agentic AI systems. Without agentic ground truth, these systems cannot be systematically evaluated for correctness of tool usage, response quality, or orchestration behavior.

### Root Causes
* The v2 data model lacks fields for tool calls, expected tools, trace payloads, context entries, and flexible conversation roles
* The frontend editor assumes two fixed roles (user/assistant) and reference-based grounding
* Approval validation gates on reference completeness, which doesn't apply to agentic items
* No mechanism exists to annotate individual tool calls with required/optional/not-needed decisions

### Impact of Inaction
* Agentic AI systems ship without systematic ground truth evaluation
* Quality assessment of tool usage and orchestration behavior remains ad-hoc
* No standardized dataset format for agentic evaluation benchmarks
* Curator expertise in RAG evaluation cannot be extended to agentic systems

## 3. Users & Personas
| Persona | Goals | Pain Points | Impact |
|---------|-------|------------|--------|
| **Agentic Curator** — SME who reviews agent traces and annotates tool call decisions | Efficiently review agent conversations; mark tool calls as required/optional/not-needed; edit agent responses for accuracy; approve high-quality ground truth | Must currently review traces in raw JSON; no structured workflow for tool call annotation; no validation that ensures completeness before approval | Primary user — performs all curation actions |
| **Curation Lead** — Manages curator assignments and monitors quality metrics | Assign agentic items to curators; monitor approval rates and quality; export approved datasets | Cannot track agentic curation progress; no stats dashboard for agentic metrics | Manages workflow and quality |
| **ML Engineer** — Consumes approved ground truth for model evaluation | Import high-quality agentic ground truth datasets; use tool call annotations for evaluation pipelines | No structured agentic ground truth exists; must manually create evaluation data | Downstream consumer |
| **RAG Curator** — Existing user of RAG curation mode | Continue using RAG curation without disruption | Any changes to shared code could regress RAG workflows | Must not be impacted |

### Journeys (Optional)
**Agentic Curator Journey:**
1. Self-serve to claim agentic items from queue
2. Review user query and agent conversation (typically single-turn; multi-turn when applicable)
3. Inspect trace data — tool calls with arguments, responses, execution times
4. For each tool call, decide: ★ Required / ○ Optional / ✕ Not needed
5. Edit agent responses if inaccurate (with optional AI assistance)
6. Add/edit user context key-value pairs
7. Manage tags (manual + computed)
8. Add curator notes
9. Save draft or approve (approval gated on validation)

## 4. Scope
### In Scope
* **Backend: Agentic data model** — `AgenticGroundTruthEntry` Pydantic model based on `gt_schema_v5_generic.py` with all fields: history, context_entries, tool_calls, expected_tools, trace_ids, trace_payload, feedback, metadata, plugins, provenance
* **Backend: Config-gated DI** — `CURATION_MODE` environment variable selecting RAG vs agentic model, plugins, and validators at startup
* **Backend: Agentic validation** — Approval validator enforcing conversation structure (≥1 turn, first turn is user, no empty messages), tool call decisions (≥1 required), and history completeness
* **Backend: Agentic computed tag plugins** — Mode-specific tag plugins (e.g., ToolCallCountPlugin, AgentRolePlugin) registered via existing `TagPluginRegistry`
* **Backend: CRUD operations** — Bulk import, paginated list, assignment lifecycle, update, snapshot/export for agentic items
* **Frontend: Agentic editor component tree** — `AgenticEditor`, `AgenticToolCallGrid`, `AgenticEvidencePanel` replacing RAG-specific components
* **Frontend: Tool call decision UI** — Segmented toggle per tool call (★ Required / ○ Optional / ✕ Not needed) with grid display showing order, function name, parallel group, execution time
* **Frontend: Conversation editor** — Role-agnostic conversation display supporting any number of turns with per-role badges, inline editing, and markdown rendering
* **Frontend: User context management** — Key-value entry CRUD for attaching context to ground truth items
* **Frontend: AI-assisted editor modal** — Deferred to post-MVP. V1 uses manual editing only
* **Frontend: Config-gated rendering** — `VITE_CURATION_MODE` compile-time constant selecting editor component; Vite tree-shaking eliminates unused mode code
* **Frontend: Agentic validation and approval gating** — `canApproveAgentic()` enforcing conversation structure and tool call requirements
* **Frontend: Agentic type definitions** — `AgenticGroundTruthItem` TypeScript types matching the v5 schema
* **Frontend: Tags management** — Manual + computed tags with modal editor (shared pattern, agentic tag vocabulary)
* **Frontend: Metadata & trace info panel** — Collapsible panel showing trace IDs, trace source, user feedback scores
* **Infrastructure: Separate deployment configuration** — Environment variables, Cosmos DB container per deployment

### Out of Scope (justify if empty)
* **Runtime mode toggle** — Mode is per-deployment, not user-selectable (architectural decision per isolation research)
* **AI-assisted editor** — Suggestion generation for turn edits and tool decisions deferred to post-MVP; V1 uses manual editing only
* **Rules engine plugin** — `expected_annotations` and `expected_rule_triggers` fields exist in schema but UI/backend support deferred (Peter's feedback: separate tool/tab)
* **Trace ingestion pipeline** — How `trace_payload` and `tool_calls` are populated before curation is a separate system concern
* **Auth/RBAC changes** — Existing auth model applies to both modes without changes
* **Mixed-mode datasets** — A dataset contains only RAG or only agentic items, never both
* **Data migration** — No migration of existing RAG data; agentic deployment starts with empty container
* **`grounding_data_summary` field** — Removed per product decision
* **`evaluation_criteria` field** — Removed per product decision

### Assumptions
* Each deployment is dedicated to a single mode (RAG or agentic); they do not coexist at runtime
* The Cosmos DB container strategy (single container per deployment, MultiHash PK on `[datasetName, bucket]`) remains unchanged
* The `gt_schema_v5_generic.py` represents the target agentic data model (schema version: `agentic-core/v1`)
* The wireframe v2.2 (`agent-curation-wireframe-v2.2.html`) represents the target agentic UI
* Trace data is available before curation begins (populated by upstream ingestion)
* Tool calls are initially imported from trace data; SME-editable tool call management is deferred

### Constraints
* Zero changes to existing RAG deployment code paths — RAG mode must remain identical
* Shared codebase — both modes maintained in the same repository with clear module boundaries
* Pydantic v2 serialization contract (snake_case internal, camelCase wire format with aliases)
* ETag-based concurrency control for all mutations
* Provider abstraction pattern for data access (mode-agnostic interface)

## 5. Product Overview
### Value Proposition
The Agentic Curation Mode extends the Ground Truth Curator to support evaluation dataset creation for agentic AI systems. Curators can review agent conversations, annotate tool call necessity, edit agent responses, and approve ground truth items through a purpose-built interface — enabling systematic quality evaluation of agent orchestration, tool usage, and response accuracy.

### Differentiators (Optional)
* **Tool call decision annotation** — First-class UI for marking each tool/subagent call as required, optional, or not needed, with parallel group visualization
* **Role-agnostic conversation model** — Supports arbitrary role strings (e.g., user, agent, orchestrator-agent, output-agent) rather than fixed user/assistant pairs; adapts to diverse agentic architectures without prescribing a specific role taxonomy
* **Trace-based evidence** — Evidence derived from execution traces rather than document references, surfacing tool arguments and responses inline
* **Plugin-based extensibility** — `PluginPayload` slots allow opaque customer-specific or feature-specific data without schema changes
* **Config-gated deployment isolation** — Zero-risk to existing RAG mode; build-time code elimination ensures clean separation

### UX / UI (Conditional)
The agentic curation UI is defined by wireframe v2.2 (`wireframes/agent-curation-wireframe-v2.2.html`). Key UX patterns:

**Layout:** Split-pane design with resizable gutter — conversation/context on the left, trace/evidence on the right. Queue sidebar on the far left. Mobile-responsive with evidence drawer.

**Conversation Pane (Left):**
- User context key-value editor (add/edit/remove entries)
- Role-agnostic conversation display with per-role badges (colors assigned by role string; e.g., User = blue, agent roles = violet/amber). Supports single-turn and multi-turn conversations
- Inline editing per turn with save/cancel
- Markdown rendering for agent responses
- Collapsible turns
- Tags section with manual/computed tags and modal management

**Trace/Evidence Pane (Right):**
- Collapsible trace data panel with tool call count
- Trace metadata summary (trace_id, device, feedback type, date, resolution)
- Feedback scores display (1-5 scale visualization)
- Tool call grid with consistent column alignment:
  - Order number (#1, #2, ...)
  - Function name (monospace, dark badge)
  - Parallel group indicator (‖ P2, P3, P4)
  - Execution time
  - Decision badge (mini colored dot)
  - Expand/collapse chevron
- Expanded tool call detail:
  - Segmented toggle: ★ Required (emerald) / ○ Optional (sky) / ✕ Not needed (rose)
  - Arguments display (code block)
  - Result display (code block, scrollable)
- Metadata & trace info (collapsible details)

**Editor Modal (Deferred to post-MVP):**
- AI-assisted suggestion generation deferred; V1 relies on inline turn editing (FR-007)
- Future: prompt-based suggestions for turn edits, tool decisions, and context entries

**Actions Bar:**
- Save Draft / Approve (gated) / Skip / Delete / Restore / Duplicate
- Approval validation: conversation structure + ≥1 required tool call

**Component Extensibility Model:**
Several schema fields are intentionally flexible — they accept arbitrary dictionary structures or unconstrained types. The UI components that render these fields **must be pluggable** so that different data shapes can be visualized appropriately without code changes to the host editor.

| Schema Field | Type | Why Pluggable |
|---|---|---|
| `feedback[].values` | `dict[str, Any]` | Feedback structure varies by source system — may be numeric scores, Likert scales, free-text, or composite rubrics. The renderer must adapt to the shape of the `values` dict |
| `metadata` | `dict[str, Any]` | Arbitrary key-value metadata attached at ingestion time. May contain flat strings, nested objects, arrays, or domain-specific structures |
| `plugins[slot].data` | `dict[str, Any]` | Opaque plugin payloads — each slot may carry a completely different data shape (e.g., citation evidence vs. cost breakdown vs. safety classification) |
| `trace_payload` | `dict[str, Any]` | Raw trace data from upstream systems. Structure depends on the trace provider (e.g., OpenTelemetry spans, custom agent traces, LangSmith format) |
| `context_entries[].value` | `Any` | Context values may be strings, numbers, JSON objects, or arrays depending on the scenario |
| `tool_calls[].response` | `Any` | Tool call responses vary by tool — could be plain text, structured JSON, error objects, or binary references |

**Pluggable renderer contract:** Each flexible field must support a **default renderer** (generic key-value / JSON tree display) and allow registration of **custom renderers** selected by a discriminator (e.g., `feedback.source`, `plugins[slot].kind`, content-type heuristics). The component registry should:
- Render unknown/new data shapes gracefully with the default renderer (never crash on unexpected structure)
- Allow custom renderers to be registered without modifying core editor code
- Support lazy loading of custom renderers to preserve bundle size (aligns with NFR-007 tree-shaking)
- Provide a consistent wrapper (padding, collapse/expand, error boundary) regardless of which renderer is active

| UX Status: Wireframe v2.2 complete |

## 6. Functional Requirements
| FR ID | Title | Description | Goals | Personas | Priority | Acceptance | Notes |
|-------|-------|------------|-------|----------|----------|-----------|-------|
| FR-001 | Agentic data model | Implement `AgenticGroundTruthEntry` Pydantic model matching `gt_schema_v5_generic.py` with all fields: id, dataset_name, bucket, doc_type, schema_version, status, etag, assigned_to/at, updated_at/by, reviewed_at, manual_tags, computed_tags, history (list[HistoryEntry]), context_entries (list[ContextEntry]), trace_ids, tool_calls (list[ToolCallRecord]), expected_tools (ExpectedTools with required/optional/not_needed and overlap rejection), feedback (list[FeedbackEntry]), metadata, plugins (dict[str, PluginPayload]), comment, created_by/at, trace_payload | G-003 | ML Engineer | P0 | Model validates against gt_schema_v5_generic.py; all field validators pass; overlap rejection on ExpectedTools works; serialization uses camelCase aliases | Schema version: `agentic-core/v1`; doc_type: `ground-truth` |
| FR-002 | Config-gated mode selection | Add `CURATION_MODE` environment variable (values: `rag`, `agentic`) that selects model, plugins, validators at DI container startup. Frontend reads `VITE_CURATION_MODE` as compile-time constant | G-002 | RAG Curator, Agentic Curator | P0 | Setting `CURATION_MODE=agentic` loads agentic model and components; `CURATION_MODE=rag` (default) loads existing RAG model; no runtime mode toggle exists | Default is `rag` to protect existing deployments |
| FR-003 | Agentic bulk import | Accept bulk import of agentic ground truth items via `POST /ground-truths` endpoint in agentic deployment, validating against `AgenticGroundTruthEntry` schema | G-003 | ML Engineer | P0 | Import validates required fields; rejects items with ExpectedTools overlap; returns item count and error details | Same endpoint path as RAG, different validation |
| FR-004 | Agentic item listing | Serve paginated list of agentic items via `GET /ground-truths/{dataset}` with agentic schema serialization | G-003 | Agentic Curator | P0 | Returns items with all agentic fields in camelCase wire format; pagination, sorting, and filtering work identically to RAG mode | |
| FR-005 | Agentic assignment lifecycle | Support self-serve assignment, item locking (ETag), update, and status transitions (draft → approved, draft → skipped, soft delete/restore) for agentic items | G-001, G-003 | Agentic Curator, Curation Lead | P0 | Assignment, locking, and status transitions behave identically to RAG mode but operate on agentic model fields | Shared assignment service with injected model |
| FR-006 | Conversation display | Render conversation with role-specific badges and colors. The `role` field is a free-form string; the UI assigns badge colors dynamically per unique role (e.g., "user" = blue, other roles get assigned colors from palette). Support collapse/expand per turn. Render markdown in agent responses. Primarily single-turn (user → agent) but supports arbitrary turn counts | G-001 | Agentic Curator | P0 | Displays all history entries with dynamically-colored role badges; markdown headers, lists, bold, code render correctly; turns collapse/expand independently; works for 1-turn, 2-turn, and N-turn conversations | Role string is not validated against an enum — any value accepted |
| FR-007 | Inline conversation editing | Allow curators to edit any conversation turn's message text with save/cancel controls. Editing is disabled when item is deleted | G-001 | Agentic Curator | P0 | Edit button appears on each turn; textarea pre-filled with current text; save updates model; cancel reverts; deleted items show no edit button | |
| FR-008 | Tool call grid display | Display tool calls in ordered grid with columns: order number, function name, parallel group, execution time, decision badge, expand chevron. Sort by curator-defined order with parallel group grouping | G-001 | Agentic Curator | P0 | All tool calls from trace displayed; order reflects layout configuration; parallel groups shown with ‖ prefix; execution time in seconds; grid columns align across rows | |
| FR-009 | Tool call decision annotation | Provide per-tool segmented toggle with three states: ★ Required (emerald), ○ Optional (sky), ✕ Not needed (rose). Decisions persist on the item's `expected_tools` field | G-001 | Agentic Curator | P0 | Each tool call has a segmented toggle; clicking a segment updates the decision; decision reflected in mini badge on collapsed view; decisions map to ExpectedTools.required/optional/not_needed | Default decision is `optional` |
| FR-010 | Tool call detail expansion | Expand individual tool calls to show arguments (code block) and result (code block, scrollable, max height). Expanded view includes the segmented decision toggle with explanatory label | G-001 | Agentic Curator | P0 | Clicking tool call row expands detail; arguments and result render as formatted code; decision toggle is functional in expanded view | |
| FR-011 | Agentic approval validation | Gate approval on: (1) conversation has ≥1 turn, (2) no empty messages, (3) first turn is user, (4) at least one tool call marked required, (5) item not deleted. Validation does **not** mandate specific agent role names — any non-user role is acceptable | G-001 | Agentic Curator | P0 | Approve button disabled when any validation fails; validation errors shown as warnings; `canApproveAgentic()` returns false for invalid items | Validation is role-name-agnostic; does not require specific roles like "orchestrator-agent" or "output-agent" |
| FR-012 | User context management | CRUD interface for key-value context entries (ContextEntry). Add new entries, edit key/value inline, remove entries | G-001 | Agentic Curator | P0 | Context entries render as input pairs; add button creates blank entry; edit updates model; remove deletes entry; entries persist on save | |
| FR-013 | Tags management | Display computed tags (read-only, locked icon) and manual tags. Modal for managing manual tags from available tag vocabulary | G-001 | Agentic Curator | P1 | Computed tags show lock icon; manual tags toggleable via modal; tag changes persist on save | Shared pattern with RAG, agentic-specific tag vocabulary |
| FR-014 | Curator notes | Textarea for free-form curator comments on each item | G-001 | Agentic Curator | P1 | Comment textarea renders with current value; changes persist on save | Maps to `comment` field |
| FR-015 | Trace metadata display | Collapsible panel showing trace IDs, trace source (agent version, environment), and user feedback details | G-001 | Agentic Curator | P1 | Trace IDs render as key-value pairs; feedback scores display with color-coded scale; panel collapses/expands | |
| FR-016 | User feedback scores | Display feedback scores from trace data with question text and numerical score, color-coded (1=green agree, 5=red disagree) | G-001 | Agentic Curator | P1 | All feedback questions display with scores; color coding applied; scale legend shown | |
| FR-017 | ~~AI-assisted editor modal~~ | ~~Modal with prompt input that generates structured suggestions~~ | ~~G-004~~ | ~~Agentic Curator~~ | ~~Deferred~~ | ~~Deferred to post-MVP~~ | V1 uses inline editing only (FR-007); AI suggestions deferred |
| FR-018 | ~~Manual editor modal~~ | ~~Direct editing mode with role selector and full-text textarea~~ | ~~G-004~~ | ~~Agentic Curator~~ | ~~Deferred~~ | ~~Deferred to post-MVP~~ | Inline turn editing (FR-007) provides equivalent capability for V1 |
| FR-019 | Agentic snapshot/export | Export approved agentic items as dataset snapshot via `POST /ground-truths/snapshot` with agentic schema shape | G-003 | ML Engineer, Curation Lead | P1 | Export includes all agentic fields; only approved items exported; format matches agentic-core/v1 schema | Same endpoint, different formatter |
| FR-020 | Agentic computed tag plugins | Create agentic-specific computed tag plugins (ToolCallCountPlugin, AgentRolePlugin) registered in agentic deployment alongside shared plugins (TurnPlugin, DatasetPlugin) | G-001 | Curation Lead | P1 | ToolCallCountPlugin tags items by tool call count range; AgentRolePlugin tags by agent roles present; shared plugins work for both modes | |
| FR-021 | Queue sidebar | Display agentic items in queue with ID, category tag, status badge, and user message preview. Support item selection, refresh, and self-serve request | G-001 | Agentic Curator | P0 | Queue shows all assigned items; clicking selects item; status badges reflect current state; deleted items shown with reduced opacity | Shared layout with RAG mode |
| FR-022 | Explorer view | List/filter view for agentic items with agentic-specific columns | G-001 | Curation Lead | P1 | Explorer renders item list with filterable columns appropriate for agentic data | |
| FR-023 | Stats view | Metrics dashboard with agentic-specific metrics (tool call counts, approval rates, decision distributions) | G-005 | Curation Lead | P1 | Stats show approval rate, items by status, tool call decision breakdown | |
| FR-024 | Item actions | Save Draft, Approve (validation-gated), Skip (auto-advance), Delete (soft), Restore, Duplicate | G-001 | Agentic Curator | P0 | All actions update item status correctly; skip advances to next item; delete sets deleted flag; restore clears it; duplicate creates new draft with incremented ID | |
| FR-025 | Split-pane layout | Resizable split-pane with conversation/context on left and trace/evidence on right. Draggable gutter. Mobile-responsive with evidence drawer | G-001 | Agentic Curator | P0 | Desktop: split pane with draggable gutter; mobile (<1024px): evidence drawer slides in from right; gutter drag updates pane widths | |
| FR-026 | Plugin payload support | Support `set_plugin()` and `get_plugin_data()` for attaching opaque customer-specific data under named plugin slots with kind and version | G-003 | ML Engineer | P2 | Plugins persist correctly; set/get round-trips; multiple plugin slots supported simultaneously | Extension point for customer-specific data |
| FR-027 | Pluggable feedback renderer | The feedback panel must use a component registry to select a renderer based on `FeedbackEntry.source`. Default renderer displays `values` as a key-value table. Custom renderers can be registered for known sources (e.g., a Likert scale renderer for `source: "user-survey"`, a numeric score bar for `source: "auto-eval"`) | G-001 | Agentic Curator | P1 | Default renderer displays any `dict[str, Any]` as key-value pairs; custom renderer selected by source string; unknown sources fall back to default without error | See Component Extensibility Model in §5 |
| FR-028 | Pluggable metadata renderer | The metadata panel must render the top-level `metadata: dict[str, Any]` field using a pluggable component. Default renderer shows a collapsible JSON tree / key-value list. Custom renderers can be registered for specific metadata shapes (discriminated by key presence or a `_type` convention) | G-001 | Agentic Curator | P1 | Flat metadata renders as key-value table; nested metadata renders as collapsible tree; custom renderers override default for recognized shapes | |
| FR-029 | Pluggable plugin slot renderer | Each `plugins[slot]` entry must render via a component selected by `PluginPayload.kind`. Default renderer shows `kind`, `version`, and `data` as a collapsible JSON tree. Custom renderers can be registered per `kind` value to provide domain-specific visualization | G-001, G-003 | Agentic Curator, ML Engineer | P2 | Each plugin slot renders independently; unknown `kind` values use default renderer; custom renderers registered by kind string | Parallel to backend FR-026 plugin support |
| FR-030 | Pluggable trace payload renderer | The trace payload panel must render `trace_payload: dict[str, Any]` via a pluggable component. Default renderer shows a collapsible JSON tree with syntax highlighting. Custom renderers can be registered for known trace formats (e.g., OpenTelemetry span viewer, LangSmith trace timeline) | G-001 | Agentic Curator | P2 | Default renderer handles arbitrary dict structures; large payloads are virtualized or paginated; custom renderers selected by trace format heuristics or explicit `_format` key | |
| FR-031 | Pluggable context value renderer | Each `ContextEntry.value` (typed `Any`) must render via a pluggable component. Default renderer applies type-appropriate display: strings as text, numbers as formatted values, objects/arrays as collapsible JSON. Custom renderers can be registered for specific `key` patterns | G-001 | Agentic Curator | P1 | String values render as editable text; JSON values render as collapsible tree; unknown types render via `JSON.stringify` fallback | |
| FR-032 | Pluggable tool response renderer | Each `ToolCallRecord.response` (typed `Any`) must render via a pluggable component in the expanded tool call detail view. Default renderer shows a code block. Custom renderers can be registered for specific tool names to provide structured visualizations (e.g., table for search results, map for geolocation responses) | G-001 | Agentic Curator | P2 | Default renders response as syntax-highlighted code block; custom renderers selected by `ToolCallRecord.name`; error responses render with error styling | |
| FR-033 | Component renderer registry | Implement a central registry where pluggable renderers are registered with a discriminator key and component reference. Registry supports: register, lookup with fallback to default, lazy import for custom renderers. Registry is initialized at app startup per curation mode | G-001, G-003 | ML Engineer | P1 | Registry API: `register(field, discriminator, component)`, `resolve(field, discriminator) → component`; unknown discriminators return default renderer; registry is tree-shakeable per curation mode | Shared infrastructure for FR-027 through FR-032 |

### Feature Hierarchy (Optional)
```plain
Agentic Curation Mode
├── Backend
│   ├── AgenticGroundTruthEntry model (FR-001)
│   ├── Config-gated DI (FR-002)
│   ├── CRUD operations (FR-003, FR-004, FR-005)
│   ├── Approval validation (FR-011)
│   ├── Computed tag plugins (FR-020)
│   └── Snapshot/export (FR-019)
├── Frontend
│   ├── AgenticEditor (FR-006, FR-007, FR-025)
│   ├── AgenticToolCallGrid (FR-008, FR-009, FR-010)
│   ├── User context management (FR-012)
│   ├── Tags management (FR-013)
│   ├── Trace/evidence panel (FR-015, FR-016)
│   ├── AI-assisted editor (FR-017, FR-018) [DEFERRED post-MVP]
│   ├── Validation & approval (FR-011, FR-024)
│   ├── Queue sidebar (FR-021)
│   ├── Explorer & Stats (FR-022, FR-023)
│   ├── Curator notes (FR-014)
│   └── Pluggable UI Component System
│       ├── Component renderer registry (FR-033)
│       ├── Feedback renderer (FR-027)
│       ├── Metadata renderer (FR-028)
│       ├── Plugin slot renderer (FR-029)
│       ├── Trace payload renderer (FR-030)
│       ├── Context value renderer (FR-031)
│       └── Tool response renderer (FR-032)
└── Infrastructure
    ├── Deployment configuration (FR-002)
    └── Cosmos DB container per mode
```

## 7. Non-Functional Requirements
| NFR ID | Category | Requirement | Metric/Target | Priority | Validation | Notes |
|--------|----------|------------|--------------|----------|-----------|-------|
| NFR-001 | Performance | Tool call grid renders without jank for items with up to 20 tool calls | First contentful paint ≤ 500ms for 20 tool calls | P0 | Performance test with 20-call dummy item | Production upper bound is 20 tool calls per item |
| NFR-002 | Performance | Agentic item save (draft) completes within existing latency bounds | Save round-trip ≤ 2s (P95) | P0 | Load test with agentic payloads | Agentic payloads are larger due to trace_payload |
| NFR-003 | Reliability | ETag concurrency control prevents lost updates on agentic items | Zero lost updates under concurrent editing | P0 | Concurrent save test | Same mechanism as RAG mode |
| NFR-004 | Scalability | Bulk import handles ≥1000 agentic items per batch | 1000-item import completes without timeout | P1 | Import load test | Agentic items are larger than RAG items |
| NFR-005 | Security | Agentic deployment inherits existing auth/RBAC without modification | All existing security controls enforced | P0 | Security review | No new auth surface |
| NFR-006 | Accessibility | Tool call decision toggles are keyboard-navigable and screen-reader accessible | WCAG 2.1 AA for segmented toggles | P1 | Accessibility audit | `role="radiogroup"`, `aria-pressed` attributes per wireframe |
| NFR-007 | Maintainability | Agentic code is tree-shaken from RAG builds and vice versa | RAG bundle size unchanged after agentic code added | P1 | Bundle analysis | Vite compile-time constant enables dead-code elimination |
| NFR-008 | Maintainability | Agentic model has >90% unit test coverage | ≥90% line coverage for agentic_models.py | P0 | Coverage report | Includes validator tests for ExpectedTools overlap rejection |
| NFR-009 | Observability | Agentic CRUD operations emit structured logs with operation name, RU charge, and elapsed time | All agentic Cosmos queries logged with metrics | P1 | Log review | Uses existing query metrics framework |
| NFR-010 | Maintainability | Schema validation rejects unknown fields (extra="forbid") | Unknown field in payload returns 422 | P0 | Unit test | Pydantic v2 strict mode per schema definition |
| NFR-011 | Extensibility | Pluggable renderer registry adds zero overhead when no custom renderers are registered (default renderers inline, custom renderers lazy-loaded) | Registry initialization ≤ 5ms; no additional network requests until custom renderer is needed | P1 | Startup performance test with default-only config | Supports FR-033; lazy loading aligns with NFR-007 tree-shaking |
| NFR-012 | Extensibility | Adding a new custom renderer for a flexible field requires no changes to the host editor component — only a registry entry and the renderer component itself | New renderer integrable with ≤ 2 files changed (registry config + new component) | P1 | Developer experience review | Open/closed principle for UI extensibility |
| NFR-013 | Reliability | Pluggable renderers must be wrapped in error boundaries. A failing custom renderer must fall back to the default renderer with a warning, never crash the editor | Custom renderer throwing error → default renderer displayed + console warning; editor remains interactive | P0 | Error injection test for each renderer slot | Critical for production stability with arbitrary data shapes |

## 8. Data & Analytics (Conditional)
### Inputs
* **Agentic ground truth items** — Imported via bulk import API from upstream trace processing pipeline. Each item contains conversation history, tool call records, trace payload, and metadata.
* **Trace data** — Embedded in `trace_payload` field as opaque dict; tool calls extracted from trace context entries.
* **User feedback** — Embedded in `metadata` or `feedback` fields as structured key-value pairs from upstream systems.

### Outputs / Events
* **Approved dataset snapshots** — Exported via snapshot API for consumption by ML evaluation pipelines.
* **Curation activity metrics** — Items curated, approval rate, tool call decision distributions, time-to-approve.

### Instrumentation Plan
| Event | Trigger | Payload | Purpose | Owner |
|-------|---------|--------|---------|-------|
| `agentic.item.approved` | Curator approves item | item_id, dataset_name, tool_calls_count, required_count, optional_count, not_needed_count | Track approval patterns and tool decision distributions | TBD |
| `agentic.item.saved` | Curator saves draft | item_id, dataset_name, fields_modified | Track curation progress and field edit frequency | TBD |
| `agentic.bulk_import` | Bulk import completes | dataset_name, item_count, error_count, elapsed_ms | Monitor import pipeline health | TBD |
| `agentic.editor.suggestion` | AI editor generates suggestions | item_id, prompt_length, suggestion_count, suggestion_types | Track AI assistance usage and effectiveness | TBD (post-MVP) |

### Metrics & Success Criteria
| Metric | Type | Baseline | Target | Window | Source |
|--------|------|----------|--------|--------|--------|
| Agentic items approved per curator per hour | Throughput | 0 | ≥3 | Weekly | Database query |
| Tool call decision coverage | Quality | N/A | 100% of tool calls have decisions before approval | Per-item | Validation gate |
| Approval validation pass rate | Quality | N/A | >80% of save attempts pass validation on first try | Weekly | API logs |
| AI suggestion acceptance rate | Adoption | N/A | Deferred to post-MVP | — | — |
| RAG mode regression rate | Safety | 0 failures | 0 failures | Per-release | CI/CD |

## 9. Dependencies
| Dependency | Type | Criticality | Owner | Risk | Mitigation |
|-----------|------|------------|-------|------|-----------|
| Trace ingestion pipeline | External system | High | TBD | Agentic items cannot be curated without populated trace data | Define minimum trace data contract; support items without trace for partial curation |
| gt_schema_v5_generic.py | Schema definition | High | Ground Truth Curator team | Schema changes invalidate backend model | Pin schema version; migration path for schema evolution |
| Wireframe v2.2 | UI specification | High | Ground Truth Curator team | UI changes require component rework | Wireframe is stable (v2.2); changes tracked via versioning |
| Existing RAG curation system | Shared codebase | High | Ground Truth Curator team | Changes to shared modules could affect both modes | Clear module boundaries; shared vs mode-specific code separation; comprehensive tests |
| Cosmos DB | Infrastructure | High | Platform team | Separate container provisioning required for agentic deployment | Use existing container provisioning patterns; separate RU allocation |
| Pydantic v2 | Library | Medium | — | Library updates could affect model behavior | Pin version in requirements; test validators after updates |

## 10. Risks & Mitigations
| Risk ID | Description | Severity | Likelihood | Mitigation | Owner | Status |
|---------|-------------|---------|-----------|-----------|-------|--------|
| R-001 | Shared codebase changes to common modules (auth, assignment lifecycle, DI container) could introduce regressions in either mode | High | Medium | 10-layer defense-in-depth strategy: directory-enforced module boundaries, DI container as sole branch point, protocol abstractions for shared services, CI boundary lint rules, CI mode matrix testing both modes, RAG regression gate job, RAG-default configuration, startup schema validation, separate Cosmos containers, and frontend bundle size gate. See [R-001 Mitigation Research](../../.copilot-tracking/research/20260310-r001-regression-mitigation-research.md) for full analysis and phased implementation plan. | TBD | Open |
| R-002 | Agentic item payloads significantly larger than RAG (due to trace_payload) could impact Cosmos RU costs and latency | Medium | Medium | Monitor RU costs per operation; consider trace_payload compression or separate storage if costs exceed threshold | TBD | Open |
| R-003 | Tool call grid performance degrades with high tool call counts (>50 per item) | Medium | Low | Virtual scrolling for large lists; lazy-load tool call details on expand; performance test with 50+ tool calls | TBD | Open |
| R-004 | ~~AI-assisted editor suggestions may not meet quality expectations~~ | — | — | Deferred to post-MVP; V1 uses manual inline editing only | — | Closed (deferred) |
| R-005 | Schema drift between gt_schema_v5_generic.py and backend model if schema evolves independently | High | Low | Single source of truth: backend model derived from schema file; automated schema comparison in CI | TBD | Open |
| R-006 | Tree-shaking may not fully eliminate unused mode code, increasing bundle size | Low | Low | Verify bundle sizes in CI; use compile-time constants (not runtime checks) for mode gating | TBD | Open |

## 11. Privacy, Security & Compliance
### Data Classification
Agentic ground truth items may contain PII from customer interactions (redacted per upstream processing). Trace data includes tool call arguments and responses which may reference customer account identifiers, device information, and usage patterns. All PII should be redacted before ingestion into the curation system.

### PII Handling
* PII redaction is the responsibility of the upstream trace ingestion pipeline, not the curation system
* Curation system stores redacted data as-is; no additional PII processing
* Curator-added context entries and comments should not contain PII (policy enforcement via training, not technical controls)
* Export/snapshot preserves existing redaction

### Threat Considerations
* **Same threat model as RAG mode** — no new attack surfaces introduced
* Auth/RBAC unchanged; deployment isolation means no cross-mode data access
* ETag concurrency prevents unauthorized overwrites
* Cosmos DB access controlled via existing connection string / managed identity patterns

### Regulatory / Compliance (Conditional)
No additional regulatory requirements beyond those already covered by the RAG deployment.

## 12. Operational Considerations
| Aspect | Requirement | Notes |
|--------|------------|-------|
| Deployment | Separate deployment per mode via `CURATION_MODE` env var; agentic deployment gets its own Cosmos container, App Service/Container App instance | Identical deployment pattern to RAG; only config differs |
| Rollback | Standard deployment rollback; agentic deployment is independent of RAG | Rolling back agentic has zero RAG impact |
| Monitoring | Reuse existing monitoring (Application Insights, structured logging); add agentic-specific metrics dashboard | Query metrics logging framework already supports mode-specific operation names |
| Alerting | Same alerting patterns as RAG; add alerts for agentic-specific failures (e.g., bulk import errors, validation failures) | |
| Support | Curators contact same support channel; mode identified by deployment URL | |
| Capacity Planning | Separate RU provisioning for agentic Cosmos container; items are larger so may need higher RU allocation | Monitor after initial data load |

## 13. Rollout & Launch Plan
### Phases / Milestones
| Phase | Date | Gate Criteria | Owner |
|-------|------|--------------|-------|
| Phase 1: Backend Foundation | TBD | Agentic model passes all schema tests; DI gating works; CRUD operations functional with agentic model | TBD |
| Phase 2: Frontend Editor MVP | TBD | AgenticEditor renders conversation, tool call grid with decisions, user context; validation gates approval | TBD |
| Phase 3: Polish & Supporting Views | TBD | Tags management; trace metadata panel; explorer/stats views; curator notes | TBD |
| Phase 4: Deployment & Hardening | TBD | Separate agentic deployment configured; Cosmos container provisioned; performance validated; RAG regression suite passes | TBD |
| Phase 5: GA | TBD | Curators onboarded; support documentation published; monitoring dashboards live | TBD |

### Feature Flags (Conditional)
| Flag | Purpose | Default | Sunset Criteria |
|------|---------|--------|----------------|
| `CURATION_MODE` | Selects RAG vs agentic mode at deployment time | `rag` | Permanent — this is the deployment isolation mechanism, not a temporary flag |
| `VITE_CURATION_MODE` | Frontend compile-time mode selection | `rag` | Permanent — matches backend configuration |

### Communication Plan
TBD — coordinate with curation team leads for curator onboarding and training on agentic workflow.

## 14. Open Questions
| Q ID | Question | Owner | Deadline | Status |
|------|----------|-------|---------|--------|
| Q-001 | ~~What is the maximum expected number of tool calls per agentic item in production data?~~ | — | — | Closed — upper bound is 20 tool calls per item |
| Q-002 | ~~How will AI-assisted editor suggestions be generated in production?~~ | — | — | Closed — AI editor deferred to post-MVP; V1 uses manual editing only |
| Q-003 | Should the agentic explorer view include tool call decision summary columns? | TBD | TBD | Open |
| Q-004 | What agentic-specific computed tag plugins are needed beyond ToolCallCountPlugin and AgentRolePlugin? | TBD | TBD | Open |
| Q-005 | ~~What are the target throughput metrics for agentic curation?~~ | — | — | Closed — target is ≥3 items per curator per hour |
| Q-006 | Are intermediate agent outputs (e.g., orchestrator responses sent to an output agent) under test, or only the final response returned to the user? This determines whether curators need to evaluate and edit intermediate turns or only the final output. | TBD | TBD | Open |

## 15. Changelog
| Version | Date | Author | Summary | Type |
|---------|------|-------|---------|------|
| 0.1 | 2026-03-09 | Copilot | Initial PRD draft derived from wireframe v2.2, gt_schema_v5_generic.py, and curation mode isolation research | Creation |
| 0.2 | 2026-03-09 | Copilot | Updated with stakeholder answers: throughput target ≥3/hr, max 20 tool calls, AI editor deferred to post-MVP, closed 3 open questions | Refinement |
| 0.3 | 2026-03-10 | Copilot | Corrected conversation model: role-agnostic (free-form `role: str`), primarily single-turn, no mandated agent role names. Validation relaxed from requiring specific role types to requiring ≥1 turn + first-turn-is-user. Subagents typically appear as tool calls, not conversation turns. System is deliberately unopinionated about role taxonomy. | Refinement |
| 0.4 | 2026-03-10 | Copilot | Enhanced R-001 mitigation with 10-layer defense-in-depth strategy based on dedicated regression research (REF-005). Added reference entry and citation for mitigation research document. | Refinement |

## 16. References & Provenance
| Ref ID | Type | Source | Summary | Conflict Resolution |
|--------|------|--------|---------|--------------------|
| REF-001 | Wireframe | `wireframes/agent-curation-wireframe-v2.2.html` | Interactive HTML wireframe defining complete agentic curation UI including conversation editor, tool call grid with decision toggles, user context management, AI-assisted editor modal, tags, metadata, and trace panels. 6 dummy items demonstrating various curation states. | Authoritative for UI behavior and layout |
| REF-002 | Schema | `wireframes/gt_schema_v5_generic.py` | Pydantic v2 data model defining AgenticGroundTruthEntry with HistoryEntry, ContextEntry, ToolCallRecord, ExpectedTools (with overlap rejection validator), FeedbackEntry, PluginPayload. Schema version: `agentic-core/v1`. | Authoritative for data model; `grounding_data_summary` and `evaluation_criteria` removed per product decision |
| REF-003 | Research | `.copilot-tracking/research/20260309-curation-mode-isolation-research.md` | Feasibility analysis for deployment-isolated RAG vs agentic modes. Recommends config-gated deployment isolation with shared codebase. Covers schema delta (12 shared, 15 RAG-only, 17 agentic-only fields), frontend/backend extension points, validation differences, and implementation order. All 8 open questions resolved. | Authoritative for architectural approach; supersedes any earlier coexistence assumptions |
| REF-004 | Requirements | `AGENTIC_REQUIREMENTS.md` | Peter's stakeholder feedback: tool calls first-class, subagent concept, remove grounding_data_summary, remove evaluation_criteria, feedback as KV pairs, rules engine as separate tool (deferred) | Authoritative for product decisions on field removal |
| REF-005 | Research | `.copilot-tracking/research/20260310-r001-regression-mitigation-research.md` | Defense-in-depth analysis for R-001 shared codebase regression risk. Defines 10-layer mitigation strategy: directory-enforced module boundaries, DI container as sole branch point, protocol abstractions, CI boundary lint rules, CI mode matrix testing, RAG regression gate job, RAG-default configuration, startup schema validation, separate Cosmos containers, and frontend bundle size gate. Includes phased implementation plan. | Authoritative for R-001 mitigation approach |

### Citation Usage
- UI behavior and component structure: REF-001
- Data model fields and validation: REF-002
- Architecture and deployment strategy: REF-003
- Product decisions (field removal, scope): REF-004
- Validation rules (conversation structure, tool decisions): REF-001 validation functions + REF-003 Scenario 3
- R-001 regression mitigation strategy: REF-005

## 17. Appendices (Optional)
### Glossary
| Term | Definition |
|------|-----------|
| Agentic Ground Truth | A curated evaluation item for an agentic AI system, containing conversation history (any role), tool call records, tool necessity decisions, and trace evidence |
| Role (HistoryEntry) | A free-form string identifying the participant in a conversation turn (e.g., "user", "agent", "orchestrator-agent", "output-agent"). The system is deliberately unopinionated about role names to support diverse agentic architectures |
| Tool Call Decision | A curator's annotation on whether a specific tool/API call was Required (★), Optional (○), or Not Needed (✕) for reaching the correct answer |
| Expected Tools | The categorization of all tool calls into required, optional, and not_needed lists, with validation preventing a tool from appearing in multiple categories |
| Trace Payload | Raw execution trace data from the agentic system, containing tool call arguments, responses, and metadata |
| Plugin Payload | An extensibility mechanism allowing opaque customer-specific data to be attached to a ground truth item under a named slot |
| Config-Gated Deployment | Architecture where a single codebase produces multiple deployment variants, with mode selected by environment variable at build/deploy time |
| Parallel Group | A set of tool calls that executed concurrently within the same step (e.g., P2, P3, P4) |
| Context Entry | A key-value pair attached to a ground truth item providing structured context for the scenario |

### Additional Notes
**Architectural Decision**: Config-gated deployment isolation was selected over runtime mode toggle and separate codebases. See REF-003 for full rationale.

**Schema Evolution from V5 to Generic**: The `gt_schema_v5_generic.py` simplifies the earlier V5 schema by removing domain-specific fields (`grounding_data_summary`, `evaluation_criteria`, `scenario_id`, `title`, `description`, `input`, `context` as top-level dicts, `frozen_tool_responses`, `expected_annotations`, `expected_rule_triggers`, `expected_output`, `temporal_context`, `fixture_id`) and introducing generic extension surfaces (`plugins`, `feedback` list, open `metadata` dict). The generic schema is the implementation target.

**Wireframe Alignment**: The wireframe v2.2 was built against an earlier schema version that included `grounding_data_summary` and `evaluationCriteria` in dummy data. These fields are retained in the wireframe for demonstration but are explicitly out of scope for implementation per product decision. The `renderEvaluationCriteria()` function in the wireframe already returns `null`. Additionally, the wireframe hardcodes specific role names ("orchestrator-agent", "output-agent") and a three-turn conversation model for demonstration purposes. The production system treats `role` as a free-form string and supports arbitrary turn counts — the wireframe role names are example values, not requirements.

Generated 2026-03-09T21:20:56Z by Copilot (mode: prd-builder)
<!-- markdown-table-prettify-ignore-end -->
