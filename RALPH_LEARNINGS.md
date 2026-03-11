# RALPH_LEARNINGS.md

Purpose: persistent handoff notes for Ralph loop runs across fresh context windows.

## How to use

- Read this file before starting implementor or reviewer work.
- Keep notes concise, durable, and specific to this repository.
- Prefer actionable guidance: file paths, commands, pitfalls, review item IDs, and remaining risks.
- Remove or rewrite stale guidance instead of appending noisy transcripts.

## Active learnings

### Frontend role model (Phase 2)
- `ConversationTurn.role` is `string`, not `"user" | "agent"`. Always use `role !== "user"` (never `role === "agent"`) to identify non-user turns — the backend may send "assistant", "output-agent", "orchestrator-agent", etc.
- `groundTruthFromApi` maps "assistant"→"agent"; all other roles are passed through. `groundTruthToPatch` maps "agent"→"assistant"; all other roles are passed through.

### Approval logic (Phase 2)
- `canApproveMultiTurn` no longer requires `expectedBehavior` on every agent turn. Approval requires only: valid conversation pattern (user/non-user alternating, ends on non-user turn) + item not deleted. The `expectedBehavior` field is still in the model and editor UI but is not gated.

### Generic schema fields (Phase 2)
- `GroundTruthItem` now carries: `contextEntries`, `toolCalls`, `expectedTools`, `feedback`, `metadata`, `plugins`, `traceIds`, `tracePayload`, `scenarioId` — all passed through by the mapper from `AgenticGroundTruthEntry-Output` in `generated.ts`.
- `hasEvidenceData(item)` returns `true` when any of toolCalls/traceIds/metadata/feedback/tracePayload has content. `TracePanel` renders only when this is true.

### Biome lint (Frontend)
- `npm run lint` applies auto-fix (writes changes); `npm run lint:check` is the gate check (no writes, exits non-zero on error).
- Biome will skip "unsafe" fixes. `noUselessFragments` wrapping a single IIFE is marked unsafe — fix manually by rewriting JSX to use direct conditionals instead of IIFEs or useless fragment wrappers.

### QueueSidebar and QuestionsExplorer (Phase 2)
- Item preview text uses `getQueuePreview(item)` — returns first user history message content, falling back to `item.question`.
- `QuestionsExplorer` has a "Turns" column (history.length); colSpan is 10 (was 9). Column header is "Question / Message" (was "Question").
