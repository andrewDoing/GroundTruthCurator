# Plan: Integrate Agent Chat API with Multi-Turn UI

## Overview
Connect the existing multi-turn conversation UI to the backend `/v1/chat` agent endpoint. When users click "Add Agent Turn" or "Regenerate" on an agent turn, we need to call the agent API with the conversation history, show a loading spinner, and populate the response with content and references.

## What We Need (Right Now Only)
- Service function to call `/v1/chat` API with conversation history formatted as a message string
- Loading state management for "Add Agent Turn" and "Regenerate Agent Response" actions
- Update agent turn content with API response
- Map API references to ground truth references and attach to the specific agent turn
- Format conversation history as context for the agent (pass previous turns as message)
- Error handling with user-friendly messages when agent call fails

## Files To Add / Modify

1. `src/services/chatService.ts` (NEW) - API wrapper for calling `/v1/chat` endpoint with conversation history.
2. `src/hooks/useGroundTruth.ts` (MODIFY) - Implement `regenerateAgentTurn` function to call chat service and update turn.
3. `src/components/app/editor/MultiTurnEditor.tsx` (MODIFY) - Add loading state, call `onGenerate` when "Add Agent Turn" clicked, pass loading state to turns.
4. `src/components/app/editor/ConversationTurn.tsx` (MODIFY) - Show loading spinner on agent turns during regeneration.
5. `src/models/groundTruth.ts` (MODIFY) - Add helper to format conversation history for agent prompt (maybe).
6. `tests/e2e/agent-chat-integration.spec.ts` (NEW) - Integration tests that call real backend `/v1/chat` endpoint.

## Minimal Function Definitions

### `src/services/chatService.ts` (NEW)
- `async callAgentChat(message: string, context?: string): Promise<{ content: string; references: ChatReference[] }>` - Call `/v1/chat` endpoint using openapi-fetch client. Takes formatted message with conversation history, returns agent response and references.
- `formatConversationForAgent(turns: ConversationTurn[], upToIndex?: number): string` - Format conversation history into a message string for the agent. If `upToIndex` provided (for regenerate), only include turns before that index. Otherwise include all turns. Format as "User: ...\nAgent: ...\nUser: ..." etc.

### `src/hooks/useGroundTruth.ts` (MODIFY)
- `regenerateAgentTurn(turnIndex: number)` - Replace TODO implementation. Extract turns up to `turnIndex`, format conversation history, call `callAgentChat`, update turn content with response, convert references to ground truth format and attach to turn via `turnIndex` field.
- `handleAddAgentTurn()` - New function or modify existing add logic. Format all existing conversation history, call `callAgentChat`, append new agent turn with response content and references.

### `src/components/app/editor/MultiTurnEditor.tsx` (MODIFY)
- `handleAddAgentTurn()` - Update to set loading state, await `onGenerate(-1)` (special index for "add new"), clear loading when done.
- Add `isGenerating: boolean` state and `generatingTurnIndex: number | null` state to track which turn is loading.

### `src/components/app/editor/ConversationTurn.tsx` (MODIFY)
- Accept `isGenerating?: boolean` prop - show loading spinner overlay when true.
- Render `<LoadingSpinner />` component or simple animated icon when generating.

### `tests/e2e/agent-chat-integration.spec.ts` (NEW)

- `test("should add agent turn with real backend API call")` - Create multi-turn item, click "Add Agent Turn", wait for real backend response, verify new agent turn added with content and references.
- `test("should regenerate agent turn with correct conversation context")` - Create multi-turn conversation with 3+ turns, click regenerate on middle agent turn, verify turn content updated and references attached with correct turnIndex.
- `test("should show loading indicator during agent call")` - Click "Add Agent Turn", verify loading spinner visible, wait for response, verify spinner removed.
- `test("should handle agent API errors gracefully")` - Trigger agent error scenario (if backend supports it), verify error message shown, verify turn remains editable.
- `test("should preserve existing turns when adding agent response")` - Verify all existing user/agent turns remain unchanged when adding new agent turn at end.
- `test("should populate references in references pane after agent turn")` - Add agent turn, verify references pane shows new references from agent response, verify references are associated with correct turn (turnIndex).

## Integration Test Implementation Details

### Test Setup
- Use existing integration test infrastructure from `tests/e2e/setup/integration-helpers.ts`.
- Tests run against real backend API (not mocked routes).
- Backend must have Azure AI Foundry agent configured with valid credentials.
- Create helper functions for multi-turn test scenarios:
  - `createMultiTurnItem(page)` - Helper to set up item with existing conversation history via UI.
  - `clickAddAgentTurn(page)` - Click "Add Agent Turn" button and wait for response.
  - `clickRegenerateTurn(page, turnIndex)` - Click regenerate button on specific turn.
  - `getConversationTurns(page)` - Extract turn elements from UI for verification.
  - `waitForAgentResponse(page)` - Wait for loading spinner to disappear and response to populate.
  - `getReferencesPaneCount(page)` - Count number of references displayed in references pane.
  - `getReferencesForTurn(page, turnIndex)` - Get references associated with specific turn index.

### Test Assertions
- Verify loading spinner visibility using role-based selectors.
- Verify turn content populated in UI after agent response.
- Verify reference count increases after agent turn added.
- Verify references appear in references pane with correct content (title, URL, snippet, keyParagraph).
- Verify references are associated with correct turn via turnIndex.
- Count turns before/after operations to ensure correct additions.

### Backend Requirements
- Backend `/v1/chat` endpoint must be running and accessible.
- Azure AI Foundry agent must be configured (`GTC_AZURE_AI_PROJECT_ENDPOINT`, `GTC_AZURE_AI_AGENT_ID`).
- `GTC_CHAT_ENABLED=true` in backend configuration.
- Tests may be slow (~10-30 seconds per test) due to real agent API calls.

## Test Names & Purpose (Integration Tests with Real Backend)

- `test("should add agent turn with real backend API call")` - Click "Add Agent Turn", wait for real agent response (may take 5-15 seconds), verify turn added with content and references.
- `test("should regenerate agent turn with correct conversation context")` - Regenerate middle turn, verify updated content matches new agent response, verify only previous turns used as context.
- `test("should show loading indicator during agent call")` - Verify loading spinner appears immediately, disappears after response.
- `test("should handle agent API errors gracefully")` - Trigger error if backend allows (e.g., disable agent), verify error message, verify UI remains functional.
- `test("should preserve existing turns when adding agent response")` - Verify no existing turns modified or removed when adding new turn.

## Configuration Additions
None - uses existing `client` from `src/api/client.ts` which already has auth headers.

## Data Flow

### Add Agent Turn Flow
1. User clicks "Add Agent Turn" button (last turn is user).
2. `MultiTurnEditor` sets `isGenerating = true` and `generatingTurnIndex = history.length`.
3. Calls `onGenerate(-1)` (special sentinel for "new turn").
4. `useGroundTruth.handleAddAgentTurn()`:
   - Formats all existing turns as conversation string.
   - Calls `chatService.callAgentChat(message, context)`.
   - Receives `{ content, references }`.
   - Appends new turn: `{ role: "agent", content }`.
   - Converts `references` to `Reference[]` with `turnIndex = history.length`.
   - Merges new references into `current.references`.
   - Updates `current.history` and `current.references`.
5. `MultiTurnEditor` sets `isGenerating = false`.

### Regenerate Agent Turn Flow
1. User clicks regenerate button on agent turn at index N.
2. `ConversationTurn` sets `isGenerating = true` for that turn.
3. Calls `onRegenerate(N)`.
4. `useGroundTruth.regenerateAgentTurn(N)`:
   - Formats turns 0 to N-1 as conversation string.
   - Calls `chatService.callAgentChat(message, context)`.
   - Receives `{ content, references }`.
   - Updates `history[N].content = content`.
   - Removes old references with `turnIndex === N`.
   - Converts new `references` to `Reference[]` with `turnIndex = N`.
   - Merges into `current.references`.
   - Updates `current.history` and `current.references`.
5. `ConversationTurn` sets `isGenerating = false`.

## Conversation History Format Example

For turns:
```
[
  { role: "user", content: "What is the airspeed velocity of an unladen swallow?" },
  { role: "agent", content: "African or European swallow?" },
  { role: "user", content: "I don't know that!" }
]
```

Formatted message for agent:
```
User: What is the airspeed velocity of an unladen swallow?
Agent: African or European swallow?
User: I don't know that!
```

When regenerating turn index 1 (second turn), only include turn 0:
```
User: What is the airspeed velocity of an unladen swallow?
```

## Reference Mapping

API `ChatReference`:
```typescript
{
  id?: string | null;
  title?: string | null;
  url?: string | null;
  snippet?: string | null;
  keyParagraph?: string | null;
}
```

Convert to ground truth `Reference`:
```typescript
{
  id: chatRef.id || generateId(),
  title: chatRef.title || undefined,
  url: chatRef.url || "",
  snippet: chatRef.snippet || undefined,
  keyParagraph: chatRef.keyParagraph || undefined,
  turnIndex: N, // which agent turn these belong to
  selected: false,
  relevance: "neutral"
}
```

## Edge Cases Considered
- Agent API returns 503 (service unavailable) → show error toast, keep turn editable.
- Agent API returns 502 (agent error) → show error message, allow retry.
- Empty response content → treat as error, don't update turn.
- No references returned → valid, just don't add any references.
- Regenerate when turn is empty → still call API with conversation context.
- Add agent turn when no user turns → disabled by UI, but should handle gracefully.
- Loading state interrupted by navigation → clear loading state in cleanup.

## Simplifications (Intentional)
- No streaming - wait for full response.
- No retry logic - user can click regenerate again.
- No optimistic updates - wait for API response before updating.
- Format conversation as plain text, not structured JSON messages.
- Single global loading state per component (not per-turn granular state initially).
- Don't store raw API response - just extract content and references.

## Incremental Implementation Order
1. Create `chatService.ts` with API call and formatting functions.
2. Update `useGroundTruth.ts` to implement `regenerateAgentTurn` and add agent turn logic.
3. Add loading state to `MultiTurnEditor.tsx`.
4. Add loading spinner UI to `ConversationTurn.tsx`.
5. Create `tests/e2e/agent-chat-integration.spec.ts` with mocked API tests.
6. Manual testing and refinement.

## Implementation Status
❌ Not started

---

## Acceptance Criteria
- [ ] Clicking "Add Agent Turn" calls agent API with full conversation history and appends response.
- [ ] Loading spinner shows during agent generation.
- [ ] Clicking "Regenerate" on agent turn calls API with only previous turns and updates that turn.
- [ ] References from agent response populate in references list with correct `turnIndex`.
- [ ] Error states show user-friendly messages.
- [ ] No loading state shown after successful or failed API call.
- [ ] Integration tests pass when backend agent is properly configured (tests hit real `/v1/chat` endpoint).

---

## Future (Out of Scope Now)
- Streaming responses with SSE.
- Per-turn loading indicators (current: single global state).
- Retry with exponential backoff.
- Conversation history sent as structured messages instead of text.
- Reference deduplication across turns.
- Undo/redo for regenerated turns.
