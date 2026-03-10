<!-- markdownlint-disable-file -->
<!-- markdown-table-prettify-ignore-start -->
# Agentic Curation Mode — Product Requirements Document (PRD)
Version 1.3 | Status DRAFT | Owner TBD | Team Ground Truth Curator | Target TBD | Lifecycle Discovery

## Progress Tracker
| Phase | Done | Gaps | Updated |
|-------|------|------|---------|
| Context | ✅ | — | 2026-03-09 |
| Problem & Users | ✅ | Persona validation | 2026-03-09 |
| Scope | ✅ | — | 2026-03-09 |
| Requirements | ✅ | Backend approval enforcement (FR-034), OpenAPI mode-safety (NFR-014), CI mode matrix (NFR-015) added | 2026-03-10 |
| Metrics & Risks | ⬜ | Success metrics, risk owners | — |
| Operationalization | 🔶 | Infra parameterization added; deployment runbook, monitoring remain | 2026-03-10 |
| Finalization | ⬜ | Stakeholder approval, open questions Q-007–Q-014 | — |
Unresolved Critical Questions: 1 | TBDs: 4

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
* The frontend editor assumes two fixed roles (user/assistant in backend, user/agent in frontend) and reference-based grounding
* Approval validation in the frontend conditionally gates on reference completeness via runtime config flags (defaulting to off), but the backend approval path performs only lightweight status and ETag checks — neither enforcement path applies meaningfully to agentic items
* No mechanism exists to annotate individual tool calls with required/optional/not-needed decisions

> [!NOTE]
> The items above describe **current-state limitations** of the existing RAG-oriented system. The requirements in §6 and §7 describe the **future-state capabilities** this initiative must deliver. Where a requirement references existing infrastructure (e.g., DI container, computed-tag registry, CI pipeline), the current code provides a reusable pattern or extension point — not a finished implementation of the agentic behavior.

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
* **Backend: Agentic data model** — `AgenticGroundTruthEntry` Pydantic model based on `gt_schema_v5_generic.py` with all fields: scenario_id, history, context_entries, tool_calls, expected_tools, trace_ids, trace_payload, feedback, metadata, plugins, provenance
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
* **Config-gated deployment isolation** (to be implemented) — Zero-risk to existing RAG mode; build-time code elimination ensures clean separation. The existing codebase provides reusable conditional-wiring patterns (e.g., DI container branching, Vite compile-time constants for `DEMO_MODE`) that will be extended to support `CURATION_MODE` / `VITE_CURATION_MODE`

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
| FR-001 | Agentic data model | Implement `AgenticGroundTruthEntry` Pydantic model matching `gt_schema_v5_generic.py` with all fields: id, dataset_name, bucket, doc_type, schema_version, status, etag, assigned_to/at, updated_at/by, reviewed_at, manual_tags, computed_tags, scenario_id, history (list[HistoryEntry]), context_entries (list[ContextEntry]), trace_ids, tool_calls (list[ToolCallRecord]), expected_tools (ExpectedTools with required/optional/not_needed and overlap rejection), feedback (list[FeedbackEntry]), metadata, plugins (dict[str, PluginPayload]), comment, created_by/at, trace_payload | G-003 | ML Engineer | P0 | Model validates against gt_schema_v5_generic.py; all field validators pass; overlap rejection on ExpectedTools works; serialization uses camelCase aliases | Schema version: `agentic-core/v1`; doc_type: `ground-truth`; scenario_id links to external scenario library |
| FR-002 | Config-gated mode selection | Add `CURATION_MODE` environment variable (values: `rag`, `agentic`) that selects model, plugins, validators at DI container startup. Frontend reads `VITE_CURATION_MODE` as compile-time constant | G-002 | RAG Curator, Agentic Curator | P0 | Setting `CURATION_MODE=agentic` loads agentic model and components; `CURATION_MODE=rag` (default) loads existing RAG model; no runtime mode toggle exists | Default is `rag` to protect existing deployments |
| FR-003 | Agentic bulk import | Accept bulk import of agentic ground truth items via `POST /ground-truths` endpoint in agentic deployment, validating against `AgenticGroundTruthEntry` schema | G-003 | ML Engineer | P0 | Import validates required fields; rejects items with ExpectedTools overlap; returns item count and error details | Same endpoint path as RAG, different validation |
| FR-004 | Agentic item listing | Serve paginated list of agentic items via `GET /ground-truths/{dataset}` with agentic schema serialization | G-003 | Agentic Curator | P0 | Returns items with all agentic fields in camelCase wire format; pagination, sorting, and filtering work identically to RAG mode | |
| FR-005 | Agentic assignment lifecycle | Support self-serve assignment, item locking (ETag), update, and status transitions (draft → approved, draft → skipped, soft delete/restore) for agentic items | G-001, G-003 | Agentic Curator, Curation Lead | P0 | Assignment, locking, and status transitions behave identically to RAG mode but operate on agentic model fields | Shared assignment service with injected model |
| FR-006 | Conversation display | Render conversation with role-specific badges and colors. The `role` field is a free-form string; the UI assigns badge colors dynamically per unique role (e.g., "user" = blue, other roles get assigned colors from palette). Support collapse/expand per turn. Render markdown in agent responses. Primarily single-turn (user → agent) but supports arbitrary turn counts | G-001 | Agentic Curator | P0 | Displays all history entries with dynamically-colored role badges; markdown headers, lists, bold, code render correctly; turns collapse/expand independently; works for 1-turn, 2-turn, and N-turn conversations | Role string is not validated against an enum — any value accepted |
| FR-007 | Inline conversation editing | Allow curators to edit any conversation turn's message text with save/cancel controls. Editing is disabled when item is deleted | G-001 | Agentic Curator | P0 | Edit button appears on each turn; textarea pre-filled with current text; save updates model; cancel reverts; deleted items show no edit button | |
| FR-008 | Tool call grid display | Display tool calls in ordered grid with columns: order number, function name, parallel group, execution time, decision badge, expand chevron. Sort by curator-defined order with parallel group grouping | G-001 | Agentic Curator | P0 | All tool calls from trace displayed; order reflects layout configuration; parallel groups shown with ‖ prefix; execution time in seconds; grid columns align across rows | |
| FR-009 | Tool call decision annotation | Provide per-tool segmented toggle with three states: ★ Required (emerald), ○ Optional (sky), ✕ Not needed (rose). Decisions persist on the item's `expected_tools` field | G-001 | Agentic Curator | P0 | Each tool call has a segmented toggle; clicking a segment updates the decision; decision reflected in mini badge on collapsed view; decisions map to ExpectedTools.required/optional/not_needed | Default decision is `optional` |
| FR-010 | Tool call detail expansion | Expand individual tool calls to show arguments (code block) and result (code block, scrollable, max height). Expanded view includes the segmented decision toggle with explanatory label | G-001 | Agentic Curator | P0 | Clicking tool call row expands detail; arguments and result render as formatted code; decision toggle is functional in expanded view | |
| FR-011 | Agentic approval validation (frontend) | Gate approval UI on: (1) conversation has ≥1 turn, (2) no empty messages, (3) first turn is user, (4) at least one tool call marked required, (5) item not deleted. Validation does **not** mandate specific agent role names — any non-user role is acceptable. Frontend enforcement provides fast feedback but is not the source of truth — see FR-034 for backend enforcement. | G-001 | Agentic Curator | P0 | Approve button disabled when any validation fails; validation errors shown as warnings; `canApproveAgentic()` returns false for invalid items | Validation is role-name-agnostic; does not require specific roles like "orchestrator-agent" or "output-agent" |
| FR-012 | User context management | CRUD interface for key-value context entries (ContextEntry). Add new entries, edit key/value inline, remove entries | G-001 | Agentic Curator | P0 | Context entries render as input pairs; add button creates blank entry; edit updates model; remove deletes entry; entries persist on save | |
| FR-013 | Tags management | Display computed tags (read-only, locked icon) and manual tags. Modal for managing manual tags from available tag vocabulary | G-001 | Agentic Curator | P1 | Computed tags show lock icon; manual tags toggleable via modal; tag changes persist on save | Shared pattern with RAG, agentic-specific tag vocabulary |
| FR-014 | Curator notes | Textarea for free-form curator comments on each item | G-001 | Agentic Curator | P1 | Comment textarea renders with current value; changes persist on save | Maps to `comment` field |
| FR-015 | Trace metadata display | Collapsible panel showing trace IDs, trace source (agent version, environment), and user feedback details | G-001 | Agentic Curator | P1 | Trace IDs render as key-value pairs; feedback scores display with color-coded scale; panel collapses/expands | |
| FR-016 | User feedback scores | Display feedback scores from trace data with question text and numerical score, color-coded (1=green agree, 5=red disagree) | G-001 | Agentic Curator | P1 | All feedback questions display with scores; color coding applied; scale legend shown | |
| FR-017 | ~~AI-assisted editor modal~~ | ~~Modal with prompt input that generates structured suggestions~~ | ~~G-004~~ | ~~Agentic Curator~~ | ~~Deferred~~ | ~~Deferred to post-MVP~~ | V1 uses inline editing only (FR-007); AI suggestions deferred |
| FR-018 | ~~Manual editor modal~~ | ~~Direct editing mode with role selector and full-text textarea~~ | ~~G-004~~ | ~~Agentic Curator~~ | ~~Deferred~~ | ~~Deferred to post-MVP~~ | Inline turn editing (FR-007) provides equivalent capability for V1 |
| FR-019 | Agentic snapshot/export | Export approved agentic items as dataset snapshot via `POST /ground-truths/snapshot` with agentic schema shape | G-003 | ML Engineer, Curation Lead | P1 | Export includes all agentic fields; only approved items exported; format matches agentic-core/v1 schema | Same endpoint, different formatter |
| FR-020 | Agentic computed tag plugins | Create agentic-specific computed tag plugins registered in agentic deployment alongside shared plugins (TurnPlugin, DatasetPlugin). **MVP set:** `DecisionCompletenessPlugin` (decisions:complete/partial/none), `HasTracePlugin` (trace:has_payload/no_payload), `FeedbackPlugin` (feedback:has_feedback/no_feedback). **Deferred:** `ToolCallCountPlugin`, `AgentRolePlugin`, domain-specific plugins — revisit when usage patterns are clearer | G-001 | Curation Lead | P1 | DecisionCompletenessPlugin flags items by tool call decision coverage; HasTracePlugin tags items by trace payload presence; FeedbackPlugin tags by feedback availability; shared TurnPlugin/DatasetPlugin work in both modes | |
| FR-021 | Queue sidebar | Display agentic items in queue with ID, category tag, status badge, and user message preview. Support item selection, refresh, and self-serve request | G-001 | Agentic Curator | P0 | Queue shows all assigned items; clicking selects item; status badges reflect current state; deleted items shown with reduced opacity | Shared layout with RAG mode |
| FR-022 | Explorer view | List/filter view for agentic items. **Columns:** ID, Status, Scenario ID, User Message (first turn preview), Tool Calls (count), Tags (manual + computed with lock icon), Reviewed (date), Actions. **Filterable by:** status, dataset, tags (include/exclude), item ID (partial match), scenario ID (partial match), keyword (searches history messages). **Sortable by:** reviewed_at, tool call count, tag count, updated_at. Scenario ID links conceptually to an external scenario library (separate component) | G-001 | Curation Lead | P1 | Explorer renders agentic items with all listed columns; scenario ID filter works as partial match; tool call count column displays correctly; tag filtering supports include/exclude toggle | Decision: No decision-progress column (Q-003). Scenario ID added to schema (gt_schema_v5_generic.py). |
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
| FR-034 | ~~Agentic approval validation (backend)~~ | ~~The backend API layer must enforce agentic approval validation rules when transitioning an item to `approved` status.~~ | ~~G-001, G-002~~ | ~~Agentic Curator, ML Engineer~~ | Deferred | ~~Deferred to post-MVP~~ | **Decision (Q-008):** Only UI curators will approve agentic items; no scripts or bulk approval expected. Frontend-only enforcement (FR-011) matches RAG pattern and is sufficient. Backend enforcement deferred as fast-follow if API consumers are introduced. See Appendix C. |

### Feature Hierarchy (Optional)
```plain
Agentic Curation Mode
├── Backend
│   ├── AgenticGroundTruthEntry model (FR-001)
│   ├── Config-gated DI (FR-002)
│   ├── CRUD operations (FR-003, FR-004, FR-005)
│   ├── Approval validation — backend (FR-034)
│   ├── Computed tag plugins (FR-020)
│   └── Snapshot/export (FR-019)
├── Frontend
│   ├── AgenticEditor (FR-006, FR-007, FR-025)
│   ├── AgenticToolCallGrid (FR-008, FR-009, FR-010)
│   ├── User context management (FR-012)
│   ├── Tags management (FR-013)
│   ├── Trace/evidence panel (FR-015, FR-016)
│   ├── AI-assisted editor (FR-017, FR-018) [DEFERRED post-MVP]
│   ├── Validation & approval — frontend (FR-011, FR-024)
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
| NFR-014 | Maintainability | OpenAPI spec and generated frontend types must remain correct when two distinct schemas coexist. The frontend type generation pipeline (`npm run api:types`) must produce mode-correct types without manual intervention. The approach (mode-conditional spec, dual-published specs, or discriminated union) must be defined before implementation begins. | Generated types compile without errors for each mode; CI validates types after schema changes | P1 | Type generation + typecheck in CI for each mode | See Q-014. Currently the repo has a single OpenAPI spec path. |
| NFR-015 | Maintainability | CI must validate both curation modes. A mode matrix job running lint, typecheck, and tests for both `rag` and `agentic` mode must be added. The existing single-mode CI job serves as RAG baseline only. | Both modes pass lint + typecheck + tests in CI; a RAG regression gate blocks merge if RAG tests fail | P0 | CI workflow inspection | Currently `.github/workflows/gtc-ci.yml` has no mode matrix or `CURATION_MODE` injection. |

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
| R-001 | Shared codebase changes to common modules (auth, assignment lifecycle, DI container) could introduce regressions in either mode | High | Medium | 10-layer defense-in-depth strategy: directory-enforced module boundaries, DI container as sole branch point, protocol abstractions for shared services, CI boundary lint rules, CI mode matrix testing both modes, RAG regression gate job, RAG-default configuration, startup schema validation, separate Cosmos containers, and frontend bundle size gate. **Current-state note:** The existing computed-tag registry (`TagPluginRegistry`) is reusable as an abstraction, but current auto-discovery loads all plugins globally — mode-selective plugin registration is not yet implemented and is required as part of this initiative (see FR-020). See [R-001 Mitigation Research](../../.copilot-tracking/research/20260310-r001-regression-mitigation-research.md) for full analysis and phased implementation plan. | TBD | Open |
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
| Infra Parameterization | Bicep/IaC must support: (1) a `curationMode` parameter (`rag` or `agentic`), (2) per-mode Container App resources with mode-specific app settings (`GTC_CURATION_MODE`, `VITE_CURATION_MODE`), (3) per-mode Cosmos DB container name (e.g., `ground-truths-rag`, `ground-truths-agentic`), (4) per-mode RU allocation. Current `infra/main.bicep` provisions shared building blocks only — mode-aware resources are not yet expressed. | See Q-011. Backend currently hard-codes a single GT container name in `backend/app/core/config.py`. This must become configurable via `GTC_COSMOS_CONTAINER` or derived from `GTC_CURATION_MODE`. |
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
| Q-003 | ~~Should the agentic explorer view include tool call decision summary columns?~~ | — | — | Closed — **Yes for tool call count; no for decision progress.** Explorer includes: ID, Status, Scenario ID, User Message, Tool Calls (count), Tags, Reviewed, Actions. Scenario ID added as a first-class field in the generic schema (`gt_schema_v5_generic.py`) linking to an external scenario library. No decision-progress summary column. See FR-022. |
| Q-004 | ~~What agentic-specific computed tag plugins are needed beyond ToolCallCountPlugin and AgentRolePlugin?~~ | — | — | Closed — **MVP: DecisionCompletenessPlugin, HasTracePlugin, FeedbackPlugin.** ToolCallCountPlugin, AgentRolePlugin, and domain-specific plugins deferred until usage patterns are clearer. Shared TurnPlugin and DatasetPlugin reused from RAG. See FR-020. |
| Q-005 | ~~What are the target throughput metrics for agentic curation?~~ | — | — | Closed — target is ≥3 items per curator per hour |
| Q-006 | ~~Are intermediate agent outputs (e.g., orchestrator responses sent to an output agent) under test, or only the final response returned to the user?~~ | — | — | Closed — **Multiple agent responses are in scope.** Curators must be able to view and edit all agent turns, not just the final response. The conversation editor (FR-006, FR-007) already supports arbitrary turn counts with role-agnostic rendering and per-turn inline editing. No FR changes needed — the existing design accommodates this. |
| Q-007 | ~~**Bucket identity typing:** The current backend model and routes use `UUID` for bucket identity. The target agentic schema (`gt_schema_v5_generic.py`) uses `str`. Which is canonical?~~ | — | — | Closed — **UUID is canonical.** Bucket cannot be removed from the Cosmos DB hierarchical partition key (`[/datasetName, /bucket]`) without container re-partitioning. For agentic mode the bucket could be simplified to a single fixed UUID (NIL UUID or dataset-scoped UUID) instead of per-item random UUIDs, making it transparent to curators while preserving partition key compatibility. The wire-format `str` in the agentic schema stores the UUID serialized as a string. See Appendix: Bucket Simplification Analysis. |
| Q-008 | ~~**Backend approval enforcement:** Should agentic approval validation be enforced in the backend, the frontend, or both?~~ | — | — | Closed — **Frontend-only (Option 1).** Only UI curators will approve agentic items; no scripts or bulk approval expected. This matches the RAG pattern. FR-034 (backend enforcement) deferred to post-MVP as a fast-follow if API consumers or bulk approval are introduced. See Appendix C. |
| Q-009 | ~~**Mode-specific plugin registration:** How will computed-tag plugins be selectively registered per mode?~~ | — | — | Closed — **Strategy A: Subdirectory convention.** Plugins organized into `computed_tags/shared/` (DatasetPlugin, TurnPlugin), `computed_tags/rag/` (existing RAG plugins), and `computed_tags/agentic/` (DecisionCompletenessPlugin, HasTracePlugin, FeedbackPlugin). `_discover_plugins(mode)` scans `shared/` + `{mode}/`. Agentic plugins use a parallel `AgenticTagPlugin` base class typed to `AgenticGroundTruthEntry`. Shared plugins accept a protocol with common fields (`datasetName`, `history`). Existing RAG plugins move to `rag/` subdirectory. |
| Q-010 | ~~**API typing strategy for two schemas:** Will the repository/service/route layer become generic over a schema type parameter, use a shared protocol for common fields, or split entirely by mode behind DI?~~ | — | — | Closed — **Strategy C: Shared Protocol + DI-Injected Strategies.** Modes are expected to stay structurally aligned (same CRUD lifecycle, same assignment flow). Only 5 methods across the stack have RAG-specific logic. DI-injected strategies will handle the mode-specific hotspots (query filter construction, sort key selection, import validation, update request mapping, item duplication). See Appendix B for full analysis. |
| Q-011 | **Infra parameterization for mode isolation:** How will deployment isolation be expressed in infrastructure-as-code? Current Bicep provisions shared resources but not per-mode app settings, container app resources, or Cosmos container parameters. See §12 Operational Considerations. | TBD | TBD | Open |
| Q-012 | **Frontend tree-shaking testability:** How will mode-specific code elimination be verified in CI? A compile-time flag alone is not enough — the code structure and CI bundle-size checks need to be defined. Currently no `VITE_CURATION_MODE`, no mode-specific import tree, and no CI bundle-size gate exist. | TBD | TBD | Open |
| Q-013 | ~~**Conversation role normalization strategy:** Backend currently uses `assistant`, frontend uses `agent`, and the agentic schema allows arbitrary strings.~~ | — | — | Closed — **Strategy 3: Keep current split, extend for agentic.** RAG mode retains the `assistant` ↔ `agent` adapter mapping unchanged. Agentic mode uses `role: str` (free-form) with pass-through — no adapter mapping. Frontend assigns badge colors dynamically per unique role string (FR-006). Backend agentic model uses `role: str` without enum constraint. This aligns with the DI-injected strategy pattern (Q-010) — each mode gets its own adapter behavior. See Appendix D. |
| Q-014 | ~~**OpenAPI/types generation mode-safety:** How will OpenAPI spec and generated frontend types remain correct when two distinct schemas coexist in the same codebase?~~ | — | — | Closed — **Strategy 2: Deployment-conditional spec.** `export_openapi.py` parameterized with `--mode` flag, producing `openapi-rag.json` + `generated-rag.ts` and `openapi-agentic.json` + `generated-agentic.ts`. Frontend build uses `VITE_CURATION_MODE` to select which generated file to import; tree-shaking eliminates the other. CI runs export + freshness checks for both modes. See Appendix E. |

## 15. Changelog
| Version | Date | Author | Summary | Type |
|---------|------|-------|---------|------|
| 0.1 | 2026-03-09 | Copilot | Initial PRD draft derived from wireframe v2.2, gt_schema_v5_generic.py, and curation mode isolation research | Creation |
| 0.2 | 2026-03-09 | Copilot | Updated with stakeholder answers: throughput target ≥3/hr, max 20 tool calls, AI editor deferred to post-MVP, closed 3 open questions | Refinement |
| 0.3 | 2026-03-10 | Copilot | Corrected conversation model: role-agnostic (free-form `role: str`), primarily single-turn, no mandated agent role names. Validation relaxed from requiring specific role types to requiring ≥1 turn + first-turn-is-user. Subagents typically appear as tool calls, not conversation turns. System is deliberately unopinionated about role taxonomy. | Refinement |
| 0.4 | 2026-03-10 | Copilot | Enhanced R-001 mitigation with 10-layer defense-in-depth strategy based on dedicated regression research (REF-005). Added reference entry and citation for mitigation research document. | Refinement |
| 0.5 | 2026-03-10 | Copilot | Post-review update driven by code-validated review (REF-006). Changes: (1) Separated current-state facts from future-state requirements in §2 Root Causes, §5 Differentiators. (2) Updated R-001 to clarify computed-tag registry is reusable but not mode-selective yet. (3) Added FR-034 backend approval enforcement. (4) Added NFR-014 OpenAPI/types mode-safety, NFR-015 CI mode matrix. (5) Expanded §12 Operational Considerations with infra parameterization detail. (6) Added 8 new open questions (Q-007–Q-014) surfaced by code validation. | Review Response |
| 0.6 | 2026-03-10 | Copilot | Closed Q-007: UUID is canonical for bucket identity; full removal not feasible due to Cosmos partition key, but single-fixed-UUID-per-dataset simplification recommended for agentic mode. Enriched Q-010 with code-validated tradeoff analysis of 3 API typing strategies. Added Appendix A (Bucket Simplification Analysis) and Appendix B (API Typing Strategy Tradeoffs). | Research Integration |
| 0.7 | 2026-03-10 | Copilot | Closed Q-010: Strategy C (Shared Protocol + DI-Injected Strategies) selected — modes stay aligned, only 5 hotspots need strategies. Added Appendix C (Approval Enforcement Tradeoffs) for Q-008 and Appendix D (Role Normalization Tradeoffs) for Q-013, both with code-validated analysis. | Research Integration |
| 0.8 | 2026-03-10 | Copilot | Closed Q-008: Frontend-only approval enforcement; FR-034 deferred to post-MVP. Closed Q-013: Strategy 3 (keep current RAG adapter split, agentic uses free-form pass-through). Both decisions align with DI-strategy pattern from Q-010. | Stakeholder Decision |
| 0.9 | 2026-03-10 | Copilot | Enriched Q-014 with code-validated type generation pipeline analysis. Added Appendix E (OpenAPI/Types Mode-Safety Tradeoffs) with 4 strategies. Strategy 2 (deployment-conditional spec) identified as best alignment with existing deployment isolation decisions. | Research Integration |
| 1.0 | 2026-03-10 | Copilot | Closed Q-014: Strategy 2 (deployment-conditional spec). Export script parameterized by mode, two spec/type file pairs, CI checks both, frontend build selects by compile-time flag. | Stakeholder Decision |
| 1.1 | 2026-03-10 | Copilot | Closed Q-003: Explorer columns defined (ID, Status, Scenario ID, User Message, Tool Calls, Tags, Reviewed, Actions); no decision-progress column. Closed Q-004: MVP plugins are DecisionCompletenessPlugin, HasTracePlugin, FeedbackPlugin; ToolCallCountPlugin/AgentRolePlugin deferred. Added `scenario_id` field to `gt_schema_v5_generic.py` and updated FR-001, FR-020, FR-022. | Stakeholder Decision |
| 1.2 | 2026-03-10 | Copilot | Closed Q-009: Subdirectory convention for mode-specific plugin registration. Plugins organized into `shared/`, `rag/`, `agentic/` subdirectories under `computed_tags/`. Discovery scans `shared/` + mode directory. | Stakeholder Decision |
| 1.3 | 2026-03-10 | Copilot | Closed Q-006: Multiple agent responses are in scope — curators must view and edit all agent turns, not just the final response. Existing FR-006/FR-007 design already supports this. | Stakeholder Decision |

## 16. References & Provenance
| Ref ID | Type | Source | Summary | Conflict Resolution |
|--------|------|--------|---------|--------------------|
| REF-001 | Wireframe | `wireframes/agent-curation-wireframe-v2.2.html` | Interactive HTML wireframe defining complete agentic curation UI including conversation editor, tool call grid with decision toggles, user context management, AI-assisted editor modal, tags, metadata, and trace panels. 6 dummy items demonstrating various curation states. | Authoritative for UI behavior and layout |
| REF-002 | Schema | `wireframes/gt_schema_v5_generic.py` | Pydantic v2 data model defining AgenticGroundTruthEntry with HistoryEntry, ContextEntry, ToolCallRecord, ExpectedTools (with overlap rejection validator), FeedbackEntry, PluginPayload. Schema version: `agentic-core/v1`. | Authoritative for data model; `grounding_data_summary` and `evaluation_criteria` removed per product decision |
| REF-003 | Research | `.copilot-tracking/research/20260309-curation-mode-isolation-research.md` | Feasibility analysis for deployment-isolated RAG vs agentic modes. Recommends config-gated deployment isolation with shared codebase. Covers schema delta (12 shared, 15 RAG-only, 17 agentic-only fields), frontend/backend extension points, validation differences, and implementation order. All 8 open questions resolved. | Authoritative for architectural approach; supersedes any earlier coexistence assumptions |
| REF-004 | Requirements | `AGENTIC_REQUIREMENTS.md` | Peter's stakeholder feedback: tool calls first-class, subagent concept, remove grounding_data_summary, remove evaluation_criteria, feedback as KV pairs, rules engine as separate tool (deferred) | Authoritative for product decisions on field removal |
| REF-005 | Research | `.copilot-tracking/research/20260310-r001-regression-mitigation-research.md` | Defense-in-depth analysis for R-001 shared codebase regression risk. Defines 10-layer mitigation strategy: directory-enforced module boundaries, DI container as sole branch point, protocol abstractions, CI boundary lint rules, CI mode matrix testing, RAG regression gate job, RAG-default configuration, startup schema validation, separate Cosmos containers, and frontend bundle size gate. Includes phased implementation plan. | Authoritative for R-001 mitigation approach |
| REF-006 | Review | `.copilot-tracking/reviews/2026-03-10/agentic-curation-mode-r001-review.md` | Code-validated review of PRD v0.4 and R-001. Found 6 major and 5 minor findings. Key gaps: approval validation overstated, computed-tag isolation not implemented, CI validates one mode only, infra parameterization underspecified, bucket typing unresolved, frontend has no pluggable renderer infrastructure yet. Raised 7 additional open questions. | Drove v0.5 updates |

### Citation Usage
- UI behavior and component structure: REF-001
- Data model fields and validation: REF-002
- Architecture and deployment strategy: REF-003
- Product decisions (field removal, scope): REF-004
- Validation rules (conversation structure, tool decisions): REF-001 validation functions + REF-003 Scenario 3
- Code-validated review findings driving v0.5 updates: REF-006
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

## Appendix A: Bucket Simplification Analysis

### Current Bucket Architecture

Bucket is a UUID field that serves as the **second level of the Cosmos DB hierarchical partition key** (`[/datasetName, /bucket]`). During bulk import, items are distributed across N random-UUID buckets (default 5 per dataset) to prevent hot partitions and stay within the 20 GB per-logical-partition limit.

**Where bucket is structurally required:**
- Cosmos DB partition key — cannot be removed without full container re-partitioning
- Point reads: `read_item(item=item_id, partition_key=[dataset, str(bucket)])` — the most efficient access pattern
- API route paths: `/{datasetName}/{bucket}/{item_id}` — 6 endpoints
- AssignmentDocument identity: `id = "{dataset}|{bucket}|{groundTruthId}"`
- Frontend cache keys: `{dataset}/{bucket}/{itemId}`

**Where bucket is NOT semantically used:**
- Listing/querying — cross-partition queries already span all buckets (no bucket filter)
- Assignment sampling — `sample_unassigned()` and `query_unassigned_*()` ignore bucket
- Export/snapshot — iterates all items regardless of bucket

### Feasibility of Removing Bucket Entirely

**Verdict: Not feasible without container migration.** The Cosmos DB hierarchical partition key is immutable after container creation. Removing `/bucket` from the key would require creating a new container, migrating all data, and updating the CD pipeline partition-path parameter.

### Recommended Approach: Single Fixed UUID Per Dataset

For agentic mode, simplify bucket to a **single deterministic UUID per dataset** rather than random per-item distribution:

| Aspect | RAG Mode (current) | Agentic Mode (proposed) |
|---|---|---|
| Bucket generation | N random UUIDs cycled across items | One fixed UUID per dataset (e.g., `UUID5(NAMESPACE_URL, datasetName)`) |
| Import `buckets` param | Accepted (default 5) | Ignored; always 1 |
| Partition distribution | Multi-bucket (load spread) | Single-bucket per dataset |
| 20 GB limit risk | Low (distributed) | Acceptable if agentic datasets stay under 20 GB; revisit if they grow |
| API path | `/{dataset}/{bucket}/{itemId}` — bucket varies | `/{dataset}/{bucket}/{itemId}` — bucket is always the same deterministic UUID |
| Frontend display | Bucket shown in inspect modal | Bucket hidden or shown as "default" |
| Point reads | Efficient (direct partition) | Equally efficient (direct partition) |

**Implementation cost:** Low — change only the bulk import logic for agentic mode to assign a single bucket. All API routes, partition keys, and AssignmentDocument logic remain unchanged.

**Trade-off:** A single-bucket dataset has a 20 GB Cosmos DB partition limit. At ~5 KB per agentic item (larger due to trace_payload), this supports ~4 million items per dataset. If datasets exceed this, the import logic can fall back to multi-bucket distribution.

### Alternative: Remove Bucket from API Paths (Deferred)

A future optimization could introduce agentic-specific routes that omit bucket from the URL path (e.g., `GET /v1/agentic/ground-truths/{dataset}/{itemId}`) and resolve the bucket internally. This requires a lookup or convention but reduces API surface complexity. **Deferred** — the single-fixed-bucket approach makes the bucket invisible to users without any route changes.

## Appendix B: API Typing Strategy Tradeoffs

### Current State

The repo/service/route stack is typed directly to `GroundTruthItem` in 20+ method signatures. Code analysis reveals:

| Layer | Total Methods | Model-Generic | RAG-Specific Logic | RAG Type Coupling Only |
|---|---|---|---|---|
| Repository protocol | 20 | 10 | 2 (`list_gt_paginated`, `import_bulk_gt` query logic) | 8 |
| Services | ~14 | 11 | 1 (`duplicate_item`) | 2 |
| API routes | 12 | 8 | 2 (update, paginated list) | 2 |

**Key insight:** Most "RAG-specific" coupling is in **type annotations and return types**, not in business logic. Only 5 methods across the entire stack have logic that inspects RAG-specific fields (refs, answer, keywords).

### Strategy A: Generic TypeVar Protocol

Make `GroundTruthRepo` generic over an item type: `GroundTruthRepo[T]` where `T` is bound to a base protocol with shared fields.

```
class CurableItem(Protocol):
    id: str; datasetName: str; bucket: UUID; status: GroundTruthStatus; ...

class GroundTruthRepo(Protocol, Generic[T: CurableItem]):
    async def get_gt(self, dataset: str, bucket: UUID, item_id: str) -> T: ...
    async def import_bulk_gt(self, items: list[T], buckets: int | None) -> BulkImportResult: ...
```

| Advantage | Disadvantage |
|---|---|
| Single protocol, single implementation | Complex generic constraints; Pydantic models don't naturally satisfy Protocols |
| Shared methods stay shared | `list_gt_paginated()` query construction would need strategy/callback pattern for mode-specific filters |
| DI container wires `Repo[GroundTruthItem]` or `Repo[AgenticItem]` | TypeVar propagation across service/route layers adds annotation noise |
| Strong compile-time type safety | Higher learning curve for contributors unfamiliar with Python generics |

**Estimated effort:** Medium-High. ~30 files touched but mostly signature-level changes. The hard part is `list_gt_paginated()` and query filter parameterization.

### Strategy B: Twin Protocols + Mode-Specific Implementations

Create `RagGroundTruthRepo` and `AgenticGroundTruthRepo` as separate protocols. Shared logic lives in a base class or mixin.

```
class BaseGroundTruthRepo(Protocol):  # shared: get_gt, soft_delete, stats, list_datasets, ...
class RagGroundTruthRepo(BaseGroundTruthRepo):  # adds: list_gt_paginated (with ref/keyword filters)
class AgenticGroundTruthRepo(BaseGroundTruthRepo):  # adds: list_gt_paginated (with tool_call/trace filters)
```

| Advantage | Disadvantage |
|---|---|
| Clean separation; each protocol is self-documenting | Shared base class needs careful design to avoid LSP issues |
| Mode-specific query logic is explicit, not hidden behind strategy callbacks | Code duplication in Cosmos implementation (two classes inheriting from shared base) |
| No generic complexity; plain Protocol types | DI container must know which protocol to wire; services become mode-aware or also need two variants |
| Easier to test each mode independently | Two protocol surfaces to maintain; shared interface drift risk |

**Estimated effort:** Medium. ~20 new files (agentic protocol, agentic cosmos repo, agentic routes) plus refactoring shared logic into base. More files but simpler per-file logic.

### Strategy C: Shared Protocol + DI-Injected Strategies

Keep a single `GroundTruthRepo` protocol, but inject mode-specific strategies for the 2-5 methods that differ:

```
class GroundTruthRepo(Protocol):
    async def get_gt(self, ...) -> dict: ...  # Returns dict, services/routes deserialize per mode
    # OR
    query_strategy: QueryStrategy  # Injected at DI time, handles filter/sort per mode
```

| Advantage | Disadvantage |
|---|---|
| Minimal structural change; same protocol | `dict` return types lose type safety at protocol boundary |
| DI container injects strategies cleanly | Strategy interface design is non-trivial (must handle query, sort, validation, serialization) |
| Only 2-5 strategy methods needed (query, sort, import validation, duplicate, update) | More indirection; harder to trace code flow |
| Shared methods truly shared with zero duplication | Strategy explosion if modes diverge further |

**Estimated effort:** Low-Medium. ~10 files changed. Risk: if strategies proliferate, this becomes a hidden twin-protocol pattern without the explicitness.

### Recommendation

**This is open for discussion** (Q-010 remains open). Based on the analysis:

- If the two modes are expected to **stay structurally aligned** (same CRUD lifecycle, same assignment flow, differing only in schema fields and query filters): **Strategy C** is the simplest path.
- If the modes are expected to **diverge in workflows** (different approval flows, different assignment patterns, different API shapes): **Strategy B** provides cleaner long-term separation.
- **Strategy A** is the most type-safe but carries the highest complexity cost for a Python codebase that doesn't currently use generics.

The 5 RAG-specific hotspots that any strategy must address:
1. `cosmos_repo._build_query_filter()` — filter construction for paginated list
2. `cosmos_repo._sort_key()` — sort field selection
3. `ground_truths.py POST /ground-truths` — bulk import request model
4. `assignments.py PUT` — update request model (refs, answer fields)
5. `assignment_service.duplicate_item()` — field-specific deep copy

## Appendix C: Approval Enforcement Tradeoffs

### Current State (RAG Mode)

| Layer | What it validates | What it doesn't validate |
|---|---|---|
| **Frontend** | Reference visit status, key paragraph length (≥40 chars, config-gated), conversation pattern (alternating user/agent), agent turns have `expectedBehavior`, item not deleted | Nothing sent to backend about validation results |
| **Backend** | ETag present (concurrency control) | Content completeness, conversation structure, reference quality — accepts any `status: approved` |

The frontend sends `{ status: "approved", ...fields }` with an ETag header. No validation metadata, no "canApprove" flag. The backend trusts the caller.

### Why This Matters for Agentic Mode

Agentic approval rules are different and arguably **higher stakes** — tool call decisions directly feed ML evaluation pipelines. If a direct API caller (script, test harness, future integration) sets `status: approved` without requiring ≥1 required tool call, the resulting dataset quality is compromised silently.

### Option 1: Frontend-Only (Match Current RAG Pattern)

| Advantage | Disadvantage |
|---|---|
| Zero backend changes; fastest to implement | Any API caller can bypass all validation |
| All validation logic in one place (easier to iterate) | Dataset quality depends on client discipline |
| Consistent with RAG mode pattern | Cannot guarantee "every approved item meets rules" at the data layer |
| Frontend can show rich, interactive validation feedback | Bulk import with `approve=true` skips all content checks |

**When this is OK:** Closed system where only the official UI creates approvals, and data quality is monitored downstream.

### Option 2: Backend-Only

| Advantage | Disadvantage |
|---|---|
| Durable guarantee — impossible to approve invalid items | Validation errors are HTTP 422s, harder to show as inline UI guidance |
| Protects against scripts, bulk operations, future integrations | Duplicate logic needed if frontend also wants pre-submit validation |
| Single source of truth for approval rules | Slower iteration — every rule change requires backend deployment |
| Works for both agentic and RAG if applied consistently | Higher latency on save (validation runs server-side) |

**When this is OK:** The approval rules are stable and few, and you want hard guarantees.

### Option 3: Both (Defense in Depth) — FR-034 Proposal

| Advantage | Disadvantage |
|---|---|
| Frontend gives fast, interactive feedback | Two copies of validation logic (Python + TypeScript) that must stay in sync |
| Backend provides durable guarantee at the data layer | More code to maintain; risk of rule drift between layers |
| Protects against all bypass vectors | Slightly more complex save flow (frontend validates → API call → backend re-validates) |
| Supports the CI mode-matrix testing approach (NFR-015) | Need a test strategy to verify frontend and backend agree |

**Sync strategy options:**
- **Code convention + tests:** Write matching rules in both languages, add cross-layer integration tests that submit known-valid and known-invalid items and assert both layers agree.
- **Schema-driven validation:** Define rules as data (e.g., JSON schema or a shared config), generate validators for both layers. Higher upfront cost but eliminates drift.
- **Backend-authoritative, frontend advisory:** Frontend shows warnings but doesn't block submit; backend rejects with structured errors that the frontend displays. This avoids duplication but worsens UX (save → 422 → fix → retry).

### Recommendation Framework

| If... | Then... |
|---|---|
| Agentic curation is UI-only for the foreseeable future | Option 1 is pragmatic; add backend enforcement later when API consumers appear |
| Bulk import with `approve=true` is expected for agentic data | Option 2 or 3 — cannot trust that importers ran validation |
| Dataset quality is a hard contractual/compliance requirement | Option 3 — defense in depth |
| You want to match the existing RAG pattern and minimize scope | Option 1 — add backend enforcement as a fast-follow |

## Appendix D: Role Normalization Tradeoffs

### Current State

```
Backend enum:     "user" | "assistant"
Frontend type:    "user" | "agent"
Agentic schema:   role: str  (free-form, no constraint)
```

The adapter layer (`apiMapper.ts`) performs explicit bidirectional mapping:
- Outbound: `"agent"` → `"assistant"` (frontend → backend)
- Inbound: `"assistant"` → `"agent"` (backend → frontend)

This works today because there are exactly **2 roles** and the mapping is 1:1. The agentic schema introduces arbitrary role strings (e.g., `"orchestrator-agent"`, `"output-agent"`, `"tool-response"`).

### The Core Tension

The agentic mode needs free-form roles. But right now the system has a hard-coded 2-role vocabulary with a translation layer in between. Three strategies exist:

### Strategy 1: Free-Form String End-to-End

Store, transmit, and display `role: str` with no enum or mapping. Whatever the ingestion system writes is what the curator sees.

| Advantage | Disadvantage |
|---|---|
| Simplest; removes adapter mapping entirely | Existing RAG mode breaks — `"assistant"` and `"agent"` would need to reconcile |
| Naturally supports any agentic architecture | No compile-time safety; typos in role names silently propagate |
| Frontend dynamically assigns badge colors per unique role string (already designed in FR-006) | Cannot validate that required roles are present (e.g., "at least one non-user role") |
| Matches the agentic schema design intent | Frontend comparison like `turn.role === "agent"` scattered across 10+ files would need refactoring |

**Migration cost for RAG mode:** The `HistoryItemRole` enum and adapter mapping must be removed or bypassed. RAG items in Cosmos currently store `"assistant"` — they would continue to display as `"assistant"` unless migrated.

### Strategy 2: Normalize to a Canonical Vocabulary at the API Boundary

Pick one vocabulary for the wire format. Backend and frontend both use it. No adapter mapping.

**Option A:** Normalize to `"assistant"` (backend wins)
- Frontend changes `"agent"` → `"assistant"` in types and 10+ component files
- Agentic schema already allows free-form, so `"assistant"` is legal
- RAG data in Cosmos needs no migration

**Option B:** Normalize to `"agent"` (frontend wins)
- Backend changes enum and all stored RAG data from `"assistant"` → `"agent"`
- Requires data migration for existing RAG items in Cosmos
- Cleaner for new agentic data but disruptive for RAG

**Option C:** RAG keeps `"assistant"` on wire, agentic uses free-form — **mode-specific wire format**
- Adapter mapping stays for RAG mode (already working)
- Agentic mode passes role strings through without mapping
- Each mode has its own wire contract; no cross-mode confusion

| Advantage | Disadvantage |
|---|---|
| No breaking change to either mode | Two adapter paths to maintain |
| RAG stays stable, agentic is free-form | Frontend must know which mode it's in to decide whether to map |
| Matches deployment isolation principle (modes don't share data) | OpenAPI spec must document both contracts |

### Strategy 3: Keep Current Split, Extend for Agentic

Keep backend enum for RAG. For agentic mode, use `role: str` without enum constraint. The adapter layer maps for RAG and passes through for agentic.

| Aspect | RAG Mode | Agentic Mode |
|---|---|---|
| Backend storage | `"user"` \| `"assistant"` (enum) | `role: str` (free-form) |
| Wire format | `"user"` \| `"assistant"` | Free-form string |
| Frontend mapping | `"assistant"` → `"agent"` (existing adapter) | Pass-through (no mapping) |
| Frontend type | `"user"` \| `"agent"` | `string` |
| Badge rendering | Hard-coded user=blue, agent=violet | Dynamic color assignment per unique role (FR-006) |

| Advantage | Disadvantage |
|---|---|
| Zero changes to RAG mode | Two code paths in the adapter layer |
| Agentic mode gets the free-form semantics it needs | Frontend needs mode-aware type widening (`role` is union of enum and string) |
| Clean separation — each mode has its own contract | Testing must cover both paths |
| Aligns with Strategy C (DI-injected strategies) | Slightly more complex type definitions |

### Recommendation Framework

| If... | Then... |
|---|---|
| You want maximum simplicity and accept RAG adapter refactoring | Strategy 1 — free-form everywhere |
| You want zero RAG changes and clean agentic semantics | Strategy 3 — keep current split, extend for agentic |
| You eventually want one canonical vocabulary across both modes | Strategy 2C — mode-specific wire format as a stepping stone |
| You want the lowest-risk, fastest-to-implement approach | Strategy 3 — it requires the fewest file changes and matches the DI-strategy pattern from Q-010 |

## Appendix E: OpenAPI/Types Mode-Safety Tradeoffs

### Current Pipeline

```
FastAPI app (Pydantic models + response_model declarations)
    ↓  app.openapi()
backend/scripts/export_openapi.py
    ↓  writes JSON
frontend/src/api/openapi.json  (committed)
    ↓  npm run api:types (openapi-typescript)
frontend/src/api/generated.ts  (committed, auto-generated)
    ↓  openapi-fetch typed client
frontend/src/adapters/apiMapper.ts  (hand-written mapping)
    ↓
frontend/src/models/groundTruth.ts  (manual domain types)
```

**CI enforcement:** Both `openapi.json` and `generated.ts` are freshness-checked in CI. If either is stale, the build fails.

**Key constraint:** Since each deployment runs **one** mode, the backend app at runtime will only expose one schema's routes. The question is how the spec export and type generation handles both schemas in the same codebase.

### Strategy 1: Single Spec with Both Schemas (Union/Discriminator)

Include both `GroundTruthItem` (RAG) and `AgenticGroundTruthEntry` in one OpenAPI spec. Routes accept/return a union type discriminated by `schemaVersion` or `docType`.

| Advantage | Disadvantage |
|---|---|
| One spec, one generated file, one pipeline | Union types are awkward — `openapi-typescript` generates `GroundTruthItem | AgenticGroundTruthEntry` that callers must narrow |
| Frontend gets both type definitions in one place | Every consumer must handle the union at every call site, even though a deployment only uses one |
| CI checks remain simple (one file pair) | OpenAPI spec grows significantly, including schemas never used by a given deployment |
| No pipeline changes needed | Misleading at runtime — a RAG deployment's spec advertises agentic types it can't serve |

### Strategy 2: Deployment-Conditional Spec (One Spec Per Mode)

The FastAPI app conditionally registers routes and models based on `CURATION_MODE`. Each deployment serves its own OpenAPI spec. The export script runs twice (once per mode) and writes two files.

```
export_openapi.py --mode=rag   → frontend/src/api/openapi-rag.json   → generated-rag.ts
export_openapi.py --mode=agentic → frontend/src/api/openapi-agentic.json → generated-agentic.ts
```

| Advantage | Disadvantage |
|---|---|
| Each spec is accurate for its deployment — no phantom types | Two spec files, two generated files to maintain |
| `openapi-typescript` produces clean types per mode (no unions) | Export script and CI must run both modes |
| Aligns with deployment isolation principle | Frontend import path depends on mode (`import from './generated-rag'` vs `'./generated-agentic'`) |
| Runtime spec at `/v1/openapi.json` matches actual deployment | Slightly more complex export script (parameterized by mode) |

**Implementation sketch:**
- `export_openapi.py` accepts `--mode` flag, sets `CURATION_MODE` env, imports app, calls `app.openapi()`
- Frontend build uses `VITE_CURATION_MODE` to select which generated file to import (dead-code eliminates the other)
- CI runs export + check for **both** modes

### Strategy 3: Shared Spec with Mode Tags

One OpenAPI spec includes both schemas, but routes are tagged by mode (`x-curation-mode: rag` or `x-curation-mode: agentic`). The frontend type generator filters by tag.

| Advantage | Disadvantage |
|---|---|
| Single spec file | Requires custom openapi-typescript plugin or post-processing to filter |
| Both schemas documented together for API consumers | Tags are non-standard; tooling support is uncertain |
| No mode-conditional export step | Still produces union types unless filtered |

### Strategy 4: Separate API Prefixes

RAG routes at `/v1/` and agentic routes at `/v1-agentic/`. Both present in all builds, but each deployment only serves one prefix.

| Advantage | Disadvantage |
|---|---|
| Clean URL separation, easy to understand | Both prefixes appear in spec even when only one is active |
| Could produce separate specs per prefix | Diverges from "shared codebase" goal — two URL trees to maintain |
| Good for API versioning long-term | Frontend URL construction becomes mode-aware |

### Recommendation Framework

| If... | Then... |
|---|---|
| You want clean per-mode types with no unions | **Strategy 2** — deployment-conditional spec is the cleanest fit |
| You want minimal pipeline changes | **Strategy 1** — but accept union-narrowing overhead in frontend code |
| You want one spec but clean types | **Strategy 3** — but requires custom tooling |
| You expect API versioning or external consumers | **Strategy 4** — separate prefixes |

**Strategy 2 aligns best** with the decisions already made:
- Deployment isolation (modes don't coexist at runtime)
- DI-injected strategies (Q-010: mode selected at startup)
- Tree-shaking (Q-012: unused mode code eliminated at build time)
- CI mode matrix (NFR-015: both modes tested in CI)

The export-per-mode approach is a natural extension of the existing `export_openapi.py` script.

<!-- markdown-table-prettify-ignore-end -->
