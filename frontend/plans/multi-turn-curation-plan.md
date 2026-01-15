# Multi-Turn Ground Truth Curation Plan

## Overview
Implement multi-turn conversation support in the Ground Truth Curator to replace the current single-turn experience. This includes building UI components to display conversation history, allow adding agent/user turns, marking references as relevant/irrelevant, and storing multi-turn conversations as single ground truth entries that can be exported as multiple entries (one per turn).

Keep it SIMPLE. We need an initial working version. Focus on the immediate MVP needs without over-engineering.

## Data Model Changes

### File: `/src/models/groundTruth.ts`

**Add new types:**

```typescript
export type ConversationTurn = {
	role: "user" | "agent";
	content: string;
};

export type ReferenceRelevance = "relevant" | "irrelevant" | "neutral";

export type Reference = {
	id: string;
	title?: string;
	url: string;
	snippet?: string;
	visitedAt?: string | null;
	keyParagraph?: string;
	selected?: boolean;
	bonus?: boolean;
	relevance?: ReferenceRelevance; // NEW: track relevance
	// Associated with a specific turn index (optional)
	turnIndex?: number; // NEW: which agent turn these refs belong to
};

export type GroundTruthItem = {
	id: string;
	question: string; // Keep for backward compat; represents last user turn
	answer: string; // Keep for backward compat; represents last agent turn
	history?: ConversationTurn[]; // NEW: full conversation history
	references: Reference[];
	status: "draft" | "approved" | "skipped";
	providerId: string;
	deleted?: boolean;
	tags?: string[];
	comment?: string;
	datasetName?: string;
	bucket?: string;
	curationInstructions?: string;
	context?: string; // NEW: app context from client
};
```

**Function: `getLastUserTurn(item: GroundTruthItem): string`**
Returns the last user message from history, or falls back to `item.question` for backward compatibility.

**Function: `getLastAgentTurn(item: GroundTruthItem): string`**
Returns the last agent message from history, or falls back to `item.answer` for backward compatibility.

**Function: `getTurnCount(item: GroundTruthItem): number`**
Returns the total number of turns in the conversation (history length).

## Component Architecture

### 1. Component: `MultiTurnEditor` (NEW)
**File:** `/src/components/app/editor/MultiTurnEditor.tsx`

**Purpose:** Main container for multi-turn conversation editing. Replaces the separate Question/Answer editors with a conversation timeline view.

**Props:**
- `current: GroundTruthItem | null`
- `onUpdateHistory: (history: ConversationTurn[]) => void`
- `onUpdateContext: (context: string) => void`
- `onGenerate: (turnIndex: number) => void` - regenerate specific agent turn
- `canEdit: boolean`

**Key functions:**
- `renderTurnItem(turn: ConversationTurn, index: number)` - Renders a single turn with role indicator and editable content.
- `handleAddUserTurn()` - Adds a new user turn to the conversation.
- `handleAddAgentTurn()` - Adds a new agent turn to the conversation.
- `handleUpdateTurn(index: number, content: string)` - Updates the content of a specific turn.
- `handleRemoveTurn(index: number)` - Removes a turn from the conversation (with confirmation).

**UI Structure:**
- Timeline/thread view showing alternating user/agent messages
- Each turn has an edit button, regenerate button (for agent), delete button
- "Add User Turn" and "Add Agent Turn" buttons at bottom
- Optional context field at top (collapsible)

---

### 2. Component: `ConversationTurn` (NEW)
**File:** `/src/components/app/editor/ConversationTurn.tsx`

**Purpose:** Displays and edits a single turn in the conversation.

**Props:**
- `turn: ConversationTurn`
- `index: number`
- `isLast: boolean`
- `onUpdate: (content: string) => void`
- `onDelete: () => void`
- `onRegenerate?: () => void` - only for agent turns

**Key functions:**
- `toggleEditMode()` - Switch between view and edit mode.
- `handleSave()` - Save changes and exit edit mode.

**UI Structure:**
- Role badge (User/Agent) with distinct colors
- Content display (markdown-rendered in view mode, textarea in edit mode)
- Action buttons (Edit, Delete, Regenerate for agent)
- Turn number indicator

---

### 3. Component: `ReferenceRelevanceToggle` (NEW)
**File:** `/src/components/app/ReferencesPanel/ReferenceRelevanceToggle.tsx`

**Purpose:** Toggle button group for marking references as relevant/irrelevant.

**Props:**
- `relevance: ReferenceRelevance`
- `onChange: (relevance: ReferenceRelevance) => void`
- `disabled?: boolean`

**Key functions:**
- `handleToggle(newRelevance: ReferenceRelevance)` - Updates the relevance state.

**UI Structure:**
- Two-button toggle: "Relevant" (green when selected) / "Irrelevant" (red when selected)
- Displays "Not visited" state when reference hasn't been opened
- Auto-switches to "Relevant" when user clicks "Open" on reference

---

### 4. Component: `ContextEditor` (NEW)
**File:** `/src/components/app/editor/ContextEditor.tsx`

**Purpose:** Editable field for application context (e.g., product, version, screen).

**Props:**
- `context: string`
- `onChange: (context: string) => void`

**Key functions:**
- None - simple controlled textarea component.

**UI Structure:**
- Collapsible section labeled "Application Context"
- Textarea with placeholder explaining what context might include
- Character count (optional)

---

### 5. Modified Component: `SelectedTab`
**File:** `/src/components/app/ReferencesPanel/SelectedTab.tsx`

**Changes:**
- Add `ReferenceRelevanceToggle` component to each reference item
- Update validation logic: "Use for LLM" checkbox is replaced by relevance toggle
- Show which turn the reference belongs to (if `turnIndex` is set)
- Update "To approve" message to mention relevance marking

**New function: `groupReferencesByTurn(refs: Reference[]): Map<number | undefined, Reference[]>`**
Groups references by their associated turn index for display.

---

### 6. Modified Component: `CuratePane`
**File:** `/src/components/app/pages/CuratePane.tsx`

**Changes:**
- Replace Question/Answer editors with `MultiTurnEditor`
- Add `ContextEditor` above the multi-turn editor
- Update save/approve logic to handle conversation history
- Add "Single-turn" / "Multi-turn" mode toggle at top (for gradual migration)

**New function: `syncHistoryToQuestionAnswer(history: ConversationTurn[])`**
When in multi-turn mode, syncs the last user/agent turns back to `question`/`answer` fields for backward compatibility.

---

## Hook Changes

### Modified Hook: `useGroundTruth`
**File:** `/src/hooks/useGroundTruth.ts`

**New functions:**

**`updateHistory(history: ConversationTurn[])`**
Updates the conversation history and syncs last turn to question/answer fields.

**`updateContext(context: string)`**
Updates the application context field.

**`addTurn(role: "user" | "agent", content: string)`**
Appends a new turn to the conversation history.

**`regenerateAgentTurn(turnIndex: number)`**
Calls the generation API for a specific agent turn, passing all prior history and references associated with that turn.

---

### Modified Hook: `useReferencesEditor`
**File:** `/src/hooks/useReferencesEditor.ts`

**New functions:**

**`updateReferenceRelevance(refId: string, relevance: ReferenceRelevance)`**
Updates the relevance field on a reference.

**`associateReferenceWithTurn(refId: string, turnIndex: number)`**
Associates a reference with a specific conversation turn.

---

## API/Service Changes

### Modified Service: `groundTruths.ts`
**File:** `/src/services/groundTruths.ts`

**Changes:**
- Ensure PUT/POST endpoints send `history`, `context`, and updated `references` with `relevance` field
- Validate that backend can handle these fields (may need backend schema update)

---

### Modified Service: `llm.ts`
**File:** `/src/services/llm.ts`

**New function: `generateForTurn(turnIndex: number, history: ConversationTurn[], references: Reference[])`**
Calls the generation endpoint with conversation history up to the specified turn, plus relevant references.

---

## Export Logic Changes

### Modified Function: `expandMultiTurnForExport`
**File:** `/src/services/groundTruths.ts` or new `/src/models/gtHelpers.ts`

**Purpose:** Expands a single multi-turn ground truth into multiple single-turn entries for export.

**Logic:**
1. If `history` is undefined/empty, export as single item (backward compat)
2. For each turn pair (user + agent), create a separate ground truth entry
3. Include all prior conversation context in the `history` field
4. Associate references with the appropriate turn
5. Increment ref IDs (e.g., `Q001-a`, `Q001-b`, `Q001-c`)

---

## UI Flow Updates

### Modified: Top-level mode toggle
**Location:** `CuratePane.tsx` or `HeaderBar.tsx`

**UI:** Tab switcher: "Single-turn" | "Multi-turn"
- Default to "Single-turn" for existing items without history
- Switch to "Multi-turn" when history is present or user clicks "Add turn"
- Persist mode preference in localStorage

---

## Validation Updates

### Modified: Approval validation
**File:** `/src/models/validators.ts` or inline in `CuratePane.tsx`

**New function: `canApproveMultiTurn(item: GroundTruthItem): boolean`**
Checks:
1. At least one complete conversation turn (user + agent)
2. All references marked as either relevant or irrelevant or neutral
3. All "relevant" references have key paragraphs ≥40 chars
4. No deleted status

---

## Testing Strategy

### Unit Tests

**File:** `/tests/unit/components/MultiTurnEditor.test.tsx`
- Render conversation history correctly
- Add user turn creates new turn in history
- Add agent turn creates new turn in history
- Update turn content updates history
- Delete turn removes from history
- Regenerate agent turn calls generation API

**File:** `/tests/unit/components/ReferenceRelevanceToggle.test.tsx`
- Toggle to relevant updates state
- Toggle to irrelevant updates state
- Disabled state prevents changes

**File:** `/tests/unit/hooks/useGroundTruth-multiturn.test.ts`
- updateHistory syncs last turn to question/answer
- addTurn appends correctly
- regenerateAgentTurn calls API with correct payload

**File:** `/tests/unit/models/gtHelpers-export.test.ts`
- expandMultiTurnForExport creates one entry per turn
- Single-turn items pass through unchanged
- Generated refs follow naming pattern (Q001-a, Q001-b)

---

## Migration Notes

1. **Backward Compatibility:** Keep `question` and `answer` fields. When `history` is present, these should reflect the last user/agent turn.

2. **Gradual Rollout:** Use mode toggle to allow SMEs to opt into multi-turn on a per-item basis.

3. **Data Migration:** No automatic migration needed. Existing items work as single-turn. New multi-turn items populate `history` field.

4. **Backend Coordination:** Confirm backend accepts `history: ConversationTurn[]`, `context: string`, and `references[].relevance` fields. Update API schema if needed.

---

## Files to Create

1. `/src/components/app/editor/MultiTurnEditor.tsx`
2. `/src/components/app/editor/ConversationTurn.tsx`
3. `/src/components/app/editor/ContextEditor.tsx`
4. `/src/components/app/ReferencesPanel/ReferenceRelevanceToggle.tsx`
5. `/tests/unit/components/MultiTurnEditor.test.tsx`
6. `/tests/unit/components/ReferenceRelevanceToggle.test.tsx`
7. `/tests/unit/hooks/useGroundTruth-multiturn.test.ts`
8. `/tests/unit/models/gtHelpers-export.test.ts`

---

## Files to Modify

1. `/src/models/groundTruth.ts` - Add ConversationTurn, ReferenceRelevance types; extend Reference and GroundTruthItem
2. `/src/models/gtHelpers.ts` - Add export expansion logic
3. `/src/components/app/pages/CuratePane.tsx` - Replace editors with MultiTurnEditor, add mode toggle
4. `/src/components/app/ReferencesPanel/SelectedTab.tsx` - Add relevance toggle to each reference
5. `/src/hooks/useGroundTruth.ts` - Add updateHistory, updateContext, addTurn, regenerateAgentTurn
6. `/src/hooks/useReferencesEditor.ts` - Add updateReferenceRelevance, associateReferenceWithTurn
7. `/src/services/groundTruths.ts` - Ensure new fields sent to backend
8. `/src/services/llm.ts` - Add generateForTurn function
9. `/src/models/validators.ts` - Add canApproveMultiTurn validation

---

## Implementation Order

1. **Phase 1 - Data Model** (Foundation)
   - Update `groundTruth.ts` types
   - Add helper functions in `gtHelpers.ts`
   - Write unit tests for helpers

2. **Phase 2 - Reference Relevance** (Quick Win)
   - Create `ReferenceRelevanceToggle` component
   - Update `SelectedTab` to use toggle
   - Update validation to check relevance
   - Test relevance marking flow

3. **Phase 3 - Multi-Turn Components** (Core Feature)
   - Create `ConversationTurn` component
   - Create `MultiTurnEditor` component
   - Create `ContextEditor` component
   - Write unit tests for components

4. **Phase 4 - Hook Integration** (Wire It Up)
   - Update `useGroundTruth` hook
   - Update `useReferencesEditor` hook
   - Update `llm.ts` service

5. **Phase 5 - UI Integration** (Make It Work)
   - Update `CuratePane` with mode toggle
   - Wire up all callbacks
   - Test full flow manually

6. **Phase 6 - Export Logic** (Complete Feature)
   - Implement `expandMultiTurnForExport`
   - Test export with multi-turn conversations

---

## Open Questions

1. **Backend Schema:** Does the backend already support `history`, `context`, and `relevance` fields? Need to coordinate with backend team.

2. **Reference Association:** Should references be explicitly associated with turns, or always shown globally? Design shows global list - keeping it simple for MVP.

3. **Regeneration Scope:** When regenerating a middle turn, do we regenerate all subsequent turns? For MVP, regenerate only the selected turn.

4. **Mode Switching:** Can users switch from multi-turn back to single-turn? For MVP, yes, but warn about data loss (only keeps last Q/A).

5. **Tag Scope:** Are tags per-conversation or per-turn? Design suggests per-conversation (keeping existing model).
