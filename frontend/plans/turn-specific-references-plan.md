# Plan: Turn-Specific Reference Display in Multi-Turn Curation

## Problem Statement

Currently, all references from every agent turn in a multi-turn conversation are aggregated and displayed together in the References panel. This creates several issues:

1. **Loss of Context**: When viewing references, it's unclear which agent turn generated which reference
2. **Cognitive Overload**: Long conversations accumulate many references, making the list unwieldy
3. **Poor UX**: Users cannot easily see which references supported a specific agent response
4. **Difficult Editing**: When regenerating a specific agent turn, all references remain visible rather than just the relevant ones

## Proposed Solution

Display references **locally** to each agent turn instead of globally. Add a **paperclip icon with reference count** button on each agent turn card that opens a popover/modal/panel showing only the references for that specific turn.

### User Experience Flow

1. User views conversation in the multi-turn editor
2. Each agent turn shows a paperclip icon badge (e.g., "📎 3" for 3 references)
3. Clicking the badge opens a view showing only references for that turn
4. User can mark relevance, edit key paragraphs, and manage references per-turn
5. References without a `turnIndex` (global) can appear in a separate section or on all turns

## Current Implementation Analysis

### Data Model (Already Supports This)

The `Reference` type already includes `turnIndex?: number` field:

```typescript
export type Reference = {
	id: string;
	title?: string;
	url: string;
	snippet?: string;
	visitedAt?: string | null;
	keyParagraph?: string;
	selected?: boolean;
	bonus?: boolean;
	relevance?: ReferenceRelevance;
	turnIndex?: number; // ✅ Already exists!
};
```

**Current behavior:**
- Agent turn generation (`appendAgentTurn`, `regenerateAgentTurn`) already assigns `turnIndex` to new references
- Backend API returns references with metadata that gets mapped to `turnIndex`
- Export logic (`expandMultiTurnForExport`) already filters references by turn

**Gap:** The UI displays all references together in `SelectedTab.tsx`, ignoring the `turnIndex` grouping.

### Current Reference Display Flow

**Location:** `GroundTruthCurator/frontend/src/components/app/ReferencesPanel/SelectedTab.tsx`

**Current behavior:**
1. Receives all `references: Reference[]` from parent
2. Maps over entire array, showing each reference in a card
3. Shows `Turn #{r.turnIndex + 1}` badge on each reference (only if `turnIndex` is defined)
4. No filtering or grouping by turn

**Location:** `GroundTruthCurator/frontend/src/components/app/ReferencesPanel/ReferencesTabs.tsx`

Manages tab switching between "Search" and "Selected". Currently shows all selected references together.

**Location:** `GroundTruthCurator/frontend/src/components/app/editor/ConversationTurn.tsx`

Each turn card currently shows:
- Role badge (User/Agent)
- Turn number
- Content (editable)
- Edit, Regenerate (agent only), Delete buttons
- Loading spinner during generation

**Gap:** No reference indicator or reference count displayed on turn cards.

### Current Reference Assignment Logic

**Location:** `GroundTruthCurator/frontend/src/hooks/useGroundTruth.ts`

#### When adding a new agent turn (`appendAgentTurn`):
```typescript
const newTurnIndex = history.length;
// ... calls agent API ...
// Filter out any previous refs at this index
const filteredRefs = (prev.references || []).filter(
	(ref) => ref.turnIndex !== newTurnIndex,
);
// Add new refs with turnIndex
const mappedRefs = chatReferencesToGroundTruth(references, newTurnIndex);
return {
	...prev,
	references: [...filteredRefs, ...mappedRefs],
};
```

#### When regenerating an agent turn (`regenerateAgentTurn`):
```typescript
const filteredRefs = (prev.references || []).filter(
	(ref) => ref.turnIndex !== turnIndex,
);
const mappedRefs = chatReferencesToGroundTruth(references, turnIndex);
return {
	...prev,
	references: [...filteredRefs, ...mappedRefs],
};
```

**Key insight:** References are already scoped to turns in the data model. The UI just needs to respect this.

## Required Changes

### 1. Add Reference Indicator to Turn Cards

**File:** `src/components/app/editor/ConversationTurn.tsx`

**Changes:**
- Add prop: `referenceCount?: number`
- Display paperclip icon with count badge for agent turns
- Make badge clickable (calls new callback)
- Visual design: subtle badge in header area, next to role/turn info

**New prop signature:**
```typescript
type Props = {
	// ... existing props ...
	referenceCount?: number;
	onViewReferences?: () => void;
};
```

**UI mockup location:** In the turn card header, after "Turn #{index}"
```
┌─────────────────────────────────────────────┐
│ 🟣 Agent  Turn #2  📎 3 references  [Edit] │
│                                              │
│ The agent's response content here...        │
└─────────────────────────────────────────────┘
```

### 2. Create Turn-Specific References Modal/Panel

**New file:** `src/components/app/editor/TurnReferencesModal.tsx` (or `TurnReferencesPanel.tsx`)

**Purpose:** Show references scoped to a specific turn

**Props:**
```typescript
type Props = {
	isOpen: boolean;
	onClose: () => void;
	turnIndex: number;
	references: Reference[];
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (ref: Reference) => void;
};
```

**Features:**
- Filter `references` array to show only those with `ref.turnIndex === turnIndex`
- Reuse existing reference card UI from `SelectedTab.tsx`
- Show count in modal header
- Allow all existing reference operations (relevance, key paragraph, visit, delete)

**Design Options:**

**Option A: Modal** (Recommended)
- Overlay modal with backdrop
- Can be large enough to show full reference details
- Familiar pattern (like inspect modal)
- Easy to implement with existing modal patterns

**Option B: Inline Expansion**
- Turn card expands to show references below
- Keeps context visible
- Requires more complex layout management
- Could get cramped with many references

**Option C: Side Panel**
- Slide-in panel from right
- Could replace or overlay the existing References panel
- More complex state management

**Recommendation:** Start with **Option A (Modal)** for simplicity.

### 3. Update MultiTurnEditor to Pass Reference Counts

**File:** `src/components/app/editor/MultiTurnEditor.tsx`

**Changes:**
- Calculate reference count per turn
- Pass counts to `ConversationTurnComponent`
- Manage modal open/close state
- Render `TurnReferencesModal` component

**New state:**
```typescript
const [viewingReferencesForTurn, setViewingReferencesForTurn] = useState<number | null>(null);
```

**Helper function to add:**
```typescript
function getReferencesForTurn(turnIndex: number, allRefs: Reference[]): Reference[] {
	return allRefs.filter(ref => ref.turnIndex === turnIndex);
}

function getReferenceCountForTurn(turnIndex: number, allRefs: Reference[]): number {
	return allRefs.filter(ref => ref.turnIndex === turnIndex).length;
}
```

**Updated render:**
```tsx
history.map((turn, index) => (
	<ConversationTurnComponent
		key={`${turn.role}-${index}`}
		turn={turn}
		index={index}
		referenceCount={turn.role === 'agent' ? getReferenceCountForTurn(index, references) : undefined}
		onViewReferences={turn.role === 'agent' ? () => setViewingReferencesForTurn(index) : undefined}
		// ... other props ...
	/>
))
```

### 4. Optional: Update Global References Panel

**File:** `src/components/app/ReferencesPanel/SelectedTab.tsx`

**Options:**

**Option 1: Hide in Multi-Turn Mode** (Recommended initially)
- When in multi-turn mode, don't show the global references tab
- All reference management happens per-turn
- Simplifies UX and removes confusion

**Option 2: Show Only Global References**
- Filter to show only references without `turnIndex`
- Useful for references manually added by curator
- Rename tab to "Global References"

**Option 3: Group References by Turn**
- Keep existing panel but add grouping
- Show expandable sections per turn
- More complex but preserves existing workflow

**Recommendation:** Start with **Option 1** - hide/disable the Selected tab in multi-turn mode. Add a note that references are managed per-turn.

### 5. Update Reference Management Logic

**File:** `src/components/app/pages/CuratePane.tsx` or parent component

**Current:** Parent passes all references to `SelectedTab`

**Change Needed:**
- Pass references and handlers to `MultiTurnEditor` instead
- Let `MultiTurnEditor` own reference display for multi-turn items
- Keep existing flow for single-turn items

### 6. Update Search Tab for Turn Assignment

**File:** `src/components/app/ReferencesPanel/SearchTab.tsx`

**New behavior in multi-turn mode:**
- When user clicks "Add Selected" from search results, show turn selection dialog
- Present list of agent turns (e.g., "Turn #2: Can you explain...", "Turn #4: What about...")
- Include option for "Global (not specific to any turn)"
- After selection, assign `turnIndex` to added references
- Update `onAddSelectedFromResults` to accept optional `turnIndex` parameter

**New component needed:** `TurnSelectorModal.tsx`
```typescript
type Props = {
  isOpen: boolean;
  onClose: () => void;
  agentTurns: Array<{ index: number; preview: string }>;
  onSelectTurn: (turnIndex: number | null) => void; // null = global
};
```

### 7. Handle Global/Unassigned References

**Edge Case:** References without `turnIndex` (manually added or legacy data)

**Decision:** Global references are no longer supported in multiturn contexts. All references must be assigned to a specific agent turn.

- Removed the "Global (not specific to any turn)" option from TurnSelectorModal
- Updated `expandMultiTurnForExport` to only include references with a specific turnIndex
- TurnReferencesModal no longer displays or supports global references
- Existing references without a turnIndex will be preserved but not displayed in multiturn contexts

### 8. Update Reference Relevance UI to Graded Scale

**File:** `src/components/app/ReferencesPanel/ReferenceRelevanceToggle.tsx`

**Current Implementation:**
- Three buttons: Relevant, Neutral, Irrelevant
- Stored as `relevance?: "relevant" | "irrelevant" | "neutral"`

**New Implementation:**
- Graded scale with 4 levels (0-3) + uncertain checkbox
- Stored as `relevanceScore?: 0 | 1 | 2 | 3` and `uncertain?: boolean`

**UI Design Options:**

**Option A: Radio Buttons + Checkbox** (Recommended for clarity)
```
○ 0 - Irrelevant          [not related]
○ 1 - Partially relevant  [on-topic but insufficient]  
○ 2 - Relevant           [answers the need]
○ 3 - Highly relevant    [canonical answer]

☐ Uncertain / Can't decide (exclude from training)
```

**Option B: Button Group + Checkbox**
```
[ 0 ] [ 1 ] [ 2 ] [ 3 ]  ☐ Uncertain
 ↓     ↓     ↓     ↓
Irrelevant → Highly relevant
```

**Option C: Slider + Checkbox**
```
|----•----|----|----|
0    1    2    3
☐ Uncertain
```

**Recommendation:** Option A for clarity during training data collection. Shows full descriptions to help annotators make consistent decisions.

**Data Model Changes:**

```typescript
// Update in src/models/groundTruth.ts
export type ReferenceRelevanceScore = 0 | 1 | 2 | 3;

export type Reference = {
  id: string;
  title?: string;
  url: string;
  snippet?: string;
  visitedAt?: string | null;
  keyParagraph?: string;
  selected?: boolean;
  bonus?: boolean;
  
  // Replace old relevance field with graded scale:
  relevanceScore?: ReferenceRelevanceScore; // 0-3 graded scale
  uncertain?: boolean; // Can't decide / insufficient context
  
  turnIndex?: number;
};
```

**Validation Updates:**

**File:** `src/models/gtHelpers.ts`

Update `canApproveMultiTurn()`:
```typescript
// OLD: Check all refs have relevance set
const allRefsMarked = item.references.every(
  (r) => r.relevance === "relevant" || r.relevance === "irrelevant" || r.relevance === "neutral"
);

// NEW: Check all refs have relevanceScore or are marked uncertain
const allRefsMarked = item.references.every(
  (r) => typeof r.relevanceScore === 'number' || r.uncertain === true
);

// For training quality: refs with relevanceScore >= 2 OR selected should have key paragraphs
const relevantRefs = item.references.filter(
  (r) => !r.uncertain && (r.relevanceScore >= 2 || r.selected)
);
const allHaveKeyParagraphs = relevantRefs.every(
  (r) => (r.keyParagraph?.trim().length || 0) >= 40
);
```

**Export Considerations:**

When exporting for embedding fine-tuning:
- Include `relevanceScore` for graded learning
- Exclude references where `uncertain === true`
- Use scores 2-3 as positives, 0-1 as negatives
- Score 1 provides valuable "hard negatives" for better model training

## Component Architecture

```
MultiTurnEditor (manages state)
├── ConversationTurn (x N)
│   ├── Role badge
│   ├── Content
│   ├── Reference count badge (agent only) → onClick → setViewingReferencesForTurn(index)
│   └── Action buttons
└── TurnReferencesModal (conditional)
    ├── Header: "References for Turn #X"
    ├── Reference count
    ├── Reference cards (filtered by turnIndex)
    │   ├── ReferenceRelevanceToggle
    │   ├── Key paragraph editor
    │   ├── Visit button
    │   └── Delete button
    └── Global references section (if any)
```

## Data Flow

1. **Turn Generation:** Agent API returns references → assigned `turnIndex` in `useGroundTruth.ts`
2. **Storage:** References stored in `current.references[]` with `turnIndex` field
3. **Display:** 
   - `MultiTurnEditor` calculates counts per turn
   - Passes count to each `ConversationTurn` component
   - User clicks paperclip badge
   - Modal opens showing filtered references for that turn
4. **Editing:** All existing reference operations work the same (just filtered by turn)

## Validation & Export Implications

### Current Validation
**File:** `src/models/gtHelpers.ts` - `canApproveMultiTurn()`

Currently checks:
- All references marked with relevance
- Relevant references have key paragraphs ≥40 chars
- At least one complete turn pair

**Impact:** No changes needed - validation already works on full reference array.

### Current Export
**File:** `src/models/gtHelpers.ts` - `expandMultiTurnForExport()`

Currently:
```typescript
const refsForTurn = item.references.filter(
	(r) => r.turnIndex === undefined || r.turnIndex === i,
);
```

Already filters references by turn for export. No changes needed.

## Testing Strategy

### Unit Tests

**New file:** `tests/unit/components/TurnReferencesModal.test.tsx`
- Renders filtered references for specified turn
- Shows only references with matching turnIndex
- Allows updating reference properties
- Shows global references section if any exist

**Update file:** `tests/unit/components/MultiTurnEditor.test.tsx`
- Calculates correct reference counts per turn
- Opens modal when reference badge clicked
- Passes correct references to modal

**Update file:** `tests/unit/components/ConversationTurn.test.tsx`
- Displays reference count badge for agent turns
- Calls onViewReferences when badge clicked
- Hides badge when no references

### E2E Tests

**Update file:** `tests/e2e/agent-chat-integration.spec.ts`
- Add agent turn → verify reference count badge appears
- Click reference badge → verify modal opens
- Verify only turn-specific references shown
- Set graded relevance (0-3) → verify persisted
- Mark as uncertain → verify persisted
- Verify validation requires relevanceScore or uncertain for all refs
- Regenerate turn → verify old references removed, new count updated
- Add reference via search → verify turn selector appears
- Select specific turn → verify reference assigned to that turn
- View turn modal → verify manually added reference appears

**New file:** `tests/e2e/graded-relevance.spec.ts`
- Test all 4 relevance levels (0-3) selection and persistence
- Test uncertain checkbox functionality
- Test validation with graded scale
- Test export filtering (exclude uncertain refs)
- Test that relevance 2-3 requires key paragraphs

## Implementation Phases

### Phase 1: Core Display (MVP)
1. Add reference count badge to `ConversationTurn.tsx`
2. Create basic `TurnReferencesModal.tsx` with filtering
3. Wire up modal open/close in `MultiTurnEditor.tsx`
4. Hide global "Selected" tab in multi-turn mode

**Deliverable:** User can see reference counts per turn and view them in a modal

### Phase 2: Full Functionality
1. Implement graded relevance scale (0-3 + uncertain)
2. Create `GradedRelevanceSelector.tsx` component
3. Add turn selection when adding references via search
4. Create `TurnSelectorModal.tsx` component
5. Update data model and validation for graded relevance
6. Implement migration from old relevance values
7. Handle global/unassigned references display
8. Add visual polish (icons, animations, empty states)
9. Update tests for new relevance system

**Deliverable:** Full feature parity with current reference management, scoped per turn, with improved relevance labeling for embedding fine-tuning

### Phase 3: Enhancements (Future)
1. Inline expansion option as alternative to modal
2. Reference preview on hover over badge
3. Bulk operations per turn
4. Reference comparison between turns

## Breaking Changes & Migration

### Data Model
**No breaking changes** - `turnIndex` field already exists and is optional.

### API
**No changes needed** - backend already supports `turnIndex` field.

### User Workflows
**Behavioral change:**
- Old: All references in one global list
- New: References organized per turn
- Migration: No data migration needed, just UI change

**Backward Compatibility:**
- Single-turn mode: Works exactly as before
- Multi-turn without references: No change
- Multi-turn with references: New UI, same data

## Alternative Approaches Considered

### 1. Keep Global View, Add Turn Filter
**Pros:** Less code change, familiar UI
**Cons:** Still cluttered, doesn't solve core UX problem

### 2. Show References Inline Under Each Turn
**Pros:** Always visible, good context
**Cons:** Very long scrolling, complex layout, hard to edit

### 3. Dedicated References Column
**Pros:** Desktop-optimized, always visible
**Cons:** Complex layout, mobile unfriendly, space constraints

### 4. Tabbed View Per Turn
**Pros:** Organized, can show lots of detail
**Cons:** Adds navigation complexity, hidden until clicked

**Selected Approach:** Modal on demand (combines visibility via badge + detail on click)

## UI/UX Considerations

### Visual Design
- **Paperclip icon:** Universally recognized for attachments
- **Count badge:** Clear numeric indicator
- **Color coding:** Match agent turn color (violet) for consistency
- **Empty state:** Show "No references" when count is 0 (but probably hide badge entirely)

### Interaction Patterns
- **Click badge:** Open modal (primary action)
- **Hover badge:** Optional tooltip showing reference titles
- **Keyboard:** Support ESC to close modal, Enter to open when focused

### Accessibility
- Add `aria-label` to badge button
- Ensure modal has proper focus management
- Support keyboard navigation within modal
- Screen reader announcements for reference counts

## Performance Considerations

### Filtering Performance
With typical conversation sizes (5-10 turns, 3-5 refs each):
- Filtering is O(n) where n = total references (~50 max)
- No performance concerns

### State Management
- Reference counts should be memoized to avoid recalculation
- Use `useMemo` for filtered reference arrays

```typescript
const referenceCounts = useMemo(() => {
	const counts = new Map<number, number>();
	references.forEach(ref => {
		if (typeof ref.turnIndex === 'number') {
			counts.set(ref.turnIndex, (counts.get(ref.turnIndex) || 0) + 1);
		}
	});
	return counts;
}, [references]);
```

## Decisions Made

1. **What to do with references added via Search tab in multi-turn mode?**
   - **DECISION: Option B - Prompt user to select which turn**
   - When adding references via search in multi-turn mode, show a dropdown/picker to select which agent turn to assign the reference to
   - This ensures explicit, correct assignment
   - UI: After clicking "Add Selected" in search tab, show modal: "Assign to which turn?" with list of agent turns

2. **Should we allow moving references between turns?**
   - **DECISION: Option B - No, references are immutable per turn (for MVP)**
   - References stay with the turn they were assigned to
   - If users need to reassign, they can delete and re-add via search, or regenerate the turn
   - Can reconsider in Phase 2 based on user feedback

3. **Should reference count include ALL references or just selected/visible?**
   - **DECISION: Show all references in count**
   - Badge shows total count: "📎 3"
   - Inside modal, show breakdown of selected/relevant status
   - Simple, clear indicator of how many references exist for the turn

4. **Relevance Labeling System**
   - **DECISION: Use graded relevance scale (0-3) + uncertain flag**
   - Replace current relevant/irrelevant/neutral buttons with graded scale
   - Labels for training:
     - **0 = Irrelevant** - Not related to the question
     - **1 = Partially relevant** - On-topic but doesn't answer the need (hard negatives)
     - **2 = Relevant** - Answers the need (acceptable positive)
     - **3 = Highly relevant** - Canonical/gold standard positive
   - Separate flag: **uncertain** (annotator can't decide) → excluded from training
   - Skip "neutral" entirely - use the graded scale for better embedding fine-tuning

## Success Metrics

After implementation, success would mean:

1. **User Feedback:** Curators find it easier to understand which references support which responses
2. **Reduced Errors:** Fewer cases of marking irrelevant references as relevant
3. **Faster Curation:** Time to curate multi-turn conversations decreases
4. **Clear Mental Model:** Users understand turn-scoped references without training

## File Checklist

### New Files
- [ ] `src/components/app/editor/TurnReferencesModal.tsx` - Modal showing references for a specific turn
- [ ] `src/components/app/editor/TurnSelectorModal.tsx` - Modal for selecting which turn to assign references to
- [ ] `src/components/app/editor/GradedRelevanceSelector.tsx` - New graded relevance UI (0-3 + uncertain)
- [ ] `tests/unit/components/TurnReferencesModal.test.tsx`
- [ ] `tests/unit/components/TurnSelectorModal.test.tsx`
- [ ] `tests/unit/components/GradedRelevanceSelector.test.tsx`

### Modified Files
- [ ] `src/models/groundTruth.ts` - Add `ReferenceRelevanceScore` type, update `Reference` type
- [ ] `src/models/gtHelpers.ts` - Update validation for graded relevance
- [ ] `src/components/app/editor/ConversationTurn.tsx` - Add reference count badge
- [ ] `src/components/app/editor/MultiTurnEditor.tsx` - Manage turn references modal
- [ ] `src/components/app/ReferencesPanel/ReferenceRelevanceToggle.tsx` - Replace with graded scale
- [ ] `src/components/app/ReferencesPanel/SearchTab.tsx` - Add turn selection when adding references
- [ ] `src/components/app/ReferencesPanel/ReferencesTabs.tsx` - Hide Selected tab in multi-turn mode
- [ ] `src/components/app/ReferencesPanel/SelectedTab.tsx` - Use new graded relevance selector
- [ ] `src/hooks/useReferencesEditor.ts` - Update for graded relevance + turnIndex
- [ ] `tests/unit/components/MultiTurnEditor.test.tsx`
- [ ] `tests/unit/components/ConversationTurn.test.tsx`
- [ ] `tests/e2e/agent-chat-integration.spec.ts`

### Documentation Updates
- [ ] `IMPLEMENTATION_SUMMARY.md` - Add section about turn-specific references and graded relevance
- [ ] `README.md` - Update screenshots/description if needed

## Implementation Estimate

**Phase 1 (MVP):** 8-12 hours
- Component creation: 3-4 hours
- Wiring and state management: 2-3 hours
- Basic styling: 2-3 hours
- Manual testing: 1-2 hours

**Phase 2 (Full):** 10-14 hours
- Turn selector modal component: 2-3 hours
- Graded relevance selector component: 2-3 hours
- Search tab turn assignment integration: 2-3 hours
- Update validation and migration logic: 1-2 hours
- Global references handling: 1-2 hours
- Polish and edge cases: 2-3 hours
- Testing: 2-3 hours

**Phase 3 (Enhancements):** TBD based on user feedback

**Total for MVP + Full:** 18-26 hours

## Next Steps

1. Review this plan with team/stakeholders
2. Get design approval for modal vs inline vs panel approach
3. Create design mockup for reference badge and modal
4. Implement Phase 1 (MVP)
5. Get user feedback
6. Iterate to Phase 2
