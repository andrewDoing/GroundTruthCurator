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
- Iteration 2 fixed the last reviewed hard-coded `"agent"` checks in `frontend/src/hooks/useGroundTruth.ts` and `frontend/src/components/app/editor/MultiTurnEditor.tsx`; add-user gating plus delete/regenerate answer sync now work for preserved non-user roles like `"output-agent"` and `"orchestrator-agent"`.

### Approval logic (Phase 2)
- `canApproveMultiTurn` no longer requires `expectedBehavior` on every agent turn and no longer reuses retrieval-specific reference gating. Approval requires only: valid conversation pattern (user/non-user alternating, ends on non-user turn) + item not deleted. The `expectedBehavior` field is still in the model and editor UI but is not gated.
- `canApproveCandidate` still keeps the old `refsApprovalReady()` checks for the single-turn compatibility path (items without `history`).

### Generic schema fields (Phase 2)
- `GroundTruthItem` now carries: `contextEntries`, `toolCalls`, `expectedTools`, `feedback`, `metadata`, `plugins`, `traceIds`, `tracePayload`, `scenarioId` — all passed through by the mapper from `AgenticGroundTruthEntry-Output` in `generated.ts`.
- `hasEvidenceData(item)` returns `true` when any of toolCalls/traceIds/metadata/feedback/tracePayload has content. `TracePanel` renders only when this is true.

### Biome lint (Frontend)
- `npm run lint` applies auto-fix (writes changes); `npm run lint:check` is the gate check (no writes, exits non-zero on error).
- Biome will skip "unsafe" fixes. `noUselessFragments` wrapping a single IIFE is marked unsafe — fix manually by rewriting JSX to use direct conditionals instead of IIFEs or useless fragment wrappers.
- Phase 2 iteration 2 validation command: `cd frontend && npm run lint:check && npm run typecheck && npm run test:run -- --pool=threads --poolOptions.threads.singleThread && npm run build`.
- Phase 2 reviewer rerun confirmed `R-001` is closed; regression coverage now exists in `frontend/tests/unit/components/app/pages/CuratePane.test.tsx`, `frontend/tests/unit/hooks/useGroundTruth-deleteTurn.test.tsx`, and `frontend/tests/unit/hooks/useGroundTruth-multiturn.test.tsx`. Current frontend gate result is `249/249` tests passing with only the known `QuestionsExplorer` `act(...)` warnings and Vite chunk-size warning still emitted.

### QueueSidebar and QuestionsExplorer (Phase 2)
- Item preview text uses `getQueuePreview(item)` — returns first user history message content, falling back to `item.question`.
- `QuestionsExplorer` has a "Turns" column (history.length); colSpan is 10 (was 9). Column header is "Question / Message" (was "Question").

### Backend plugin packs (Phase 3)
- Plugin-pack startup validation now runs in `backend/app/container.py` via `container.plugin_pack_registry.validate_all()` during `startup_cosmos()`. Misconfigured packs should fail startup there, not lazily at request time.
- The minimal backend plugin-pack contract lives in `backend/app/plugins/base.py` (`PluginPack`, `PluginPackRegistry`); the default registry wiring is in `backend/app/plugins/pack_registry.py`.
- RAG-specific helper ownership moved to `backend/app/plugins/packs/rag_compat.py`. Reuse `RagCompatPack` helpers instead of hard-coding the `"rag-compat"` plugin key or adding ref attach/detach logic back into generic services.
- `backend/app/services/search_service.py` is now query-only. Plugin-specific approval extensions flow through `backend/app/services/validation_service.py` by calling `container.plugin_pack_registry.collect_approval_errors(item)` after the generic approval checks.
- `POST /v1/ground-truths?approve=true` bulk imports must use `validate_item_for_approval()` (not `collect_approval_validation_errors()` directly) so plugin-pack approval hooks run. Regression coverage lives in `backend/tests/unit/test_phase1_rework.py::TestBulkImportApprovalValidation::test_bulk_import_approve_enforces_plugin_pack_approval_hooks`.
- Phase 3 validation command: `cd backend && uv run ruff check app/ && uv run ty check app/ && uv run pytest tests/integration/ -v -k 'assignments or ground_truths or search or snapshot'`.
- Phase 3 iteration 2 review closed `R-001`: `backend/app/api/v1/ground_truths.py` now routes bulk `approve=true` imports through `validate_item_for_approval()`, and the targeted regression + integration slice both pass (`18 passed` targeted unit slice, `90 passed / 2 skipped` integration slice). Treat remaining `GroundTruthItem` field-shadowing warnings as known deferred noise, not a fresh Phase 3 regression.

### Frontend evidence shell (Phase 4)
- Phase 4 reviewer finding `R-001`: `frontend/src/models/groundTruth.ts` `hasEvidenceData()` and `frontend/src/components/app/TracePanel.tsx` still omit `contextEntries` and plugin payload rendering, so items carrying only those fields do not surface in the right pane yet.
- Phase 4 reviewer finding `R-002`: `frontend/src/components/app/ReferencesPanel/ReferencesTabs.tsx` still calls `setRightTab("selected")` during render for multi-turn mode, which now shows up as `Cannot update a component while rendering a different component` during `ReferencesSection.test.tsx`.
- `frontend/src/components/app/pages/ReferencesSection.tsx` is now the generic right-pane host: render `TracePanel` first when `hasEvidenceData(item)` is true, then show `ReferencesTabs` only as a labeled RAG compatibility surface (`!isMultiTurn || references.length > 0`).
- `frontend/src/components/app/TracePanel.tsx` now owns expected-tools review UI. Required expected tools are compared against `item.toolCalls`; missing required tools show as failures there and also block approval through `validateExpectedTools()` / `canApproveMultiTurn()`.
- `frontend/src/models/groundTruth.ts` `hasEvidenceData(item)` now treats `expectedTools` as evidence data too, so expected-tools-only items still render the evidence pane.
- `frontend/src/components/app/QuestionsExplorer.tsx` supports `toolCallCount` sorting, but it is client-side only for now — do not pass that sort key to backend list APIs.
- Phase 4 iteration 2 closed review items `R-001`/`R-002`: `hasEvidenceData(item)` now also lights up for `contextEntries` and `plugins`, `TracePanel` renders generic `Context Entries` plus `Plugin Details` sections, and `ReferencesTabs` forces the multi-turn `"selected"` tab from an effect instead of render.
- In multi-turn mode, keep Cmd/Ctrl+2 for the selected references tab, but ignore Cmd/Ctrl+1 because the search tab is intentionally hidden there; tests now cover both the effect-driven tab sync and the absence of the render-phase React warning.
- Phase 4 validation command: `cd frontend && npm run lint:check && npm run typecheck && npm run test:run -- --pool=threads --poolOptions.threads.singleThread && npm run build`.
- Current frontend gate after Phase 4 iteration 2: `267/267` tests passing, with the long-standing `QuestionsExplorer` `act(...)` warnings and the existing Vite chunk-size warning still emitted. The render-phase `ReferencesTabs` warning is gone.
- Reviewer rerun on 2026-03-12 re-confirmed Phase 4 closeout: `ReferencesSection.test.tsx` and `ReferencesTabs.multiturn.test.tsx` still cover the fixed paths, `267/267` frontend tests pass, and only the long-standing `QuestionsExplorer` `act(...)` plus Vite chunk-size warnings remain.
