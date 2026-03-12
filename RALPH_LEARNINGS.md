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

### Frontend evidence shell (Phase 4 — prior iterations)
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

### Tool-Call Decision Editing (Phase 4 — current iteration)
- `ToolCallRecord` now has `arguments?: Record<string, unknown>`. The apiMapper passes through the raw object — no special mapping needed since the spread already copies it.
- `ToolCallDetailView` at `frontend/src/components/app/editors/ToolCallDetailView.tsx` replaces the inline `ToolCallEntry` in TracePanel. Uses `CodeBlockFallback` from registry with a minimal `RenderContext` stub for arguments and response rendering.
- `ToolNecessityEditor` at `frontend/src/components/app/editors/ToolNecessityEditor.tsx` is a tri-state toggle (required/optional/not-needed) per tool name. Tool names are derived from the union of toolCalls + existing expectedTools entries. Default state for unclassified tools is `optional`.
- `useGroundTruth` now exposes `updateExpectedTools(tools: ExpectedTools)`. Prop is threaded through `demo.tsx` → `ReferencesSection` → `TracePanel` → `ToolNecessityEditor` and also → `ExpectedToolsSection`.
- `canApproveMultiTurn` now enforces ≥1 required tool in `expectedTools.required`. Items with no expectedTools or empty required array are blocked UNLESS a plugin declares `data.canBypassRequiredTools: true`.
- `canBypassRequiredToolsCheck(item)` checks `item.plugins` for any payload with `data.canBypassRequiredTools === true`. RAG compat items should set this flag in their plugin payload.
- The bypass only skips the "≥1 required tool" gate; it does NOT skip `validateExpectedTools` (required tools still must appear in toolCalls if defined).
- Phase 4 validation: `cd frontend && npm run typecheck && npm run lint:check && npm run test:run -- --pool=threads --poolOptions.threads.singleThread`. Current gate: 297/297 tests (39 test files), tsc/Biome clean.
- Backend test for required-tools enforcement (`test_validation_required_tools.py`) deferred to Phase 5 when the backend side is implemented.
- Test updates: `gtHelpers.expectedBehavior.test.ts` base item now includes `expectedTools: { required: [...] }` + `toolCalls` to satisfy the new gate. Two new test cases: plugin bypass and strictness when no required tools defined.

### Phase 3 workspace layout (reviewer-confirmed)
- The curate workspace now uses `react-resizable-panels` v4.7.2 (Group/Panel/Separator API, NOT PanelGroup/PanelResizeHandle). The library API is: `orientation` (not `direction`), `Group` (not `PanelGroup`), `Separator` (not `PanelResizeHandle`). No `autoSaveId` prop — use `onLayoutChanged` + `defaultLayout` with manual localStorage.
- `SplitPaneLayout.tsx` lives at `frontend/src/components/app/layout/SplitPaneLayout.tsx`. The left panel id is `"editor"`, right is `"evidence"`, stored under `gtc-split-pane-sizes`. Min size is 20% per panel (percentage-based, not pixel).
- Mobile evidence drawer lives at `frontend/src/components/app/layout/EvidenceDrawer.tsx`. Toggle state (`drawerOpen`) is in `demo.tsx`. Drawer has `role="dialog"`, `aria-modal`, backdrop, outside-click dismiss, Escape key.
- `ContextEntryEditor.tsx` at `frontend/src/components/app/editors/ContextEntryEditor.tsx` (note: `editors/` plural, distinct from existing `editor/` singular directory).
- `useGroundTruth` now exposes `updateContextEntries(entries: ContextEntry[])`. The prop is threaded through `demo.tsx` → `ReferencesSection` → `TracePanel` → `ContextEntryEditor`.
- `demo.tsx` no longer uses CSS grid for the curate layout. The grid was `md:grid-cols-12` with `col-span` classes; it's now flexbox + SplitPaneLayout. The `cn` import was removed from demo.tsx since it's unused post-grid-removal.
- Phase 3 validation: `cd frontend && npm run typecheck && npm run lint:check && npm run test:run -- --pool=threads --poolOptions.threads.singleThread` — expect 288+ tests, 38+ files, 134 files linted.
- Biome flags `autoFocus` as unsafe (`noAutofocus`); use `useRef` + `useEffect` focus pattern instead.
- ContextEntryEditor does not yet integrate RegistryRenderer for plugin-contributed context entry editors — no plugins register such editors yet. Future phases wiring plugin context-entry renderers should add RegistryRenderer lookup here.
- Phase 3 reviewer iteration 1: approved with 0 findings. All success criteria met, 288/288 tests, tsc/Biome clean.

### Frontend component registry (Phase 2 — registry implementation)
- Registry files live at `frontend/src/registry/`: `FieldComponentRegistry.ts` (singleton), `RegistryRenderer.tsx` (wrapper), `PluginErrorBoundary.tsx`, and `fallbacks/` directory.
- Barrel at `frontend/src/registry/index.ts` re-exports everything — Biome enforces alphabetical named exports.
- `FieldComponentRegistry.resolve()` does exact match first, then prefix match (registered `"toolCall"` matches `"toolCall:retrieval"` — separator must be `:`).
- `RegistryRenderer` selects fallback by data shape: objects→`KVDictFallback`, strings→`CodeBlockFallback`, everything else→`JsonFallback`.
- `PluginErrorBoundary` logs to `console.error` only under `import.meta.env.DEV`.
- Tests are in `frontend/tests/unit/registry/` (NOT `frontend/src/registry/__tests__/`) — vitest includes `tests/unit/**/*.{test,spec}.{ts,tsx}`.
- Phase 2 validation: `cd frontend && npm run typecheck && npm run lint:check && npm run test:run -- --pool=threads --poolOptions.threads.singleThread` — expect 288+ tests, 38+ test files.
- `reset()` exists on the class for testing — use fresh `new FieldComponentRegistry()` instances in tests rather than the module singleton.
- Reviewer iteration 1 confirmed Phase 2 approved: 288/288 tests, tsc/Biome clean. No open items.
- `types.ts:64` comment says "Throws on duplicate" but implementation warns — matches Phase 2 spec; consider fixing the comment in a future pass.
- TracePanel KVDict extraction was suggested in details but deferred — fits Phase 3 or Phase 6 integration.

### Phase 1 contract stabilization (Phase 1)

- `RetrievalCandidate` added to `backend/app/domain/models.py` (after `ExpectedTools`) and `frontend/src/models/groundTruth.ts` (after `PluginPayload`). Not yet used by any API endpoint — will appear in OpenAPI when Phase 5/6 wires it into responses.
- Backend `PluginPack` now has four no-op extension methods: `get_stats_contribution`, `get_explorer_fields`, `get_import_transforms`, `get_export_transforms`. Existing `RagCompatPack` does not need overrides yet — backward compat confirmed.
- `PluginPackRegistry` has matching aggregation helpers: `collect_stats`, `collect_explorer_fields`, `collect_import_transforms`, `collect_export_transforms`.
- Supporting dataclasses `ExplorerFieldDefinition`, `ImportTransform`, `ExportTransform` live in `backend/app/plugins/base.py`. Each has a `pack_name` field auto-populated by the registry aggregation methods.
- Frontend registry types live at `frontend/src/registry/types.ts` with barrel at `frontend/src/registry/index.ts`. Phase 2 will add the concrete `FieldComponentRegistry` implementation.
- Biome enforces alphabetical named exports — keep barrel exports sorted.
- Wireframe-to-schema field mapping at `.copilot-tracking/research/2026-03-12/wireframe-schema-field-mapping.md` — key difference is `toolCallDecisions` (wireframe per-ID map) vs `expectedTools` (schema categorized lists).
- Phase 1 reviewer validation (iteration 1): all gates pass — `ruff check`, `ty check`, `tsc`, Biome lint, 343 backend unit tests. No review items opened. `RetrievalCandidate` backend model uses `extra="forbid"` and validators for `url` (non-empty) and `relevance` (enum constraint) — later phases wiring this into APIs should preserve those guards.

### Phase 5 full-stack validation (Phase 5)

- All validation gates pass: `smoke`, `check`, `test` (340 backend unit + 267 frontend), `backend-integration-test` (138 passed, 9 skipped), `ci`, `verify`, `export_openapi.py`, `api:types:check`.
- One minor fix required: the committed `frontend/src/api/openapi.json` and `frontend/src/api/generated.ts` had a stale `HistoryEntryPatch` schema reference. The OpenAPI exporter now resolves it from `assignments.py` (new canonical location after Phase 1) instead of the duplicate `ground_truths.py` definition. Refreshing and committing the two API artifacts resolved the `api:types:check` failure.
- Remaining noise: `GroundTruthItem` field-shadowing `UserWarning` entries in `export_openapi.py` output are pre-existing deferred items tracked as `WI-08`. `QuestionsExplorer` `act(...)` warnings and Vite chunk-size warning remain from prior phases.
- Duplicate `HistoryEntryPatch` in `ground_truths.py` vs `assignments.py` is tracked as `WI-09`/`WI-23` for future cleanup — do not remove the `ground_truths.py` copy without verifying no consumers import it directly.
- Phase 5 reviewer rerun on 2026-03-12 re-confirmed the artifact fix: `frontend/src/api/openapi.json` and `frontend/src/api/generated.ts` now reference `app__api__v1__assignments__HistoryEntryPatch` everywhere, and no stale `app__api__v1__ground_truths__HistoryEntryPatch` refs remain.
- If validation totals drift from the Phase 5 changes log in a dirty worktree, check for unrelated local test edits before treating it as a redesign regression; the current rerun still passed with unrelated local changes outside the reviewed phase.
