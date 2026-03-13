# Frontend Refactoring Plan — Ground Truth Curator

> Migration note: this document now describes the generic host plus plugin-owned evidence direction. Older single-turn and global references-tab assumptions are kept only when they still describe an active compatibility path.

This plan outlines how to refactor the current 1-file demo (`src/demo.tsx`) into cohesive, testable modules using the already-established patterns (components in `components/*`, hooks in `hooks/*`, models in `models/*`, services in `services/*`). The goal is to preserve behavior while improving structure, maintainability, and testability.

## Goals
- Reduce the size and complexity of `src/demo.tsx` by extracting focused components and hooks.
- Centralize data-and-actions for ground truth items behind a small state layer (hook or context).
- Keep UI patterns and styling consistent with current Tailwind/purple theme.
- Improve separations of concerns: view components vs. state/effects vs. data provider.
- Enable unit tests for provider/versioning rules and validators without browser UI.

## Non-goals (for this refactor)
- Replacing mock services with real backends (Azure/OpenAI/Search). Provide clean extension points instead.
- Changing visual design beyond modest structure/layout improvements.
- Introducing a full-blown global state library unless clearly needed.

## Current State (high-level)
- Single container component: `src/demo.tsx` holds:
  - App header, view toggles, JSON export, in-app preview toggle.
  - Left `QueueSidebar` (already extracted), center multi-turn editor, right evidence/review host (`ReferencesTabs` only when the workflow still uses the shared compatibility surface).
  - Modals already extracted: `GenerateAnswerModal`, `ExportModal`.
  - Overlay already extracted: `ReferenceViewer`.
  - Toast system via `useToasts` and `Toasts` component.
  - Data in `models/*`, mocks in `services/*`.

## Guiding Principles
- Prefer extracting logic to `hooks/*` and views to `components/*`.
- Keep props simple and typed with existing `models/*` types.
- Make stateful features testable by moving I/O and side-effects behind a hook or service function.
- Don’t prematurely generalize; keep focused, composable components.

## Target Architecture
- App shell remains in `demo.tsx` temporarily (or `App.tsx` once swapped).
- Introduce a dedicated feature hook that owns ground truth state and actions:
  - `hooks/useGroundTruth.ts` (or context provider `GroundTruthProvider` if we want React Context). Start with a hook; promote to context only if needed.
- UI composed of small components:
  - HeaderBar (view toggles, preview toggle, export)
  - Editor panel broken into multi-turn conversation editing plus save controls
  - Evidence/review host under `components/app/pages/ReferencesSection.tsx`, with `components/app/ReferencesPanel/*` reserved for the shared compatibility surface
  - Explorer view list extracted to `QuestionsList`.
- Data/Provider boundary
  - Keep `JsonProvider` as the backing implementation.
  - `useGroundTruth` wraps provider calls, tracks selection, saving, and versioning fingerprints.
- Services
  - Keep `services/llm` and `services/search` mocks; expose calls via `useGroundTruth` or pass down as props to components that trigger them.

## Phased Plan
1) Stabilize and extract state layer
- Create `hooks/useGroundTruth.ts` that encapsulates:
  - Provider init and list/get/save/export wiring
  - Items, selectedId, current, fingerprints, saving flag
  - Actions: select, update QA, update reference, remove reference (with undo), toggle deleted/restore, save (with validation), exportJson, runSearch, add refs from results, generate answer scaffolding
  - Keep toast coupling minimal: return status objects or accept callbacks
- Move `runSelfTests()` to `dev/self-tests.ts` and invoke conditionally in development-only code path.

2) Extract view components
- `components/app/HeaderBar.tsx` — controls: sidebar toggle, view toggle, preview toggle, export button.
- `components/app/QuestionsList.tsx` — lists questions and supports soft-delete/restore.
- `components/app/editor/QuestionEditor.tsx`
- `components/app/editor/AnswerEditor.tsx`
- `components/app/editor/ChangeCategorySelector.tsx`
- `components/app/editor/SaveControls.tsx` — save draft/approve/delete/restore buttons (wired to hook actions and validation states).

3) Rewire `demo.tsx`
- Replace inline logic with hook usage and compose the new components.
- Pass only the data/handlers each component needs.

4) Tests
- Add `frontend/src/__tests__/provider.spec.ts` covering versioning bump rules (already asserted in `runSelfTests`).
- Add validator coverage for generic conversation/expected-tools approval first; keep `refsApprovalReady` coverage only for RAG-compat migration paths.
- Add minimal component smoke tests where practical.

5) Cleanup
- Remove obsolete functions from `demo.tsx` and keep it thin.
- Ensure types remain in `models/*`.

## Detailed Extraction Map
From `src/demo.tsx` → new modules:

- Provider and data wiring
  - `providerRef`, list/get/save/export, fingerprints and `saving` → `hooks/useGroundTruth.ts`
  - `onSave`, `toggleDeletedFlag`, `toggleAnyDeleted`, `onExportJson` → `useGroundTruth`
  - Selection: `items`, `selectedId`, `setSelectedId`, `current` → `useGroundTruth`

- Reference management
  - `updateRef`, `removeRefWithUndo` (incl. toast Undo), `onOpenRef` → `useGroundTruth` (expose as actions)
  - `allRefsComplete` → keep in `models/validators` or small util in hook
  - Ref viewer open state (`refViewer`) can remain in the view; the action to mark visited at open comes from the hook

- Search integration
  - `runSearch`, `addRefsFromResults`, `toggleSelectSearchResult`, `addSelectedFromResults` → Split:
    - Search execution stays in hook (`runSearch`) for the remaining compatibility surface
    - Plugin-owned retrieval acquisition should stay out of the shared right-pane host and surface through plugin panels instead.

- Generation
  - `onGenerate`, `doGenerateApply` → Expose `generateDraftAnswer` action in `useGroundTruth` (implementation calls `services/llm` mocks). Modal visibility remains in the view layer.

- QA change tracking
  - `qaState` and `qaChanged` — keep in hook, expose `qaChanged`, `changeCategory`, and setters.

- UI components
  - Header bar: buttons wired to `useGroundTruth` actions `exportJson`, view toggles stay in parent state.
  - Center editors: `QuestionEditor`, `AnswerEditor`, `ChangeCategorySelector`, `SaveControls` consuming hook state/actions.
  - Explorer view list: `QuestionsList` consumes items + delete/restore actions from the hook and an `onOpen` callback to select/open.

## Proposed Files and Responsibilities
- `src/hooks/useGroundTruth.ts`
  - Contract
    - State: items, selectedId, current, saving, inAppPreview (optional if owned by shell), qaChanged, changeCategory, search state (optional), lastSavedStateFingerprint
  - Actions: selectItem(id), updateQuestion(text), updateAnswer(text), setChangeCategory(c), updateReference(id, patch), removeReference(id) with undo callback, markVisited(id), openReference(ref) (returns target URL), runSearch(query), addReferences(refs), save(nextStatus?), exportJson(), toggleDeleted(current/any)
  - Implementation details
    - Holds `providerRef` and memoizes.
    - Encapsulates `itemStateFingerprint` logic.
    - Treats `history[]` with stable `turnId` / `stepId` as canonical editing state, with `question` / `answer` retained only as migration projections.
    - Uses generic approval rules first, with reference-specific validation isolated to compat/plugin behavior.

- `src/components/app/HeaderBar.tsx`
  - Props: sidebarOpen/toggle, viewMode/toggle, inAppPreview/toggle, onExport

- `src/components/app/QuestionsList.tsx`
  - Props: items, onSoftDelete(id), onRestore(id), onOpen(id)

- `src/components/app/editor/QuestionEditor.tsx`
  - Props: value, onChange

- `src/components/app/editor/AnswerEditor.tsx`
  - Props: value, onChange, onGenerate

- `src/components/app/editor/ChangeCategorySelector.tsx`
  - Props: categories, selected, required, onSelect

- `src/components/app/editor/SaveControls.tsx`
  - Props: canApprove, saving, isDeleted, onSaveDraft, onApprove, onDelete, onRestore

- Keep existing:
  - `QueueSidebar`, `ReferencesTabs` (compatibility surface), `GenerateAnswerModal`, `ExportModal`, `ReferenceViewer`, `Toasts`

## Validation and Versioning Rules (kept)
- Status-only saves do not bump version.
- Content changes (question/answer/references) bump version.
- Approval is generic by default; reference visit/key-paragraph rules are a compat/plugin concern while legacy RAG workflows still exist.

## Phase 1 Migration Inventory

- Keep: `useGroundTruth` as the shared editing boundary, but make history the canonical host contract.
- Rewrite: any remaining guidance that treats top-level question/answer or refs-only approval as the permanent architecture.
- Narrow: mapping/provider tests that still hard-code legacy single-turn conversion.
- Delete with shim: temporary references-only guidance once the legacy adapter path is removed.

## Testing Plan
- Unit tests using Vitest (or your current test runner):
  - Provider/versioning: replicate `runSelfTests` into tests and remove from runtime.
  - Validators: generic approval rules first, then `refsApprovalReady` cases for the shrinking compat surface.
  - Hook: small tests around `itemStateFingerprint` behavior and save gating (optional if time-bound).

## Rollout Strategy
- Phase-by-phase PRs:
  1. Add `useGroundTruth` (no UI changes) and rewire `demo.tsx` to use it internally.
  2. Extract editor child components and wire them to the hook.
  3. Extract header and questions list.
  4. Add tests and remove `runSelfTests` from runtime.

## Risks & Mitigations
- Prop drilling after extraction
  - Mitigation: keep `useGroundTruth` in parent and pass only what’s needed; consider context if drilling grows.
- Undo timer and toast coupling
  - Mitigation: allow `useGroundTruth` to surface an `onUndo` callback rather than needing toast access; the shell triggers the toast with that callback.
- Search selection ownership ambiguity
  - Mitigation: keep selection local to `ReferencesTabs` and pass chosen refs back up.

## Acceptance Criteria (DoD)
- Behavior remains aligned with the generic host and active compatibility flows (manual smoke test: save, generic approve gating, delete/restore, add/remove evidence on compat items, generate draft, export JSON, in-app preview toggling).
- `demo.tsx` becomes a thin composition root; core logic moved to `hooks/useGroundTruth.ts` and child components.
- Self-tests moved into unit tests; no console.assert in production code.
- Lint/build pass without new warnings.

## Post-Refactor Follow-ups (Optional)
- Replace mocks with real Azure AI Search and Azure OpenAI via environment-configured services.
- Introduce React Router and move view toggling to routes.
- Consider persistence of UI state (selected tab, search query) via URL or local storage.

## Appendix — Function Mapping
- Data/Save/Export: `onSave`, `toggleDeletedFlag`, `toggleAnyDeleted`, `onExportJson` → `useGroundTruth`
- References: `updateRef`, `removeRefWithUndo`, `onOpenRef` → `useGroundTruth` actions
- Search: `runSearch`, `addRefsFromResults` → `useGroundTruth` actions; selection stays in `ReferencesTabs`
- Generation: `onGenerate`, `doGenerateApply` → `useGroundTruth.generateDraftAnswer` (modal stays in UI)
- QA Tracking: `qaState`, `qaChanged` → `useGroundTruth` state
