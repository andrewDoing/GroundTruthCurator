# Frontend Implementation Analysis: Agentic Curation Redesign vs PRD Requirements

## Executive Summary

The frontend has **partial implementation** of the agentic-first redesign. The generic schema fields (toolCalls, expectedTools, contextEntries, feedback, metadata, plugins, tracePayload) are passed through the API adapter and rendered in a read-only TracePanel. However, **critical gaps exist** in:

1. **No field component registry** — No pluggable component system for flexible fields
2. **No action-capable editors** — Cannot edit generic fields (only read-only default renderers)
3. **TracePanel is display-only** — No mechanism for plugins to contribute custom panels
4. **No approval rule extensibility** — Approval logic is hardcoded, not pluggable
5. **No explorer/stats extensibility** — No mechanism for plugins to add columns/filters/metrics
6. **RAG compatibility stuck on references** — No architecture for plugin-specific data persistence
7. **No explicit startup validation** for plugin contracts
8. **Tests/documentation minimal** — No test suite for agentic workflow; no plugin contract docs

The codebase is **70-80% prepared** for the redesign (schemas, models, validators in place) but **missing 20-30%** of the extensibility infrastructure required by the PRD.

---

## Current Implementation Status by PRD Feature

### ✅ Implemented Features

#### FR-002: Generic Ground-Truth Domain Model
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/models/groundTruth.ts` (lines 1-255)
- **Evidence**:
  - All agentic schema types defined: `ToolCallRecord`, `ContextEntry`, `ExpectedTools`, `FeedbackEntry`, `PluginPayload`
  - Core item schema includes: `history`, `scenarioId`, `contextEntries`, `toolCalls`, `expectedTools`, `feedback`, `metadata`, `plugins`, `traceIds`, `tracePayload`
  - Helper functions for multi-turn support: `getLastUserTurn()`, `getLastAgentTurn()`, `isMultiTurn()`, `hasEvidenceData()`
- **Completeness**: 100% for data contract layer

#### FR-004: Wireframe-Aligned Workspace Shell
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/demo.tsx` (lines 33-456)
- **Evidence**:
  - Queue sidebar on left (collapsible): `QueueSidebar` component
  - Split-pane layout with draggable gutter: grid cols-1 md:cols-12, responsive
  - Center: editor pane (`CuratePane`)
  - Right: evidence/trace panel (`ReferencesSection`)
  - Mobile collapse to drawer behavior via `lg:hidden`
  - Item actions (save, approve, skip, delete, restore, duplicate, export)
- **Completeness**: 95% (wireframe-aligned; minor polish items remain)

#### FR-005: Queue and Selection Workflow
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/components/app/QueueSidebar.tsx`
- **Evidence**:
  - Queue displays items with ID, status badge, preview, edit state tracking
  - Selection via click or keyboard (arrow keys)
  - Refresh button, self-serve assignment, copy-to-clipboard for ID/dataset/path
  - Unsaved indicator per item
- **Completeness**: 100%

#### FR-006: Conversation Display and Editing
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/components/app/editor/MultiTurnEditor.tsx` (lines 1-150)
- **Evidence**:
  - Conversation history rendered with free-form role labels (role: string, not enum)
  - Editable via `ConversationTurn.tsx` component
  - Add user/agent turns, delete turns with validation
  - Agent turn generation via chat service
- **Completeness**: 100%

#### FR-007: Tool Calls as First-Class Review Objects
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/components/app/TracePanel.tsx` (lines 185-230)
- **Evidence**:
  - ToolCall entries shown with: callType, name, stepNumber, agent, parallelGroup info
  - Expandable details for arguments and response
  - Response JSON rendering (raw or stringified)
  - Indexed display with step numbers
- **Completeness**: 85% (display complete; no action-capable review yet)

#### FR-008: Tool Necessity Decisions
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/models/groundTruth.ts` (lines 35-39), `frontend/src/models/validators.ts`
- **Evidence**:
  - `ExpectedTools` type with `required`, `optional`, `notNeeded` buckets
  - `validateExpectedTools()` checks required tools present in toolCalls
  - Approval gate enforces valid expectedTools (see `frontend/src/models/gtHelpers.ts` lines 62-64)
  - UI will support editing expectedTools once editor component is added
- **Completeness**: 80% (data model 100%; UI editing 0%)

#### FR-010: Generic Evidence and Detail Panels
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/components/app/TracePanel.tsx` (full file, 457 lines)
- **Evidence**:
  - Default collapsible sections for: expectedTools, traceIds, toolCalls, contextEntries, feedback, metadata, plugins, tracePayload
  - Generic KVDict renderer for metadata/trace
  - FeedbackEntryRow, ContextEntryRow, ToolCallEntry, PluginPayloadCard sub-components
  - Graceful fallback: "No data available" when sections empty
- **Completeness**: 85% (read-only; no plugin overrides yet)

#### FR-013: Core Approval Workflow
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/models/gtHelpers.ts` (lines 29-67)
- **Evidence**:
  - `canApproveMultiTurn()`: validates conversation pattern + expected tools
  - `canApproveCandidate()`: generic approval gate (multi-turn or single-turn compat)
  - Integration with validators: `validateConversationPattern()`, `validateExpectedTools()`
  - Approval blocked when: deleted, invalid conversation, missing required tools
- **Completeness**: 90% (core logic present; no plugin extensibility yet)

#### FR-019: Lifecycle Actions and Concurrency
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/demo.tsx` (lines 101-148), `frontend/src/hooks/useGroundTruth.ts`
- **Evidence**:
  - Save draft, approve, skip, delete, restore, duplicate all implemented
  - ETag-based concurrency control in API responses
  - Optimistic UI state management via hook
- **Completeness**: 100%

#### FR-003: Reusable Plumbing Preservation
- **Status**: ✅ IMPLEMENTED
- **Location**: `frontend/src/api/client.ts`, `frontend/src/services/*`, `frontend/src/adapters/apiMapper.ts`
- **Evidence**:
  - OpenAPI-typed client (`client.ts`)
  - Service layer pattern: `groundTruths.ts`, `tags.ts`, `assignments.ts`, `search.ts`, `stats.ts`
  - Adapter layer: `apiMapper.ts` (248 lines) normalizes API payloads to domain models
  - Telemetry, auth (dev user header), repository abstractions preserved
- **Completeness**: 100%

---

### ⚠️ Partially Implemented Features

#### FR-009: Context Entry Editing
- **Status**: ⚠️ PARTIAL
- **Location**: `frontend/src/models/groundTruth.ts` (lines 101-102), `frontend/src/components/app/TracePanel.tsx` (lines 281-297)
- **Evidence**:
  - Data model: `ContextEntry` type defined (key, value)
  - Display: `ContextEntryRow` renders entries as key/value pairs
  - **Gap**: No edit UI for context entries (read-only display only)
- **Completeness**: 40% (model + display; no editing)

#### FR-016: Explorer Extensibility
- **Status**: ⚠️ PARTIAL
- **Location**: `frontend/src/components/app/QuestionsExplorer.tsx` (lines 1-100)
- **Evidence**:
  - Core columns: status, dataset, tags, keyword filters, ID filter, reference URL filter
  - Sort options: status, dataset, tags
  - **Gap**: No documented mechanism for plugins to add columns or filters
- **Completeness**: 60% (core explorer works; no extensibility infrastructure)

#### FR-017: Tagging Extensibility
- **Status**: ⚠️ PARTIAL
- **Location**: `frontend/src/services/tags.ts`, `frontend/src/hooks/useTags.ts`, `frontend/src/models/groundTruth.ts` (lines 128-132)
- **Evidence**:
  - Manual tags (`manualTags`) and computed tags (`computedTags`) supported
  - Tag glossary modal available
  - Tags persist via API
  - **Gap**: No mechanism for plugins to register custom tag providers or glossaries
- **Completeness**: 60% (manual + computed tags work; no plugin extensibility)

#### FR-018: Metrics and Stats Extensibility
- **Status**: ⚠️ PARTIAL
- **Location**: `frontend/src/components/app/pages/StatsPage.tsx`, `frontend/src/services/stats.ts`
- **Evidence**:
  - Core stats: total counts (approved, draft, deleted) per sprint
  - **Gap**: No mechanism for plugins to contribute additional metric cards
- **Completeness**: 40% (basic stats; no extensibility)

---

### ❌ NOT Implemented (Critical Gaps)

#### FR-011: Field Component Registry
- **Status**: ❌ NOT IMPLEMENTED
- **PRD Requirement** (lines 152-157):
  > "The frontend shall provide a field component registry that resolves default and plugin-contributed components for flexible fields by discriminator...The registry shall support passive renderers and action-capable review components."
- **What's Missing**:
  - No registry system (no type definitions, no register/resolve functions)
  - No discriminator-based component lookup
  - No fallback mechanism for unknown components
  - Current approach: hardcoded default renderers in TracePanel
- **Impact**: Cannot plug in custom renderers for feedback, metadata, tool responses, context values

#### FR-012: Plugin Pack Contribution Model
- **Status**: ❌ NOT IMPLEMENTED
- **PRD Requirement** (lines 158-161):
  > "Plugin packs shall be able to contribute field component overrides, action-capable review components, supplemental workspace panels...through documented extension points."
- **What's Missing**:
  - No plugin initialization or registration system
  - No extension point definitions
  - No plugin payload validation at startup
  - No documented contract for plugin authors
- **Impact**: No way to add domain-specific behavior without modifying core

#### FR-014: RAG Compatibility Pack
- **Status**: ❌ NOT IMPLEMENTED (Partial Data Model Only)
- **PRD Requirement** (lines 161-167):
  > "The redesigned platform shall include a RAG compatibility pack that reproduces the existing RAG-focused curation flow through plugin surfaces."
- **What Exists**:
  - `Reference` type with `messageIndex` for per-turn attachment
  - `ReferencesTabs`, `SearchTab`, `SelectedTab` components for retrieval UI
  - `ReferencesSection.tsx` shows RAG compat surface alongside evidence panel
- **What's Missing**:
  - No framework for plugin-specific data persistence (where does RAG plugin store selected references?)
  - No retrieval adapter contract (how do backends normalize search results?)
  - Reference-centric approval gates not yet wired to plugin model
- **Impact**: RAG workflow survives but cannot be truly plugged in

#### FR-015: Compatibility Data Adapters
- **Status**: ❌ NOT IMPLEMENTED
- **PRD Requirement** (lines 166-170):
  > "The platform shall support plugin-provided import/export or adapter logic so workflows such as RAG can project their domain-specific shapes into the generic core contract."
- **What's Missing**:
  - No adapter contract for import/export
  - No mechanism for plugins to transform on read/write
  - Current adapter layer is hard-coded for RAG only
- **Impact**: Cannot support non-RAG domain workflows

#### FR-021: Plugin Contract Documentation
- **Status**: ❌ NOT IMPLEMENTED
- **PRD Requirement** (lines 206-207):
  > "The project shall document how to build a plugin pack, what extension points are available, and what guarantees the core provides."
- **What's Missing**:
  - No plugin architecture documentation
  - No extension point inventory
  - No examples or tutorials for plugin authors
- **Impact**: Plugin authors have no guidance

#### FR-022: Explicit Startup Validation
- **Status**: ❌ NOT IMPLEMENTED
- **PRD Requirement** (lines 208-212):
  > "Plugin registration and core-plugin contract validation shall run at startup, and invalid plugins shall fail explicitly rather than being silently ignored."
- **What's Missing**:
  - No plugin contract validation function
  - No startup hooks
  - No error reporting for misconfigured plugins
- **Impact**: Silent failures if plugins are broken

#### FR-023/024/025/026/027/028: Component Surface Contracts
- **Status**: ❌ NOT IMPLEMENTED
- **PRD Requirements** (lines 213-237):
  > Custom renderers for feedback, metadata, plugin payloads, trace payloads, context values, tool responses
- **What Exists**:
  - Default read-only renderers in TracePanel (lines 264-330)
  - Generic KVDict, FeedbackEntryRow, ContextEntryRow, ToolCallEntry, PluginPayloadCard
- **What's Missing**:
  - No mechanism to register alternative renderers by discriminator
  - No action-capable component support
  - No documented component contracts
- **Impact**: Cannot customize how evidence is displayed or edited

#### FR-029/030/031: Retrieval Tool-Call Specialization
- **Status**: ❌ NOT IMPLEMENTED (Requires FR-012, FR-025, FR-028 First)
- **PRD Requirement** (lines 239-252):
  > "The RAG compatibility pack shall treat retrieval as a specialized toolCalls[].response review experience...Retrieval adapters shall normalize different search engine outputs into a common candidate-reference contract."
- **What's Missing**:
  - No retrieval review component surface
  - No candidate-reference contract
  - No mechanism to persist per-call reference selections as plugin data
  - No backend adapter interface
- **Impact**: Cannot implement sophisticated retrieval-specific curation UI

#### FR-001: Agentic-First Core Architecture
- **Status**: ⚠️ MOSTLY IMPLEMENTED (but not proven via RAG pack)
- **PRD Requirement** (lines 145-148):
  > "The product shall provide one generic curation architecture rather than separate RAG and agentic modes."
- **Current State**:
  - Single generic editor architecture exists (✅)
  - Wireframe-aligned workspace implemented (✅)
  - But: No runtime proof that RAG can operate as a pure plugin without hidden host assumptions
  - The architecture claims to be "generic" but has some RAG-shaped assumptions baked in
- **Completeness**: 70% (framework in place; proof via plugin model missing)

---

## File Structure & Key Components

### Core Files

| Path | Lines | Purpose | Status |
|------|-------|---------|--------|
| `frontend/src/App.tsx` | 7 | App entry point (delegates to demo) | ✅ Complete |
| `frontend/src/main.tsx` | 25 | React root initialization | ✅ Complete |
| `frontend/src/demo.tsx` | 456 | Main app shell, routing (3 views) | ✅ Complete |
| `frontend/src/models/groundTruth.ts` | 255 | Core domain types | ✅ Complete |
| `frontend/src/models/gtHelpers.ts` | 68 | Approval logic | ✅ Complete |
| `frontend/src/models/validators.ts` | 150+ | Conversation, expectedTools, references validation | ✅ Complete |
| `frontend/src/api/client.ts` | 61 | OpenAPI-typed fetch client | ✅ Complete |
| `frontend/src/api/generated.ts` | 73,704 | OpenAPI schema (generated) | ✅ Complete |
| `frontend/src/adapters/apiMapper.ts` | 248 | API response → domain model mapping | ✅ Complete |

### Component Files

| Path | Lines | Purpose | Status |
|------|-------|---------|--------|
| `frontend/src/components/app/QueueSidebar.tsx` | ~120 | Queue list, selection, self-serve | ✅ Complete |
| `frontend/src/components/app/pages/CuratePane.tsx` | 455 | Main editor pane | ✅ Complete |
| `frontend/src/components/app/editor/MultiTurnEditor.tsx` | ~400 | Conversation editing | ✅ Complete |
| `frontend/src/components/app/pages/ReferencesSection.tsx` | 175 | Right-pane evidence + RAG compat | ⚠️ Partial |
| `frontend/src/components/app/TracePanel.tsx` | 457 | Evidence/trace display (read-only) | ⚠️ Partial |
| `frontend/src/components/app/InstructionsPane.tsx` | ~75 | Collapsible instructions | ✅ Complete |
| `frontend/src/components/app/QuestionsExplorer.tsx` | ~400 | Explorer/list view with filters | ✅ Complete |
| `frontend/src/components/app/pages/StatsPage.tsx` | ~60 | Stats view | ✅ Complete |

### Service/Hook Files

| Path | Lines | Purpose | Status |
|------|-------|---------|--------|
| `frontend/src/hooks/useGroundTruth.ts` | ~600 | State management (main hook) | ✅ Complete |
| `frontend/src/services/groundTruths.ts` | ~200 | CRUD API calls | ✅ Complete |
| `frontend/src/services/tags.ts` | ~150 | Tag management | ✅ Complete |
| `frontend/src/services/search.ts` | ~100 | Retrieval search | ✅ Complete |
| `frontend/src/services/stats.ts` | ~60 | Stats fetching | ✅ Complete |
| `frontend/src/services/telemetry.ts` | ~250 | Event logging | ✅ Complete |

---

## Key Evidence Files for PRD Alignment Check

### 1. **Generic Schema Adoption**
- ✅ `frontend/src/models/groundTruth.ts` (lines 87-150): All generic fields present
- ✅ `frontend/src/adapters/apiMapper.ts` (lines 115-143): Pass-through for contextEntries, toolCalls, expectedTools, feedback, metadata, plugins, traceIds, tracePayload
- ✅ `frontend/src/components/app/TracePanel.tsx` (full file): Display all generic fields

### 2. **Wireframe Implementation**
- ✅ `frontend/src/demo.tsx` (lines 278-431): Split-pane layout with queue, editor, evidence
- ✅ `frontend/src/components/app/QueueSidebar.tsx`: Queue sidebar
- ✅ `frontend/src/components/app/pages/CuratePane.tsx`: Editor pane
- ✅ `frontend/src/components/app/pages/ReferencesSection.tsx`: Right-pane evidence

### 3. **Tool Call Review**
- ✅ `frontend/src/components/app/TracePanel.tsx` (lines 185-230): Tool call display
- ✅ `frontend/src/models/groundTruth.ts` (lines 14-23): ToolCallRecord type
- ⚠️ No action-capable tool call editor (read-only only)

### 4. **Expected Tools**
- ✅ `frontend/src/models/groundTruth.ts` (lines 35-39): ExpectedTools type
- ✅ `frontend/src/models/validators.ts`: validateExpectedTools() function
- ✅ `frontend/src/components/app/TracePanel.tsx` (lines 76-183): Expected tools review section
- ⚠️ No UI for curators to edit expectedTools directly

### 5. **Multi-Turn Support**
- ✅ `frontend/src/components/app/editor/MultiTurnEditor.tsx`: Full multi-turn editor
- ✅ `frontend/src/models/groundTruth.ts` (lines 154-209): Helper functions for multi-turn
- ✅ `frontend/src/models/validators.ts`: Conversation pattern validation

### 6. **Approval Logic**
- ✅ `frontend/src/models/gtHelpers.ts` (lines 52-67): canApproveMultiTurn()
- ✅ `frontend/src/models/validators.ts`: validateExpectedTools(), validateConversationPattern()
- ❌ No plugin-extensible approval rules

### 7. **API Adapter**
- ✅ `frontend/src/adapters/apiMapper.ts`: Full mapping layer
- ✅ `frontend/src/api/client.ts`: Typed fetch client

---

## Critical Redesign Gaps

### Gap 1: No Field Component Registry (FR-011)
**What's needed**: A system to register custom renderers for flexible fields (feedback, metadata, plugins, toolCalls.response, etc.) by discriminator (e.g., plugin kind, feedback source, tool name).

**Current state**: TracePanel hardcodes default renderers; no extensibility hook.

**Example of missing code**:
```typescript
// NOT IMPLEMENTED:
type FieldComponentRegistry = {
  registerFeedbackComponent(source: string, component: React.ComponentType<FeedbackComponentProps>): void;
  registerMetadataComponent(signature: string, component: React.ComponentType<MetadataComponentProps>): void;
  registerToolResponseComponent(toolName: string, component: React.ComponentType<ToolResponseComponentProps>): void;
  resolveFeedbackComponent(source: string): React.ComponentType<FeedbackComponentProps>;
  // ... etc
};
```

**Impact**: Cannot customize how evidence is displayed.

### Gap 2: No Plugin Pack Model (FR-012)
**What's needed**: A documented extension-point contract allowing plugins to:
- Contribute field components (via registry above)
- Add workspace panels
- Define approval rules
- Add explorer columns/filters
- Contribute stats cards
- Implement import/export transforms

**Current state**: No plugin initialization, no extension points, no contract.

**Example of missing code**:
```typescript
// NOT IMPLEMENTED:
interface PluginPack {
  name: string;
  version: string;
  registerComponents(registry: FieldComponentRegistry): void;
  registerApprovalRules(gate: ApprovalGate): void;
  registerExplorerFields(explorer: ExplorerRegistry): void;
  registerStatsCards(stats: StatsRegistry): void;
  // ... etc
}

function registerPluginPack(pack: PluginPack): void {
  // Validate, initialize, and wire up the plugin
}
```

**Impact**: Cannot extend the system for new domains.

### Gap 3: No Action-Capable Component Support (FR-025, FR-028)
**What's needed**: The ability to register action-capable review components (not just passive renderers) for `plugins[].data` and `toolCalls[].response`.

**Current state**: TracePanel renders responses as JSON text only; no interactive editing.

**Example of missing code**:
```typescript
// Current (read-only):
<pre>{JSON.stringify(tc.response, null, 2)}</pre>

// Missing (action-capable):
// <ToolResponseReviewComponent toolCall={tc} onSave={...} />
```

**Impact**: Cannot implement domain-specific review workflows (e.g., retrieval candidate selection).

### Gap 4: RAG Compatibility Pack Incomplete (FR-014, FR-029)
**What's needed**: A plugin pack that:
- Treats retrieval as a specialized tool-call review experience
- Normalizes backend search results into a common candidate-reference contract
- Lets curators select primary and bonus references
- Persists those selections as plugin-owned data

**Current state**: `ReferencesSection` and reference UI exist, but:
- No framework for plugin-owned data storage
- No candidate-reference contract
- No retrieval adapter interface
- Reference storage tied to top-level item, not to retrieval tool call

**Impact**: Cannot prove the generic architecture works for RAG as a plugin.

### Gap 5: No Explorer/Stats Extensibility (FR-016, FR-018)
**What's needed**: Documented mechanisms for plugins to:
- Add custom columns to explorer
- Add custom filters
- Add custom metrics cards to stats view

**Current state**: Core explorer and stats work; no plugin hooks.

**Impact**: Cannot show domain-specific insights (e.g., reference coverage metrics for RAG).

### Gap 6: No Startup Validation (FR-022)
**What's needed**: At app startup, validate that all registered plugins conform to the extension contract and fail loudly if they don't.

**Current state**: No startup hooks, no validation, no error reporting.

**Impact**: Silent failures if plugins are misconfigured.

### Gap 7: No Plugin Documentation (FR-021)
**What's needed**: Clear documentation describing:
- How to build a plugin pack
- What extension points are available
- What guarantees the core provides
- Examples and tutorials

**Current state**: No documentation.

**Impact**: Plugin authors have no guidance.

---

## Test & Documentation Status

### Unit/Component Tests
- **Status**: ❌ NONE FOUND
- **Search result**: `find frontend/src -name "*.test.ts*" -o -name "*.spec.ts*"` returned no results
- **Gap**: No test suite for:
  - Agentic workflow (conversation, tool calls, expected tools)
  - Approval logic
  - Validator functions
  - Adapter layer
  - Component rendering

### E2E/Integration Tests
- **Status**: ⚠️ PLANNED BUT NOT IN PLACE
- **Evidence**: `frontend/plans/playwright-e2e-test-plan.md` exists (design doc, not implementation)
- **Gap**: No running test suite

### Implementation Plans
- **Status**: ✅ EXTENSIVE PLANNING DOCS
- **Evidence**: 11 plans in `frontend/plans/`:
  - multi-turn-curation-plan.md
  - turn-specific-references-plan.md
  - questions-explorer-plan.md
  - agent-integration-plan.md
  - etc.
- **Gap**: These describe what needs building, not what was built

### Runtime Documentation
- **Status**: ❌ NO PLUGIN ARCHITECTURE DOCS
- **Gap**: No README or architecture guide for the frontend

### Code Comments
- **Status**: ⚠️ MINIMAL
- **Evidence**:
  - `demo.tsx` (demo.tsx lines 3-4): Delegates to GTAppDemo with no explanation
  - `TracePanel.tsx` (lines 1-17): Good header comment explaining the component
  - Most components lack JSDoc or architecture comments
- **Gap**: New contributors cannot understand the plugin architecture expectations

---

## Specific File-by-File Gaps

### `frontend/src/components/app/TracePanel.tsx`
- ✅ All 7 evidence surfaces implemented (expectedTools, traceIds, toolCalls, contextEntries, feedback, metadata, plugins, tracePayload)
- ❌ No mechanism to register custom renderers
- ❌ No action-capable components (read-only only)
- ⚠️ Plugin payload rendered as generic KVDict; no way for specific plugins to customize

### `frontend/src/components/app/pages/ReferencesSection.tsx`
- ✅ Evidence panel shown at top when agentic data present
- ✅ RAG compat surface shown at bottom
- ⚠️ No framework for plugin-specific data (where does RAG plugin store selected refs?)
- ❌ No mechanism to swap out reference review component

### `frontend/src/models/gtHelpers.ts`
- ✅ Core approval logic works
- ❌ No extension point for plugins to add approval rules
- ⚠️ Comment notes "Retrieval-specific reference gating stays on single-turn compat path until plugin pack work lands" (lines 50-51)

### `frontend/src/hooks/useGroundTruth.ts`
- ✅ State management and CRUD complete
- ❌ No mechanism to wire plugin lifecycle hooks
- ⚠️ No telemetry for plugin events (FR-009)

### `frontend/src/components/app/QuestionsExplorer.tsx`
- ✅ Core explorer works with filters, sorting, pagination
- ❌ No extension point for plugins to add columns
- ❌ No extension point for plugins to add filters

### `frontend/src/components/app/pages/StatsPage.tsx`
- ✅ Core stats displayed
- ❌ No mechanism for plugins to contribute additional metrics

---

## Line-by-Line Evidence of Agentic Schema Support

### Field Definitions
| Field | Model File | Lines | API Mapper | TracePanel |
|-------|------------|-------|-----------|-----------|
| `history` | groundTruth.ts | 98 | apiMapper.ts 31-75 | (editor, not trace) |
| `scenarioId` | groundTruth.ts | 100 | apiMapper.ts 117 | (not displayed) |
| `contextEntries` | groundTruth.ts | 101 | apiMapper.ts 118 | TracePanel 412-424 |
| `toolCalls` | groundTruth.ts | 104 | apiMapper.ts 119 | TracePanel 392-407 |
| `expectedTools` | groundTruth.ts | 106 | apiMapper.ts 120 | TracePanel 76-183 |
| `feedback` | groundTruth.ts | 108 | apiMapper.ts 121 | TracePanel 425-436 |
| `metadata` | groundTruth.ts | 110 | apiMapper.ts 122-125 | TracePanel 437-441 |
| `plugins` | groundTruth.ts | 112 | apiMapper.ts 126-132 | TracePanel 442-452 |
| `traceIds` | groundTruth.ts | 114 | apiMapper.ts 133 | TracePanel 368-371 |
| `tracePayload` | groundTruth.ts | 116 | apiMapper.ts 134-137 | TracePanel 453-457 |

---

## PRD Compliance Scorecard

| Feature | ID | Status | Completeness | Evidence |
|---------|----|----|---|---|
| Agentic-first core | FR-001 | ⚠️ | 70% | demo.tsx architecture in place; RAG plugin proof missing |
| Generic schema | FR-002 | ✅ | 100% | groundTruth.ts, apiMapper.ts |
| Plumbing reuse | FR-003 | ✅ | 100% | api/, services/, adapters/ intact |
| Workspace shell | FR-004 | ✅ | 95% | demo.tsx, all panes implemented |
| Queue workflow | FR-005 | ✅ | 100% | QueueSidebar.tsx |
| Conversation editing | FR-006 | ✅ | 100% | MultiTurnEditor.tsx |
| Tool calls review | FR-007 | ✅ | 85% | TracePanel.tsx; no editing |
| Tool decisions | FR-008 | ✅ | 80% | model 100%, UI 0% |
| Context editing | FR-009 | ⚠️ | 40% | display only, no editor |
| Evidence panels | FR-010 | ✅ | 85% | TracePanel.tsx; no custom renderers |
| Field registry | FR-011 | ❌ | 0% | NOT IMPLEMENTED |
| Plugin pack model | FR-012 | ❌ | 0% | NOT IMPLEMENTED |
| Core approval | FR-013 | ✅ | 90% | gtHelpers.ts; no plugins |
| RAG compat pack | FR-014 | ❌ | 30% | References exist; plugin model missing |
| Adapters | FR-015 | ❌ | 0% | NOT IMPLEMENTED |
| Explorer extensibility | FR-016 | ⚠️ | 60% | core works; no plugins |
| Tag extensibility | FR-017 | ⚠️ | 60% | computed tags work; no plugins |
| Stats extensibility | FR-018 | ⚠️ | 40% | basic stats; no plugins |
| Lifecycle actions | FR-019 | ✅ | 100% | demo.tsx, useGroundTruth.ts |
| Code retirement | FR-020 | ❌ | N/A | (future action) |
| Plugin docs | FR-021 | ❌ | 0% | NOT IMPLEMENTED |
| Startup validation | FR-022 | ❌ | 0% | NOT IMPLEMENTED |
| Feedback surface | FR-023 | ⚠️ | 50% | display only; no custom components |
| Metadata surface | FR-024 | ⚠️ | 50% | display only; no custom components |
| Plugin payload surface | FR-025 | ⚠️ | 50% | display only; no custom or action-capable |
| Trace payload surface | FR-026 | ⚠️ | 50% | display only; no custom components |
| Context value surface | FR-027 | ⚠️ | 50% | display only; no custom components |
| Tool response surface | FR-028 | ⚠️ | 50% | display only; no custom or action-capable |
| Retrieval specialization | FR-029 | ❌ | 0% | NOT IMPLEMENTED (requires FR-012, FR-025, FR-028) |
| Retrieval summaries | FR-030 | ❌ | 0% | NOT IMPLEMENTED |
| Retrieval contract | FR-031 | ❌ | 0% | NOT IMPLEMENTED |

**Overall Completion**: ~60% of functional requirements, ~40% of extensibility requirements

---

## Biggest Redesign Gaps Summary

1. **Field Component Registry (FR-011)** — 0% complete. No pluggable renderer system.
2. **Plugin Pack Model (FR-012)** — 0% complete. No extension point contracts.
3. **RAG Compatibility as Plugin (FR-014)** — 30% complete. Data model exists; plugin framework missing.
4. **Retrieval Specialization (FR-029)** — 0% complete. Blocks proof that generic architecture works.
5. **Startup Validation (FR-022)** — 0% complete. No contract validation infrastructure.
6. **Plugin Documentation (FR-021)** — 0% complete. No guides for plugin authors.
7. **Action-Capable Components (FR-025, FR-028)** — 0% complete. Read-only renderers only.
8. **Explorer/Stats Extensibility (FR-016, FR-018)** — 60% complete. Core works; no plugin hooks.

**To complete the redesign, approximately 30-40% more work is needed in the frontend**, focused on building the plugin framework and extension points rather than new features. The foundation is solid; the extensibility layer is missing.

