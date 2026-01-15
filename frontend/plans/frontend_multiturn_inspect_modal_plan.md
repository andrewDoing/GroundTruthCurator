# Frontend Multi-Turn Inspect Modal Plan

## Overview

Update the InspectItemModal to support multi-turn conversations by reusing the MultiTurnEditor component in read-only mode. Currently, the inspect modal only shows the final answer from the last turn, missing the full conversation history. We need to display the complete multi-turn conversation while ensuring all editing capabilities are disabled for inspection-only use.

## Problem Statement

- InspectItemModal.tsx currently displays only single-turn view (question/answer format)
- Multi-turn conversations show only the last turn's answer, losing conversation context
- No way to view the full conversation flow in inspection mode
- References are shown globally but not associated with specific turns

## Solution Approach

Reuse MultiTurnEditor component with read-only mode by:
1. Adding `readOnly` prop to MultiTurnEditor component
2. Hiding all editing controls when `readOnly=true`
3. Updating InspectItemModal to detect multi-turn items and use MultiTurnEditor in read-only mode
4. Providing no-op handlers for all editing operations

## Files to Modify

### 1. `src/components/app/editor/MultiTurnEditor.tsx` (MODIFY)
- **Purpose**: Add read-only mode support to existing MultiTurnEditor
- **Key Functions**:
  - Add `readOnly?: boolean` prop to Props interface
  - `renderAddTurnButtons()`: Only render when `!readOnly`
  - `renderManageTagsButton()`: Only render when `!readOnly`
  - Pass `canEdit={!readOnly}` to ConversationTurnComponents

### 2. `src/components/modals/InspectItemModal.tsx` (MODIFY)
- **Purpose**: Replace entire content section with MultiTurnEditor in read-only mode
- **Key Functions**:
  - Remove all existing Q&A display logic
  - Use MultiTurnEditor for ALL items (single-turn items are auto-converted to multi-turn format)
  - Keep metadata display (ID, status, dataset, etc.)

### 3. `src/components/app/editor/TurnReferencesModal.tsx` (VERIFY)
- **Purpose**: Ensure references modal works properly in read-only mode
- **Key Functions**:
  - Verify editing controls are hidden when used from read-only MultiTurnEditor
  - Ensure reference viewing (but not editing) works properly

## Detailed Implementation

### Step 1: Add Read-Only Mode to MultiTurnEditor

**File:** `src/components/app/editor/MultiTurnEditor.tsx`

```typescript
type Props = {
  current: GroundTruthItem | null;
  readOnly?: boolean; // NEW PROP
  onUpdateHistory: (history: ConversationTurn[]) => void;
  onDeleteTurn: (messageIndex: number) => void;
  onGenerate: (messageIndex: number) => Promise<AgentGenerationResult>;
  canEdit: boolean;
  // ... other props
};

// Key changes:
- Add readOnly prop with default false
- Conditional rendering of Add Turn buttons: {!readOnly && canEdit && (...)}
- Conditional rendering of Manage Tags button: {!readOnly && canEdit && (...)}
- Pass canEdit={canEdit && !readOnly} to ConversationTurnComponents
```

**Key Features:**
- Reuses ALL existing conversation display logic
- Inherits reference counting, pattern validation, turn organization
- Disables editing when `readOnly=true`
- No code duplication - single source of truth for conversation display

### Step 2: Update InspectItemModal

**File:** `src/components/modals/InspectItemModal.tsx`

```typescript
// Simplified approach - NO detection logic needed:
- Remove all existing Q&A display sections (question, answer, references)
- Use MultiTurnEditor with readOnly={true} for ALL items
- Single-turn items already converted to multi-turn format by mapGroundTruthFromApi

// No-op handlers for MultiTurnEditor:
- onUpdateHistory={() => {}}
- onDeleteTurn={() => {}}  
- onGenerate={() => Promise.resolve({ ok: false })}
- onUpdateReference={() => {}}
- onRemoveReference={() => {}}
- onUpdateTags={() => {}}
```

**Logic Flow:**
1. Keep metadata display (ID, status, dataset, bucket, tags, reviewedAt)
2. Replace content section with MultiTurnEditor in read-only mode
3. ALL items work - no need for single vs multi-turn detection

### Step 3: Verify Reference Modal Read-Only Behavior

**File:** `src/components/app/editor/TurnReferencesModal.tsx`

Ensure the references modal works properly when called from read-only MultiTurnEditor:
- Reference viewing should work (onOpenReference)
- Reference editing should be disabled
- Adding new references should be disabled

## UI/UX Considerations

### Layout Changes
- **Modal Size**: Increase max width to accommodate conversation flow
- **Header**: Update title to indicate "Multi-Turn" vs "Single-Turn" inspection
- **Content Area**: Use flex layout to accommodate variable conversation length
- **Metadata**: Show at top (ID, status, dataset) and bottom (tags, timestamps)

### Visual Indicators
- **Read-Only Badge**: Clear indication this is inspection mode
- **Turn Numbers**: Show conversation turn progression
- **Reference Association**: Clear visual linking of references to specific agent turns
- **Pattern Validation**: Show conversation flow validation status

## Testing Strategy

### Unit Tests
1. **MultiTurnEditor.test.tsx** (UPDATE):
   - Renders in read-only mode correctly
   - Hides editing controls when `readOnly=true`
   - Shows conversation history and validation
   - Reference viewing works in read-only mode

2. **InspectItemModal.test.tsx** (UPDATE):
   - Detects single-turn vs multi-turn items correctly
   - Renders appropriate view mode (single-turn Q&A vs MultiTurnEditor)
   - Displays all metadata correctly
   - MultiTurnEditor integration works in read-only mode

### E2E Tests
1. **inspect-multiturn-modal.spec.ts** (NEW):
   - Open inspect modal for multi-turn item
   - Verify full conversation history visible
   - Verify no edit buttons present
   - Verify reference counts per turn
   - Verify pattern validation display

2. **inspect-singleturn-modal.spec.ts** (UPDATE existing):
   - Ensure single-turn items still work correctly
   - Verify backwards compatibility

## Implementation Notes

### Reusability Strategy
- Reuse MultiTurnEditor component entirely with read-only mode
- Single source of truth for conversation display logic
- No code duplication - all improvements to MultiTurnEditor automatically benefit inspection

### Backwards Compatibility
- Single-turn items continue to use existing Q&A display
- No changes to existing single-turn item behavior
- Graceful fallback if conversation history is malformed

### Performance Considerations
- Lazy load ReadOnlyMultiTurnViewer only when needed
- Minimize re-renders in read-only mode
- Efficient reference counting for large conversations

## Key Design Decisions

1. **Component Reuse**: Reuse MultiTurnEditor component entirely with `readOnly` prop rather than creating new components
2. **Modal Adaptation**: Update existing InspectItemModal rather than creating new modal
3. **Detection Logic**: Use presence of `item.history` array to determine display mode
4. **Reference Handling**: Maintain existing reference opening behavior but disable editing via read-only mode
5. **Validation Display**: Show conversation pattern validation for educational value
6. **Handler Strategy**: Provide no-op handlers to MultiTurnEditor in read-only mode

## Migration Strategy

1. **Phase 1**: Add `readOnly` prop to MultiTurnEditor component
2. **Phase 2**: Update InspectItemModal with detection logic and MultiTurnEditor integration
3. **Phase 3**: Verify reference modal behavior in read-only mode
4. **Phase 4**: Add comprehensive testing for read-only MultiTurnEditor
5. **Phase 5**: Update documentation and user guides

This approach ensures we maintain the existing single-turn inspection experience while adding comprehensive multi-turn support with clear read-only constraints.