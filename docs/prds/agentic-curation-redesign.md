<!-- markdownlint-disable-file -->
<!-- markdown-table-prettify-ignore-start -->
# Agentic Curation Redesign - Product Requirements Document (PRD)
Version 0.6 | Status Draft | Owner TBD | Team Ground Truth Curator | Target TBD | Lifecycle Discovery

## Progress Tracker
| Phase | Done | Gaps | Updated |
|-------|------|------|---------|
| Context | ✅ | Confirm final plugin packaging decisions | 2026-03-11 |
| Problem & Users | ✅ | Validate RAG compatibility stakeholders | 2026-03-11 |
| Scope | ✅ | Confirm any legacy API-compatibility promises | 2026-03-11 |
| Requirements | ✅ | Refine implementation sequencing with engineering | 2026-03-11 |
| Metrics & Risks | ✅ | Validate performance budget for large traces | 2026-03-11 |
| Operationalization | ✅ | Confirm rollout gates and temporary migration flags | 2026-03-11 |
| Finalization | ⏳ | Approve supersession of prior PRD and translate resolved decisions into an implementation plan | 2026-03-11 |
Unresolved Critical Questions: 0 | TBDs: 3

## 1. Executive Summary
### Context
The current Ground Truth Curator implementation is centered on a RAG-specific curation flow. A prior PRD proposed adding agentic curation as a separate mode in the same codebase. That direction would preserve the RAG-shaped core and layer agentic behavior beside it, increasing duplication across models, UI trees, validators, and long-term maintenance paths.

This PRD replaces that direction. The new initiative redesigns the current curation experience around an agentic-first, generic core derived from `wireframes/agent-curation-wireframe-v2.2.html` and `wireframes/gt_schema_v5_generic.py`. The redesign intentionally reuses durable plumbing such as API routing, services, storage, assignment, snapshot/export, auth, and computed-tag infrastructure, while allowing large portions of the current RAG-specific curation implementation to be deleted and rebuilt on top of the new core.

### Core Opportunity
Turn Ground Truth Curator into a single generic curation platform for agentic traces, tool decisions, context, feedback, and extensible domain-specific panels. Instead of preserving RAG as the host architecture, RAG becomes one plugin pack implemented through the new extension points. This exercises the platform's generic design immediately and prevents a second long-lived fork of the product.

### Goals
| Goal ID | Statement | Type | Baseline | Target | Timeframe | Priority |
|---------|-----------|------|----------|--------|-----------|----------|
| G-001 | Deliver the primary curation workflow defined in `agent-curation-wireframe-v2.2.html` as the product's default architecture | Business | Current UI is RAG-oriented | Wireframe-aligned agentic-first workflow implemented | TBD | P0 |
| G-002 | Replace the RAG-shaped core data model and editor architecture with a generic schema-first core based on `gt_schema_v5_generic.py` | Technical | Core contracts are RAG-specific | Generic core owns CRUD, editing, review, and export | TBD | P0 |
| G-003 | Recreate the existing RAG curation flow on the redesigned platform through plugins and documented extension points, not through a second app mode | Technical | RAG is the hard-coded host flow | RAG operates as a compatibility pack on the generic core | TBD | P0 |
| G-004 | Delete redundant legacy curation code once the redesigned core and compatibility pack cover required behavior | Technical | Parallel RAG-oriented implementations exist | Legacy editor/mode-specific branches retired | TBD | P1 |
| G-005 | Preserve and reuse proven plumbing where it remains valuable (routing, service orchestration, storage, assignment, exports, auth, telemetry, computed tags) | Operational | Plumbing is intertwined with current feature shape | Plumbing survives behind cleaner generic contracts | TBD | P1 |
| G-006 | Improve long-term maintainability by ensuring future domain workflows are added via plugins rather than new top-level modes | Operational | New workflows imply app forking risk | New workflows fit extension model | TBD | P1 |

### Objectives (Optional)
| Objective | Key Result | Priority | Owner |
|-----------|------------|----------|-------|
| Establish agentic-first core | Core editor, explorer, and approval flow operate on the generic schema | P0 | TBD |
| Prove generic architecture with RAG | Existing RAG flow works through plugin surfaces without reviving the old host architecture | P0 | TBD |
| Simplify codebase | Legacy mode split and redundant editor paths are removed after parity | P1 | TBD |

## 2. Problem Definition
### Current Situation
Ground Truth Curator currently assumes a RAG-shaped item: question/answer content, grounding references, expected behavior annotations, and reference-driven approval gating. The UX, models, validators, and explorer semantics all reflect that assumption.

The desired future state is materially different:
* Tool calls are a first-class review surface.
* Agent traces, trace payloads, metadata, feedback, and plugin data are generic and variably shaped.
* Conversations may involve flexible role names and multi-step agent behavior.
* The dominant workflow is the agentic curation experience represented in the wireframe, not the current RAG form.

### Problem Statement
If agentic curation is added as a separate mode on top of the current RAG-centric architecture, the product will carry two competing cores: the old RAG-first one and the new agentic one. That creates duplicated UI stacks, duplicated validation rules, duplicated domain models, and permanent architectural drag. Because there are no current users of the existing setup, the better choice is to redesign now around the target workflow and treat RAG as a specialization of that new platform.

### Root Causes
* The current core domain contracts are organized around RAG concepts rather than generic agentic review primitives.
* The earlier "separate mode" direction optimizes for coexistence instead of simplification.
* Flexible fields such as feedback, metadata, trace payloads, tool responses, and plugin payloads need generic rendering and extension contracts, not hard-coded schemas in the host app.
* Current approval and editing assumptions are tightly coupled to references and expected-behavior semantics that should become plugin-provided behavior for RAG, not universal product rules.

### Impact of Inaction
Retaining the current direction would:
* Increase engineering cost for every future workflow by requiring more mode-specific branches.
* Delay delivery of the wireframe-defined agentic workflow because the platform remains anchored to RAG semantics.
* Limit the ability to delete old code and simplify the repository while no users depend on it.
* Undermine the claim that the new schema and editor are genuinely generic because RAG would still be the real host architecture.

## 3. Users & Personas
| Persona | Goals | Pain Points | Impact |
|---------|-------|------------|--------|
| **Agentic Curator** - Reviews traces, tool usage, and responses | Curate agent conversations quickly and confidently; decide which tools were required; edit responses and metadata | Current product is optimized for references, not tool-centric review | Primary day-to-day user |
| **Curation Lead** - Monitors throughput and data quality | Assign work, review progress, track status and quality signals across datasets | Current metrics and explorer semantics do not map cleanly to agentic work | Operational owner |
| **ML Engineer / Evaluator** - Consumes approved data | Export generic agentic datasets with clear schema and plugin data | No stable generic contract for agentic evaluation datasets | Downstream consumer |
| **Plugin Author** - Extends the product for domain workflows such as RAG | Add domain-specific panels, rules, metrics, and transforms without forking the app | Current architecture requires hard-coded product changes for each domain | Internal platform extender |

### Journeys (Optional)
1. Agentic Curator self-assigns an item from the queue, reviews conversation/tool calls/evidence, edits the item, and approves it.
2. Curation Lead filters the explorer by tags, plugin-provided signals, and approval state to manage quality and throughput.
3. Plugin Author adds a compatibility pack for RAG that restores reference-centric review behavior using core extension points rather than a new product mode.

## 4. Scope
### In Scope
* Redesign the curation product around a single generic agentic-first core.
* Adopt `AgenticGroundTruthEntry` and its supporting models from `gt_schema_v5_generic.py` as the foundation for core data contracts.
* Build the primary UX from `agent-curation-wireframe-v2.2.html`, including queue/sidebar, split-pane editing, evidence drawer, tool-call review, trace/metadata/feedback surfaces, and lifecycle actions.
* Define extension points for renderer contributions, plugin panels, validation rules, search/explorer fields, tagging, import/export transforms, and stats.
* Reuse existing plumbing where it remains architecture-safe: FastAPI routing, services, repository abstractions, assignment lifecycle, snapshot/export pipeline, auth, telemetry, and computed-tag registry patterns.
* Recreate the existing RAG curation flow as a compatibility pack implemented through the new extension surfaces.
* Remove obsolete RAG-specific core code and any separate-mode branching after the redesigned architecture reaches required parity.

### Out of Scope (justify if empty)
* Long-lived runtime "RAG mode" versus "agentic mode" product branching.
* Preserving the current RAG-specific editor tree as a parallel first-class experience.
* One-off support for every historical data shape in the core schema; non-core shapes belong in adapters or plugins.
* Permanent transitional read paths for legacy RAG payloads after the redesigned system normalizes them into the generic core contract.
* Recreating every legacy RAG-specific UI affordance or stricter workflow detail when it is not needed for the essential curator flow in v1.
* Integrating the optional rules engine into the core workflow in v1; it remains a separate tool/tab decision until the generic plugin model and RAG compatibility pack are proven.
* Infrastructure redesign under `infra/`.

### Assumptions
* There are no current production users depending on the existing setup, so replacement and deletion are preferable to long-term coexistence.
* The wireframe is the primary source of truth for the target user workflow and information architecture.
* `gt_schema_v5_generic.py` is the primary source of truth for the generic core record contract.
* Existing storage, assignment, and export plumbing can be reused if reshaped behind generic domain contracts.
* The redesigned core may store domain-specific data in `plugins` and other flexible schema surfaces, provided core rendering and validation remain generic by default.

### Constraints
* Backend layering must remain `api/v1 -> services -> adapters`.
* Frontend data-fetching must continue to flow through `frontend/src/api/` or `frontend/src/services/`.
* Extension points must be explicit enough that RAG compatibility does not require reviving a parallel app or hidden mode branches.
* Plugin failures must surface explicitly; the system must not silently fall back to success-shaped behavior.
* The redesign should maximize deletion of obsolete code, not preserve it for comfort.

## 5. Product Overview
### Value Proposition
Ground Truth Curator becomes a generic curation platform for agentic evaluation data. The host product natively understands conversations, tool calls, context entries, feedback, metadata, tags, provenance, and plugin payloads. Domain workflows such as RAG are layered on top through compatible plugins rather than hard-coded into the core.

### Differentiators (Optional)
* **Agentic-first, not mode-added** - The product is designed around the target workflow instead of bolting it onto a legacy flow.
* **Schema-first generic core** - Flexible fields remain flexible, with sane default renderers and targeted overrides.
* **Deletion-friendly redesign** - The architecture is intentionally chosen to enable removal of obsolete RAG-first code while risk is low.
* **Compatibility through plugins** - Existing RAG behavior is preserved as a proof that the new architecture is truly generic.

### UX / UI (Conditional)
The target UX follows `agent-curation-wireframe-v2.2.html` and includes:
* A queue sidebar for assignment, selection, and item status.
* A split-pane workspace with conversation/context editing on the left and evidence/trace panels on the right.
* Tool calls as a first-class review artifact with expandable details and required/optional/not-needed decisions.
* Generic panels for trace data, metadata, feedback, tags, comments, and plugin-provided content.
* Responsive behavior that collapses evidence into a mobile drawer.
* Item lifecycle actions including save, approve, skip, delete, restore, and duplicate.

Core extensibility model:
* Default components exist for flexible schema fields (`feedback`, `metadata`, `plugins`, `tracePayload`, `ContextEntry.value`, `ToolCallRecord.response`).
* The flexible surfaces that must be explicitly extensible are `feedback`, `metadata`, `plugins[].data`, `tracePayload`, `contextEntries[].value`, and `toolCalls[].response`.
* Plugin packs can contribute custom field components, side panels, approval rules, explorer columns, derived summaries, import/export transforms, computed tags, and stats cards.
* `plugins[].data` and `toolCalls[].response` must support action-capable review components, not just passive renderers.
* Retrieval-oriented workflows such as RAG treat retrieval as a specialized tool-call review experience. Retrieval adapters normalize backend-specific search results into a common candidate-reference contract while preserving raw backend responses for fallback rendering and auditability.
* Selected primary and bonus references persist as plugin-owned data keyed to the retrieval tool call that produced them, and plugin-derived item summaries feed queue, explorer, and approval views.
* The RAG compatibility pack must use these same surfaces to recreate reference-focused curation without reinstating a RAG-first host architecture.

## 6. Functional Requirements
| FR ID | Title | Description | Goals | Personas | Priority | Acceptance | Notes |
|-------|-------|-------------|-------|----------|----------|-----------|-------|
| FR-001 | Agentic-first core architecture | The product shall provide one generic curation architecture rather than separate RAG and agentic modes. Core application wiring shall load a generic editor/explorer/workspace and register optional plugin packs against documented extension points. | G-001, G-002, G-006 | Agentic Curator, Plugin Author | P0 | No permanent runtime mode split exists in the final design; core startup loads one generic architecture with plugin registration | Temporary migration toggles may exist during implementation but must not survive launch |
| FR-002 | Generic ground-truth domain model | The backend and frontend shall adopt the generic schema in `gt_schema_v5_generic.py` as the core item contract, including history, contextEntries, toolCalls, expectedTools, feedback, metadata, plugins, comment, provenance, and tracePayload. | G-001, G-002 | Agentic Curator, ML Engineer | P0 | CRUD, serialization, editing, and export operate on the generic schema with the documented camelCase aliases | Core must not reintroduce RAG-only required fields |
| FR-003 | Reusable plumbing preservation | Existing routing, service orchestration, repository abstractions, assignment lifecycle, auth, telemetry, snapshot/export pipeline, and computed-tag infrastructure shall be reused where compatible with the redesigned core. | G-005 | Curation Lead, ML Engineer | P1 | Architecture review shows plumbing is retained behind new generic contracts instead of rewritten from scratch | Reuse plumbing, not RAG-first semantics |
| FR-004 | Wireframe-aligned workspace shell | The frontend shall implement the primary curation shell described in the wireframe, including queue/sidebar, split-pane layout, draggable gutter, evidence area, item actions, and mobile evidence drawer. | G-001 | Agentic Curator | P0 | Workspace behavior and panel hierarchy match the wireframe's primary interaction model | The wireframe is the UX source of truth |
| FR-005 | Queue and selection workflow | Curators shall view, refresh, select, and request/assign items from a queue that shows item ID, status, category/tag hints, and conversation preview. | G-001 | Agentic Curator, Curation Lead | P0 | Queue supports item selection and status awareness without opening a second application mode | |
| FR-006 | Conversation display and editing | The workspace shall display conversation history with flexible role strings and permit editing of applicable agent/user turns inline. | G-001, G-002 | Agentic Curator | P0 | Conversation renders arbitrary role labels; edited content persists on save; empty messages are blocked by validation | Role names are not limited to a fixed enum |
| FR-007 | Tool calls as first-class review objects | Tool calls shall render as an ordered, expandable review surface with sequence metadata, grouping support for parallel calls, tool/subagent identity, arguments, responses, and decision controls. | G-001, G-002 | Agentic Curator | P0 | Tool calls are visible without plugin code; expanded details show arguments and responses; parallel group information is preserved | Derived from wireframe and generic schema |
| FR-008 | Tool necessity decisions | Curators shall mark tool calls as required, optional, or not needed via the `expectedTools` model. The default state is allowed/optional, and approval shall require at least one required tool unless a plugin explicitly overrides that rule for a workflow. | G-001, G-002 | Agentic Curator | P0 | Decisions persist to `expectedTools`; overlap validation is enforced; approval is blocked when no required tool exists in core agentic flow | Aligns with `AGENTIC_REQUIREMENTS.md` |
| FR-009 | Context entry editing | Curators shall add, edit, and remove `contextEntries` as key/value pairs using generic editing controls that support primitive and structured values. | G-001, G-002 | Agentic Curator | P1 | Context entries round-trip without losing type information | |
| FR-010 | Generic evidence and detail panels | The workspace shall expose core panels for feedback, metadata, trace payload, tags, curator comments, and plugin data, with default renderers that can handle unknown shapes gracefully and explicitly. | G-001, G-002 | Agentic Curator | P0 | Unknown data shapes still render meaningfully through default components; no field is hidden because a custom renderer is missing | Default renderers may use key/value or JSON tree views |
| FR-011 | Field component registry | The frontend shall provide a field component registry that resolves default and plugin-contributed components for flexible fields by discriminator (for example plugin kind, feedback source, metadata signature, tool name, or context key) and falls back to defaults when no custom component is registered. The registry shall support passive renderers and action-capable review components. | G-002, G-003 | Plugin Author | P0 | Registry supports register and resolve; unknown discriminators use documented defaults; action-capable components can be registered for `plugins[].data` and `toolCalls[].response` without modifying core component code | |
| FR-012 | Plugin pack contribution model | Plugin packs shall be able to contribute field component overrides, action-capable review components, supplemental workspace panels, retrieval review experiences, explorer columns/filters, derived item summaries, validation rules, computed tags, import/export transforms, and metrics cards through documented extension points. | G-002, G-003, G-006 | Plugin Author, Curation Lead | P0 | A plugin pack can add domain behavior without forking the core app, reviving a mode branch, or flattening per-tool-call workflow data into host-specific fields | This is the primary extensibility contract |
| FR-013 | Core approval workflow | Core approval shall validate generic integrity rules for agentic items, including valid history content, non-empty edited fields, and tool decision completeness. Plugin packs may add domain-specific approval gates on top. | G-001, G-002 | Agentic Curator | P0 | Generic approval rules run for all items; plugin rules can block approval with explicit messages; approval behavior is deterministic and testable | RAG-specific reference gates move to the RAG pack |
| FR-014 | RAG compatibility pack | The redesigned platform shall include a RAG compatibility pack that reproduces the essential existing RAG-focused curation flow through plugin surfaces. This includes retrieval-specific search integration, curator selection of primary and bonus references, persisted plugin-owned reference data, reference-centric validation, multi-turn reference attachment where applicable, and any additional explorer/approval semantics needed for RAG curation. Richer legacy RAG-only affordances that are not required for the curator's essential workflow may be simplified in v1. | G-003 | Agentic Curator, Plugin Author, ML Engineer | P0 | Existing RAG flow is achievable on the new platform without a dedicated app mode or second editor tree, and RAG reference state persists without reintroducing RAG-only core fields | This requirement proves the generic architecture is real |
| FR-015 | Compatibility data adapters | The platform shall support plugin-provided import/export or adapter logic so workflows such as RAG can project their domain-specific shapes into the generic core contract and back out to the required snapshot shape. Legacy RAG payload compatibility shall be handled at those boundaries rather than through a permanent transitional read path in the redesigned core. | G-003, G-005 | ML Engineer, Plugin Author | P1 | RAG compatibility pack can ingest and export its workflow data without changing the generic core schema or requiring a shipped dual-read compatibility layer | Adapter ownership belongs outside the core data contract |
| FR-016 | Explorer extensibility | The explorer/list view shall support a generic baseline of columns and filters plus plugin-contributed columns, derived fields, and filter controls. | G-001, G-003 | Curation Lead | P1 | Core explorer works for generic items; plugin pack adds workflow-specific filters/columns without core forks | |
| FR-017 | Tagging extensibility | The system shall support manual tags and registry-driven computed tags in the generic core, and plugin packs may contribute domain-specific tag providers or glossaries. | G-005, G-006 | Curation Lead, Plugin Author | P1 | Tags remain visible and editable through one shared pattern; plugin-provided computed tags appear without custom core branches | Reuse current registry pattern where practical |
| FR-018 | Metrics and stats extensibility | The stats experience shall provide generic operational metrics plus plugin-contributed workflow metrics. | G-005, G-006 | Curation Lead | P1 | Core metrics render for all datasets; plugin-specific cards appear through the extension model | |
| FR-019 | Lifecycle actions and concurrency | Save draft, approve, skip, delete, restore, duplicate, assignment, and ETag-based concurrency controls shall continue to operate on the redesigned core items. | G-001, G-005 | Agentic Curator, Curation Lead | P0 | Lifecycle operations work with the generic schema and preserve current concurrency expectations | Reuse existing assignment/concurrency plumbing where possible |
| FR-020 | Legacy code retirement | Once the generic core and RAG compatibility pack meet acceptance, the team shall remove obsolete RAG-first editor stacks, separate-mode branches, and no-longer-used validation paths. | G-004 | Engineering Team | P1 | Final architecture contains one core editor stack and documented plugin packs rather than parallel host implementations | Deletion is part of the requirement, not optional cleanup |
| FR-021 | Plugin contract documentation | The project shall document how to build a plugin pack, what extension points are available, and what guarantees the core provides. | G-003, G-006 | Plugin Author | P1 | Engineers can implement a new plugin pack using repository documentation and tests rather than reverse-engineering the core | Documentation may live alongside existing architecture/docs surfaces |
| FR-022 | Explicit startup validation | Plugin registration and core-plugin contract validation shall run at startup, and invalid plugins shall fail explicitly rather than being silently ignored. | G-005, G-006 | Plugin Author, Curation Lead | P1 | Misconfigured plugin packs surface actionable startup errors; the system does not run in a partially wired state without notice | Protects correctness of a plugin-based architecture |
| FR-023 | Feedback component surface | The feedback surface shall expose a documented default component for unknown feedback shapes and allow plugin overrides keyed by feedback source or discriminator. | G-002, G-006 | Agentic Curator, Plugin Author | P1 | Unknown feedback payloads remain readable by default; known sources can register custom components without host changes | |
| FR-024 | Metadata component surface | The metadata surface shall expose a documented default component for arbitrary metadata structures and allow plugin overrides keyed by metadata signature or discriminator. | G-002, G-006 | Agentic Curator, Plugin Author | P1 | Flat and nested metadata render through documented defaults; custom components can override known shapes without host changes | |
| FR-025 | Plugin payload component surface | Each `plugins[].data` payload shall render through a documented default component and may be upgraded to an action-capable review component keyed by plugin kind when the workflow requires editing or guided curation behavior. | G-002, G-003, G-006 | Agentic Curator, Plugin Author | P0 | Unknown plugin payloads remain readable by default; plugin-specific review components can edit and persist plugin-owned data without host schema changes | |
| FR-026 | Trace payload component surface | The trace payload surface shall expose a documented default component for arbitrary trace payloads and allow plugin overrides for known trace formats or workflow-specific evidence views. | G-001, G-002 | Agentic Curator, Plugin Author | P1 | Arbitrary trace payloads remain inspectable by default; known formats can register richer components without host forks | |
| FR-027 | Context value component surface | Each `contextEntries[].value` shall render through a documented default component based on value shape and may be overridden by plugin components keyed by context entry type or key pattern. | G-001, G-002 | Agentic Curator, Plugin Author | P1 | Primitive and structured context values render and round-trip through defaults; plugins can provide richer components for known contexts | |
| FR-028 | Tool response component surface | Each `toolCalls[].response` shall render through a documented default component and may be upgraded to an action-capable review component keyed by tool identity when a workflow requires structured review or editing actions. | G-001, G-002, G-003 | Agentic Curator, Plugin Author | P0 | Unknown tool responses remain inspectable by default; tool-specific review components can add structured review behavior without host forks | |
| FR-029 | Retrieval tool-call specialization | The RAG compatibility pack shall treat retrieval as a specialized `toolCalls[].response` review experience. Retrieval review components shall allow curators to inspect normalized candidates, select primary and bonus references, and persist those decisions as plugin-owned data keyed to the retrieval tool call instance. | G-003 | Agentic Curator, Plugin Author, ML Engineer | P0 | Retrieval remains a tool-call-centered workflow; selected references are stored per retrieval call rather than flattened into host-level RAG fields | |
| FR-030 | Derived retrieval summaries | Plugin packs shall be able to derive item-level summaries from per-tool-call retrieval data for queue, explorer, and approval flows without flattening the stored per-call data model. | G-003, G-005, G-006 | Curation Lead, Plugin Author | P1 | Queue/explorer/approval can consume derived signals such as selected-reference counts or unresolved retrieval steps while canonical storage remains per retrieval call | |
| FR-031 | Retrieval candidate contract | Retrieval adapters shall normalize different search engine outputs into a common candidate-reference contract for retrieval review while preserving the raw backend response for fallback rendering, auditability, and export logic. | G-003, G-005 | ML Engineer, Plugin Author | P0 | At least one retrieval review component can operate across multiple backend adapters through the common candidate contract, and the raw backend payload remains available | |

### Feature Hierarchy (Optional)
```plain
Ground Truth Curator
├── Generic Core
│   ├── Queue / Explorer / Stats
│   ├── Workspace Shell
│   ├── Conversation Editing
│   ├── Tool Call Review
│   ├── Context / Feedback / Metadata / Trace Panels
│   ├── Assignment / Save / Approval / Export
│   └── Field Component + Plugin Registries
├── Plugin Packs
│   ├── RAG Compatibility Pack
│   │   ├── Retrieval Tool-Call Review
│   │   ├── Candidate Reference Normalizers
│   │   ├── Per-Call Reference Selection State
│   │   ├── Derived Queue / Explorer / Approval Summaries
│   │   ├── RAG Approval Rules
│   │   ├── RAG Explorer Fields
│   │   └── RAG Import / Export Adapters
│   └── Future Domain Packs
└── Shared Plumbing
    ├── API Routes / Services / Repositories
    ├── Auth / Telemetry / Snapshot Pipeline
    └── Computed Tag Infrastructure
```

## 7. Non-Functional Requirements
| NFR ID | Category | Requirement | Metric/Target | Priority | Validation | Notes |
|--------|----------|-------------|---------------|----------|-----------|-------|
| NFR-001 | Performance | The workspace shall render a representative item with up to 20 tool calls and a large trace payload without visible jank on standard developer hardware | Initial interactive render <= 1s for reference dataset | P0 | Frontend performance test using representative wireframe-like data | |
| NFR-002 | Performance | Draft save operations shall remain within current acceptable latency bounds despite larger generic payloads | Save round-trip <= 2s P95 | P0 | API/load testing | |
| NFR-003 | Reliability | ETag concurrency control shall prevent lost updates in the redesigned core | Zero lost updates in concurrent edit tests | P0 | Concurrency integration tests | |
| NFR-004 | Scalability | Bulk import and snapshot export shall support large generic datasets without schema-specific hacks in the core | 1000-item import/export succeeds without timeout | P1 | Batch import/export test | |
| NFR-005 | Security | Existing auth, RBAC, and PII handling patterns shall continue to apply to the redesigned core and plugin-provided panels | No reduction in current security posture | P0 | Security review and regression tests | Plugins must not bypass core data protections |
| NFR-006 | Accessibility | Core workspace interactions shall remain keyboard accessible and preserve readable contrast/state signaling | Keyboard navigation and contrast meet current accessibility standards | P1 | Manual accessibility review | |
| NFR-007 | Maintainability | The final product shall ship one host editor architecture, not duplicated RAG and agentic host stacks | No permanent duplicate host stacks remain | P0 | Architecture/code review | |
| NFR-008 | Extensibility | The RAG compatibility pack shall be implementable through documented extension points without modifying core host behavior beyond those contracts | RAG pack delivered without restoring a second host architecture | P0 | Implementation review against extension-point inventory | |
| NFR-009 | Observability | Plugin registration, approval failures, and major lifecycle events shall emit structured telemetry consistent with existing observability conventions | Events appear in `.harness/logs.jsonl` or equivalent runtime telemetry | P1 | Harness verification / log inspection | |
| NFR-010 | Startup correctness | Invalid or incomplete plugin wiring shall fail fast with actionable errors instead of silently degrading behavior | 100% of plugin contract failures produce explicit startup error paths | P1 | Startup validation tests | |
| NFR-011 | Runtime isolation | Plugin-contributed field components shall run behind error boundaries with explicit fallback behavior so runtime failures degrade to safe default views rather than breaking the curation workspace | 100% of injected component failures preserve workspace operation with visible fallback state | P0 | Frontend fault-injection test / manual review | Applies to retrieval review components and other flexible-field overrides |
| NFR-012 | Low-overhead extensibility | Optional plugin-contributed field components shall be lazy-loaded and add near-zero startup overhead when unused | Registry initialization <= 5 ms; no additional network requests until a custom component is needed | P1 | Startup performance test with default-only configuration | Prevents optional RAG surfaces from bloating the generic host |

## 8. Data & Analytics (Conditional)
### Inputs
Core inputs include generic ground-truth records matching `agentic-core/v1`, trace payloads, context entries, tool call records, manual/computed tags, and plugin-defined supplemental payloads.

### Outputs / Events
Approved datasets, snapshot exports, item lifecycle events, plugin validation outcomes, and operational metrics for queue/explorer/stats views.

### Instrumentation Plan
| Event | Trigger | Payload | Purpose | Owner |
|-------|---------|---------|---------|-------|
| `curation.item_saved` | User saves draft | item id, dataset, plugin pack, status, validation summary | Track editing throughput and save health | TBD |
| `curation.item_approved` | Item approved | item id, dataset, plugin pack, tool decision count | Measure approval throughput and completeness | TBD |
| `curation.plugin_validation_failed` | Plugin blocks action or startup | plugin name, error code, action | Detect broken plugin packs quickly | TBD |
| `curation.renderer_fallback_used` | Default renderer used for flexible payload | field type, discriminator, plugin pack | Identify missing custom renderers | TBD |
| `curation.snapshot_exported` | Snapshot/export succeeds | dataset, item count, plugin pack | Track downstream dataset generation | TBD |

### Metrics & Success Criteria
| Metric | Type | Baseline | Target | Window | Source |
|--------|------|----------|--------|--------|--------|
| Curator throughput | Operational | Current baseline tied to RAG-only flow | Meets or exceeds current curation throughput after redesign | TBD | App telemetry |
| Approval success rate | Quality | No generic agentic baseline | Stable approval flow with actionable failures | TBD | App telemetry |
| RAG compatibility coverage | Delivery | 0% on redesigned core | Existing RAG flow demonstrably runs via plugin pack | Release gate | Integration tests / manual review |
| Legacy host code retired | Maintainability | Parallel host code exists today | Obsolete host branches removed before completion | Release gate | Architecture review |

## 9. Dependencies
| Dependency | Type | Criticality | Owner | Risk | Mitigation |
|-----------|------|-------------|-------|------|-----------|
| `wireframes/agent-curation-wireframe-v2.2.html` | UX reference | Critical | Product/Design | Misreading target workflow | Treat wireframe as primary UX reference and review gaps explicitly |
| `wireframes/gt_schema_v5_generic.py` | Data contract | Critical | Engineering | Schema drift during implementation | Keep schema as core source of truth |
| Existing API/service/repository plumbing | Internal system | High | Engineering | Reuse boundaries may be leaky | Refactor behind generic domain contracts |
| Current computed-tag registry pattern | Internal pattern | Medium | Engineering | Registry may be too RAG-shaped | Extend or refactor registry instead of duplicating it |
| RAG workflow knowledge | Domain reference | High | Product/Engineering | Compatibility pack may miss must-have behavior | Validate parity with current flow before legacy deletion |

## 10. Risks & Mitigations
| Risk ID | Description | Severity | Likelihood | Mitigation | Owner | Status |
|---------|-------------|----------|------------|------------|-------|--------|
| R-001 | The core becomes "generic" in name only and still encodes hidden RAG assumptions | High | Medium | Make RAG prove the extension model by living entirely in a compatibility pack | TBD | Open |
| R-002 | Over-generalization slows delivery of the wireframe-defined primary flow | High | Medium | Prioritize the wireframe flow first; add only extension points needed to support RAG compatibility and clear future growth | TBD | Open |
| R-003 | Legacy code remains indefinitely because parity is never made explicit | Medium | Medium | Make deletion a release requirement with clear acceptance criteria | TBD | Open |
| R-004 | Large trace payloads and flexible renderers degrade editor performance | Medium | Medium | Set performance budgets, use representative data, and optimize large payload rendering paths | TBD | Open |
| R-005 | Plugin contracts are too weak, forcing direct core modifications for compatibility packs | High | Medium | Define and test extension surfaces early, then implement the RAG pack against them | TBD | Open |

## 11. Privacy, Security & Compliance
### Data Classification
Ground-truth items and trace payloads may contain sensitive operational or user-derived data and must retain the current repository's privacy and access controls.

### PII Handling
The redesigned core shall continue using existing backend privacy and PII handling patterns. Plugin packs and renderers must not expose raw sensitive data outside those controls.

### Threat Considerations
The plugin model increases the number of extension surfaces, so plugin registration, renderer execution, and export transforms must be constrained to trusted repository code and validated explicitly at startup.

### Regulatory / Compliance (Conditional)
| Regulation | Applicability | Action | Owner | Status |
|-----------|--------------|--------|-------|--------|
| Internal data handling policies | Applicable | Preserve current auth, auditing, and PII controls through redesign | TBD | Open |

## 12. Operational Considerations
| Aspect | Requirement | Notes |
|--------|-------------|-------|
| Deployment | Deploy one redesigned curation product with plugin registration, not separate long-lived host modes | |
| Rollback | Roll back by reverting the redesign deployment if critical defects appear before legacy deletion is finalized | |
| Monitoring | Reuse current telemetry and harness conventions for lifecycle and plugin events | |
| Alerting | Surface plugin startup and approval validation failures in operational telemetry | |
| Support | Engineering team supports core; domain owners support their plugin packs | |
| Capacity Planning | Size performance testing around large trace payloads and tool-call-heavy items | |

## 13. Rollout & Launch Plan
### Phases / Milestones
| Phase | Date | Gate Criteria | Owner |
|------|------|---------------|-------|
| Core contract and extension design | TBD | Generic domain contract, plugin interfaces, and deletion targets approved | TBD |
| Wireframe-first workspace delivery | TBD | Primary agentic workflow matches wireframe for generic core items | TBD |
| RAG compatibility pack | TBD | Existing RAG flow works on the new platform via plugins and adapters | TBD |
| Legacy retirement and hardening | TBD | Obsolete host code removed; performance, telemetry, and rollout checks pass | TBD |

### Feature Flags (Conditional)
| Flag | Purpose | Default | Sunset Criteria |
|------|---------|---------|----------------|
| Temporary migration flags only | Support implementation sequencing while old and new code coexist briefly | Off in final release | Remove before launch of redesigned host architecture |

### Communication Plan (Optional)
Communicate clearly that this PRD supersedes the earlier separate-mode direction. Reviewers should evaluate the redesign based on whether the generic core can host both the target agentic workflow and the RAG compatibility workflow without architectural duplication.

## 14. Open Questions
| Q ID | Question | Owner | Deadline | Status |
|------|----------|-------|----------|--------|
| Q-001 | What is the minimal plugin surface set required for the RAG compatibility pack to achieve parity without hidden core exceptions? | TBD | TBD | Resolved |
| Q-002 | Should legacy RAG API payloads be adapted at import/export boundaries only, or is a transitional read-path needed during implementation? | TBD | TBD | Resolved |
| Q-003 | Which current RAG behaviors are mandatory for v1 compatibility versus acceptable to simplify while there are no active users? | TBD | TBD | Resolved |
| Q-004 | Should the optional rules engine remain fully separate in v1, or should the plugin model reserve a standard hook for future rules-engine integration now? | TBD | TBD | Resolved |

Resolved Q-001: The minimal RAG compatibility surface must include a retrieval review plugin experience that can bind domain search backends, let curators select primary and bonus references, persist those selections in plugin-owned data on the generic core, and integrate with validation, explorer, computed-tag, and import/export extension points. The generic host schema must not regain a RAG-only `refs` field.

Resolved Q-002: Legacy RAG payloads should be adapted at import/export boundaries only. The redesigned system should store and read the normalized generic record, and any migration toggles used during implementation must remain temporary rather than becoming a shipped transitional read path.

Resolved Q-003: v1 compatibility should preserve the curator-visible essentials of the current RAG flow: retrieval/search, primary and bonus reference selection, reference visit validation when enabled, multi-turn reference attachment where applicable, assignment/approval/export lifecycle continuity, and tags. Richer legacy RAG-only affordances such as stricter key-paragraph expectations, older grounding-summary/evaluation-specific surfaces, and similar non-essential conveniences may be simplified while there are no active users.

Resolved Q-004: The optional rules engine should remain fully separate in v1. The plugin model should not reserve a dedicated standard hook for rules-engine integration until the generic plugin model and the RAG compatibility pack are proven in practice.

## 15. Changelog
| Version | Date | Author | Summary | Type |
|---------|------|--------|---------|------|
| 0.6 | 2026-03-11 | Copilot | Expanded extensibility requirements to explicitly cover six flexible field surfaces, action-capable tool/plugin components, retrieval-as-tool-call review, derived summaries, common retrieval candidate contracts, and runtime/performance guardrails | Update |
| 0.5 | 2026-03-11 | Copilot | Resolved Q-004 by keeping the optional rules engine separate in v1 with no reserved standard hook yet | Update |
| 0.4 | 2026-03-11 | Copilot | Resolved Q-003 by preserving essential RAG curator workflow while allowing simplification of non-essential legacy affordances in v1 | Update |
| 0.3 | 2026-03-11 | Copilot | Resolved Q-002 by defining boundary-only legacy RAG payload adaptation with no permanent transitional read path | Update |
| 0.2 | 2026-03-11 | Copilot | Resolved Q-001 by defining retrieval review as a plugin-owned RAG compatibility surface with persisted primary and bonus references | Update |
| 0.1 | 2026-03-11 | Copilot | Created new PRD that supersedes the separate-mode direction and defines an agentic-first redesign with RAG compatibility via plugins | Draft |

## 16. References & Provenance
| Ref ID | Type | Source | Summary | Conflict Resolution |
|--------|------|--------|---------|--------------------|
| REF-001 | Wireframe | `wireframes/agent-curation-wireframe-v2.2.html` | Primary UX definition for the target agentic-first curation workflow | Takes precedence for workspace and interaction design |
| REF-002 | Schema | `wireframes/gt_schema_v5_generic.py` | Primary generic data contract for the redesigned core | Takes precedence for core record shape |
| REF-003 | Notes | `wireframes/AGENTIC_REQUIREMENTS.md` | Supporting requirements and Peter feedback, including tool-call-first review, removal of grounding summary/evaluation criteria, and required-tool expectation | Used to clarify behaviors where the wireframe/schema are implicit |
| REF-004 | Superseded PRD | `docs/prds/agentic-curation-mode.md` | Prior direction based on separate mode; retained only as historical context | This PRD supersedes it where directions conflict |

### Citation Usage
The wireframe defines the target user workflow and visual hierarchy. The generic schema defines the core persisted record shape. `AGENTIC_REQUIREMENTS.md` clarifies supporting behavioral expectations that are not fully expressed in the schema alone. The older `agentic-curation-mode.md` is included both to preserve history and to carry forward the earlier explicit inventory of pluggable flexible-field surfaces, now reframed for the redesigned single-core architecture.

## 17. Appendices (Optional)
### Glossary
| Term | Definition |
|------|------------|
| Generic core | The redesigned host architecture that understands agentic schema primitives and plugin extension points |
| Plugin pack | A bundled set of renderers, rules, adapters, metrics, and panels that implement a domain workflow on top of the generic core |
| RAG compatibility pack | The plugin pack that recreates the existing reference-centric RAG curation flow on the generic core |
| Legacy host code | Current RAG-first editor/mode-specific paths targeted for retirement after parity |

### Additional Notes
This PRD intentionally treats code deletion and host-architecture simplification as product requirements. Because there are no current users of the existing setup, the redesign should optimize for the best future architecture rather than preserving the previous one.

Generated 2026-03-11T04:10:52.010Z by GitHub Copilot CLI (mode: full)
<!-- markdown-table-prettify-ignore-end -->
