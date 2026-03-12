# Frontend Agentic Curation Redesign: Quick Reference

## Key Files at a Glance

### Entry Points & App Shell
- **`frontend/src/main.tsx`** (25 lines) — React root, telemetry init
- **`frontend/src/App.tsx`** (7 lines) — App entry point
- **`frontend/src/demo.tsx`** (456 lines) — **Main app shell, 3 view modes (curate/questions/stats)**

### Core Models & Types
- **`frontend/src/models/groundTruth.ts`** (255 lines) — **All agentic schema types + helpers**
  - ToolCallRecord, ContextEntry, ExpectedTools, FeedbackEntry, PluginPayload
  - Multi-turn helpers: getLastUserTurn(), isMultiTurn(), hasEvidenceData()
- **`frontend/src/models/gtHelpers.ts`** (68 lines) — **Approval logic (canApproveMultiTurn)**
- **`frontend/src/models/validators.ts`** (150+ lines) — **validateExpectedTools(), validateConversationPattern()**

### Pages & Components (Workspace)
- **`frontend/src/components/app/pages/CuratePane.tsx`** (455 lines) — **Main editor pane**
- **`frontend/src/components/app/pages/ReferencesSection.tsx`** (175 lines) — **Right-pane (Evidence + RAG compat)**
- **`frontend/src/components/app/QueueSidebar.tsx`** (~120 lines) — **Queue list and selection**
- **`frontend/src/components/app/pages/StatsPage.tsx`** (~60 lines) — **Stats view**

### Evidence & Trace Display
- **`frontend/src/components/app/TracePanel.tsx`** (457 lines) — **🔴 CRITICAL: Read-only evidence display**
  - Lines 76-183: ExpectedTools review
  - Lines 185-230: ToolCall entries
  - Lines 234-260: Feedback entries
  - Lines 281-297: Context entries
  - Lines 298-330: Plugin payloads
  - ❌ **GAP: No mechanism to register custom renderers**

### Conversation & Multi-Turn
- **`frontend/src/components/app/editor/MultiTurnEditor.tsx`** (~400 lines) — **Multi-turn editor**
- **`frontend/src/components/app/editor/ConversationTurn.tsx`** (~300 lines) — **Turn editing UI**
- **`frontend/src/components/app/editor/TurnReferencesModal.tsx`** — **Per-turn reference modal**

### Explorer & Filtering
- **`frontend/src/components/app/QuestionsExplorer.tsx`** (~400 lines) — **Explorer with filters**
- **`frontend/src/components/app/InstructionsPane.tsx`** (~75 lines) — **Collapsible instructions**

### State Management & Hooks
- **`frontend/src/hooks/useGroundTruth.ts`** (~600 lines) — **🔴 CRITICAL: Main state hook**
  - Item selection, editing, save/approve workflows
  - Search and references management
  - Multi-turn support
  - ❌ **GAP: No plugin lifecycle hooks**

### API Client & Services
- **`frontend/src/api/client.ts`** (61 lines) — **OpenAPI-typed fetch client**
- **`frontend/src/api/generated.ts`** (73,704 lines) — **OpenAPI schema (generated)**
- **`frontend/src/adapters/apiMapper.ts`** (248 lines) — **🔴 CRITICAL: API response → domain mapping**
  - Lines 115-143: Generic field pass-through
  - Lines 225-236: Round-trip on save
  - ✅ Handles all agentic schema fields
- **`frontend/src/services/groundTruths.ts`** (~200 lines) — **CRUD operations**
- **`frontend/src/services/tags.ts`** (~150 lines) — **Tag management**
- **`frontend/src/services/assignments.ts`** — **Assignment workflows**
- **`frontend/src/services/search.ts`** — **Retrieval search**
- **`frontend/src/services/stats.ts`** — **Stats fetching**
- **`frontend/src/services/telemetry.ts`** — **Event logging**

---

## What's Implemented (70% Foundation)

### ✅ Data Models
- ✅ Generic schema types (ToolCallRecord, ContextEntry, ExpectedTools, FeedbackEntry, PluginPayload)
- ✅ All agentic fields on GroundTruthItem passed through API adapter
- ✅ Multi-turn conversation support with free-form roles

### ✅ Workspace Shell
- ✅ Queue sidebar (left)
- ✅ Editor pane (center)
- ✅ Evidence/trace panel (right)
- ✅ Mobile responsive (collapses to drawer)
- ✅ 3 view modes: curate, questions explorer, stats

### ✅ Conversation & Editing
- ✅ Multi-turn editor with add/delete turns
- ✅ Free-form role strings (not enum-constrained)
- ✅ Per-turn reference attachment (messageIndex)
- ✅ Agent turn generation via chat service

### ✅ Tool Call & Evidence Display
- ✅ Tool calls shown with callType, name, stepNumber, agent info
- ✅ Expandable response details (JSON rendering)
- ✅ Expected tools review (required/optional/not-needed)
- ✅ Context entries, metadata, feedback, trace IDs, plugins, trace payload display

### ✅ Approval & Validation
- ✅ canApproveMultiTurn() checks conversation pattern + expected tools
- ✅ validateExpectedTools() ensures required tools in toolCalls
- ✅ validateConversationPattern() validates user/agent alternation
- ✅ Approval blocked when: deleted, invalid pattern, missing required tools

### ✅ Queue & Explorer
- ✅ Item selection with keyboard nav
- ✅ Filters: status, dataset, tags, ID, reference URL, keyword
- ✅ Sorting, pagination
- ✅ Self-serve assignment, refresh

### ✅ Lifecycle Actions
- ✅ Save draft, approve, skip, delete, restore, duplicate, export
- ✅ ETag-based concurrency control

---

## What's Missing (30% Extensibility)

### ❌ Field Component Registry (FR-011)
- **Status**: 0% implemented
- **What's missing**: No way to register custom renderers for feedback, metadata, tool responses, context values
- **Current**: Hardcoded default renderers in TracePanel
- **Impact**: Cannot customize how evidence is displayed without modifying core
- **Effort**: 2-3 days

### ❌ Plugin Pack Model (FR-012)
- **Status**: 0% implemented
- **What's missing**: No extension points, no plugin initialization, no startup validation
- **Current**: No plugin system exists
- **Extension points needed**:
  - Field component registry (feedback, metadata, tool response, context value)
  - Approval rules (custom gates)
  - Explorer columns/filters
  - Stats cards
  - Import/export transforms
- **Impact**: Cannot extend for new domains without core modifications
- **Effort**: 3-4 days

### ❌ Action-Capable Components (FR-025, FR-028)
- **Status**: 0% implemented
- **What's missing**: Cannot register interactive (edit/save) components for plugin data and tool responses
- **Current**: All renderers are read-only JSON display
- **Impact**: Cannot implement domain-specific curation UI (e.g., retrieval reference selection)
- **Effort**: 1-2 days

### ❌ RAG Compatibility Pack (FR-014)
- **Status**: 30% (data model exists, plugin framework missing)
- **What's missing**: Plugin-owned data persistence, retrieval adapter contract, retrieval review component
- **Current**: References exist but no framework to move them to plugin model
- **Impact**: Cannot prove generic architecture works without hidden RAG assumptions
- **Effort**: 2-3 days (+ FR-011, FR-012, FR-025)

### ❌ Plugin Documentation (FR-021)
- **Status**: 0% implemented
- **What's missing**: No guides, no extension point inventory, no examples
- **Impact**: Plugin authors have no guidance
- **Effort**: 2-3 days

### ⚠️ Explorer Extensibility (FR-016)
- **Status**: 60% (core works, no plugins)
- **Missing**: registries to add custom columns/filters
- **Effort**: 1 day

### ⚠️ Stats Extensibility (FR-018)
- **Status**: 40% (basic stats, no plugins)
- **Missing**: registry to add custom metric cards
- **Effort**: 1 day

### ⚠️ Context/ExpectedTools Editing (FR-009, FR-008 UI)
- **Status**: 0% UI (data model exists)
- **Missing**: ContextEntryEditor, ExpectedToolsEditor components
- **Effort**: 1-2 days

---

## Where to Start (For Next Developer)

### To Add Field Component Registry (FR-011):
1. Create `frontend/src/types/fieldComponent.ts` — define component interfaces
2. Create `frontend/src/components/core/fieldComponentRegistry.ts` — implement registry
3. Modify `frontend/src/components/app/TracePanel.tsx` — integrate registry into rendering
4. Write unit tests for registry lookup and fallback

### To Add Plugin Pack Model (FR-012):
1. Create `frontend/src/types/plugin.ts` — define PluginPack interface
2. Create `frontend/src/components/core/pluginRegistry.ts` — plugin initialization
3. Create `frontend/src/config/plugins.ts` — plugin loading config
4. Modify `frontend/src/main.tsx` — add startup validation
5. Write tests for startup validation and error reporting

### To Add RAG Compatibility Pack (FR-014):
1. Implement FR-011 (field registry) — needed for custom retrieval component
2. Implement FR-012 (plugin model) — needed for plugin initialization
3. Create `frontend/src/plugins/rag/index.ts` — RAG plugin entry point
4. Create `frontend/src/plugins/rag/retrievalReviewComponent.tsx` — custom retrieval UI
5. Create `frontend/src/types/retrievalAdapter.ts` — normalized candidate contract
6. Modify `frontend/src/hooks/useGroundTruth.ts` — plugin-owned data persistence
7. Write integration tests proving RAG works as pure plugin

---

## Files to Read First

1. **`FRONTEND_REDESIGN_ANALYSIS.md`** — Comprehensive gap analysis (this workspace)
2. **`FRONTEND_GAPS_SUMMARY.txt`** — Executive summary with roadmap
3. **`docs/prds/agentic-curation-redesign.md`** — PRD specification (source of truth)
4. **`wireframes/agent-curation-wireframe-v2.2.html`** — Wireframe reference
5. **`wireframes/gt_schema_v5_generic.py`** — Generic schema definition

---

## Code Patterns to Follow

### Adding a New Field Component Type
```typescript
// frontend/src/components/core/fieldComponentRegistry.ts
export interface FieldComponentRegistry {
  registerMyCustomComponent(discriminator: string, component: React.ComponentType<MyComponentProps>): void;
  resolveMyCustomComponent(discriminator: string): React.ComponentType<MyComponentProps> | null;
}

// In TracePanel or other display component:
const ResolvedComponent = registry.resolveMyCustomComponent(discriminator);
if (ResolvedComponent) {
  return <ResolvedComponent data={data} />;
} else {
  return <DefaultComponent data={data} />; // fallback
}
```

### Adding a Plugin
```typescript
// frontend/src/plugins/my-domain/index.ts
export const myDomainPlugin: PluginPack = {
  name: "my-domain",
  version: "1.0.0",
  registerComponents(registry: FieldComponentRegistry): void {
    registry.registerMetadataComponent("my:signal", MySignalComponent);
    registry.registerToolResponseComponent("my_tool", MyToolReviewComponent);
  },
  registerApprovalRules(gate: ApprovalGate): void {
    gate.addRule((item) => ({
      valid: checkMyDomainConstraint(item),
      error: "Custom error message"
    }));
  }
};
```

---

## Testing Checklist

- [ ] No unit tests exist for agentic workflow
- [ ] No component tests for TracePanel
- [ ] No integration tests for approval workflows
- [ ] No E2E tests for plugin-contributed features
- [ ] Needs ~500 lines of test code to reach 80% coverage

---

## Links to Key PRD Sections

| Requirement | Section | Status |
|-------------|---------|--------|
| Generic core | FR-001, FR-002 | 70% ✅ |
| Workspace shell | FR-004 | 95% ✅ |
| Queue & explorer | FR-005, FR-016 | 100%/60% ✅⚠️ |
| Conversation editing | FR-006 | 100% ✅ |
| Tool calls review | FR-007 | 85% ✅ |
| Tool decisions | FR-008 | 80% ✅ |
| Evidence panels | FR-010 | 85% ✅ |
| **Field registry** | **FR-011** | **0% ❌** |
| **Plugin model** | **FR-012** | **0% ❌** |
| Approval workflow | FR-013 | 90% ✅ |
| **RAG compatibility** | **FR-014** | **30% ⚠️** |
| Approval rules | FR-013, plugin extension | 0% ❌ |
| Explorer extensibility | FR-016 | 60% ⚠️ |
| Stats extensibility | FR-018 | 40% ⚠️ |
| Lifecycle actions | FR-019 | 100% ✅ |
| **Startup validation** | **FR-022** | **0% ❌** |
| **Plugin docs** | **FR-021** | **0% ❌** |

---

## Quick Commands

```bash
# Find all uses of agentic schema fields
grep -r "toolCalls\|expectedTools\|contextEntries\|feedback\|metadata\|plugins\|tracePayload" frontend/src --include="*.tsx" --include="*.ts"

# Find TracePanel rendering code
grep -n "export default\|function.*Trace" frontend/src/components/app/TracePanel.tsx

# Check for plugin/registry references (should be empty)
grep -r "pluginRegistry\|fieldComponentRegistry\|PluginPack" frontend/src --include="*.ts*"

# Find all validators
grep -r "validate\|Validation" frontend/src/models --include="*.ts"

# Check API adapter
head -150 frontend/src/adapters/apiMapper.ts | tail -50
```

---

## Reference Materials in Workspace

- **`docs/prds/agentic-curation-redesign.md`** (340 lines) — Full PRD (version 0.6, status Draft)
- **`wireframes/agent-curation-wireframe-v2.2.html`** — UX wireframe (primary reference)
- **`wireframes/gt_schema_v5_generic.py`** — Generic schema (primary reference)
- **`wireframes/AGENTIC_REQUIREMENTS.md`** — Supporting requirements
- **`frontend/plans/` (11 files)** — Implementation plans (e.g., multi-turn-curation-plan.md)
- **`FRONTEND_REDESIGN_ANALYSIS.md`** (612 lines) — This workspace's detailed analysis
- **`FRONTEND_GAPS_SUMMARY.txt`** (430 lines) — Executive summary with roadmap

---

**Last Updated**: 2026-03-12  
**Analysis Scope**: frontend/src vs docs/prds/agentic-curation-redesign.md (v0.6)  
**Overall Completion**: ~60% (Foundation 70% + Extensibility 0%)
