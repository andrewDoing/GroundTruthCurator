# Ground Truth Curator – Frontend Codebase Guide

This guide is a compact, practical map for future contributors (human or AI) to understand and extend the React + Vite + TypeScript frontend. It explains structure, data models, flows, and safe extension points. It reflects the current codebase after the hook refactor and API integrations.

If you do just one thing: scan the Architectural Overview and the Key Flows. They’ll unlock ~80% of the code.

## Stack and Tooling

- Runtime: React 19, TypeScript 5.8, Vite 7
- Styling: Tailwind CSS v4 (via `@tailwindcss/vite`)
- Icons: `lucide-react`
- API client: `openapi-fetch` + generated types via `openapi-typescript` (`src/api/generated.ts`)
- Tests: Vitest (unit) + Playwright (e2e)
- Lint/Format: Biome (`biome.json`), ESLint baseline present but Biome is primary
- Build scripts (see `package.json`):
  - dev: vite
  - build: `tsc -b && vite build`
  - lint: `biome check --write`
  - preview: vite preview
  - api:types: generate `src/api/generated.ts` from `VITE_OPENAPI_URL` (defaults to `http://localhost:8000/v1/openapi.json`)
  - test: Vitest; e2e via `playwright test`
- TypeScript config uses project references (`tsconfig.json` → `tsconfig.app.json`, `tsconfig.node.json`), bundler resolution, and strict flags. No emit; Vite does the bundling.

## Directory Layout

- `index.html` – Vite entry, loads `src/main.tsx`
- `src/main.tsx` – React root render, StrictMode, imports Tailwind via `index.css`
- `src/App.tsx` – App shell; renders the demo application `src/demo.tsx`
- `src/demo.tsx` – Shell UI that composes feature hooks and components
- `src/components/` – UI building blocks
  - `app/QueueSidebar.tsx` – left queue of items, includes self-serve assignment button
  - `app/StatsView.tsx` – simple stats dashboard
  - `app/InstructionsPane.tsx` – collapsible markdown pane (curation instructions)
  - `app/ReferencesPanel/` – right panel tabs: search + selected
  - `app/editor/TagsEditor.tsx` – tag management
  - `common/Toasts.tsx` – toast UI
  - `overlay/ReferenceViewer.tsx` – legacy in-app preview (currently not used; we open in a new tab)
- `src/hooks/` – feature hooks
  - `useGroundTruth.ts` – main state/logic hub (provider, selection, save, delete/restore)
  - `useReferencesSearch.ts`, `useReferencesEditor.ts` – sub-features
  - `useGlobalHotkeys.ts`, `useToasts.ts` – UX utilities
- `src/models/` – domain types, utilities, provider abstraction
  - `groundTruth.ts` – types (Reference, GroundTruthItem)
  - `fingerprints.ts` – idempotency/versioning fingerprints
  - `provider.ts` – Provider interface, `JsonProvider` (demo), `ApiProvider` (backend with ETag)
  - `gtHelpers.ts` – helpers: approval/generation gates, ref de-dupe
  - `utils.ts` – misc helpers (nowIso, randId, urlToTitle, cn)
  - `validators.ts` – approval gating primitive
- `src/api/` – OpenAPI client plumbing
  - `generated.ts` – generated types (run `npm run api:types`)
  - `client.ts` – typed `openapi-fetch` client + utf-8 JSON fetch wrapper
- `src/services/` – backend integrations
  - `assignments.ts` – request/list/update assigned items
  - `groundTruths.ts` – list/get/update/delete, snapshot download
  - `http.ts` – small fetch helpers
  - `search.ts` – `searchReferences` (backend) + `mockAiSearch`
  - `stats.ts` – stats endpoint + demo mock
- `src/config/demo.ts` – DEMO mode flag
- `src/dev/self-tests.ts` – runtime self-checks for versioning/validators (dev only)
- `tests/` – Vitest unit + Playwright e2e suites

## Architectural Overview

A single-page React app. Core state and logic live in `src/hooks/useGroundTruth.ts` (with sub-hooks), and `src/demo.tsx` focuses on composing the UI. There’s no global store; the Provider pattern is abstracted via `models/provider.ts` with:
- `JsonProvider` – in-memory demo data (used when DEMO_MODE is on)
- `ApiProvider` – real backend via assignments/ground-truths endpoints, with ETag handling and conflict (412) retry

Key concepts:
- Provider abstraction: `Provider` with list/get/save/export. `ApiProvider` implements REST calls and ETag concurrency.
- DEMO mode: `src/config/demo.ts` computes a boolean from `DEMO_MODE`/`VITE_DEMO_MODE`; when true, the app uses `JsonProvider` and mocks for search/LLM/stats.
- Fingerprints: `itemVersionFingerprint` (content only) and `itemStateFingerprint` (content + status/deleted) drive idempotency and version bumping. Tags are part of content.
- Approval constraints: `canApproveCandidate(item)` requires at least one selected reference AND that `refsApprovalReady(item)` passes (all refs visited; selected refs have ≥40 char key paragraph). Deleted items cannot be approved.
- UX separation: Left queue, center editor (Question/Answer + actions), right references pane (Search vs Selected tabs), stats view, and modal overlays.

## Data Models (from `src/models/groundTruth.ts`)

- Reference: { id, title?, url, snippet?, visitedAt?, keyParagraph?, selected? }
- GroundTruthItem: {
  id, question, answer,
  references: Reference[],
  status: "draft" | "approved" | "skipped",
  providerId, version, deleted?,
  tags?: string[],
  curationInstructions?: string
}
- Change category: previously required when Q/A changed; no longer enforced. A legacy `ChangeCategorySelector` component exists but is not wired into save logic.

## Provider Contract (from `src/models/provider.ts`)

- id: string
- list(): Promise<{ items: GroundTruthItem[] }>
- get(itemId): Promise<GroundTruthItem | null>
- save(item): Promise<GroundTruthItem>
  - Version bumps only when content fingerprint changes (question/answer/references/tags). Status-only updates do NOT bump.
- export(ids?): Promise<string> – JSON string (array) of current items

Providers:
- `JsonProvider` – in-memory store seeded by `DEMO_JSON` (for demo mode and self-tests)
- `ApiProvider` – integrates with real backend
  - Uses assignments endpoints for typical updates; ground-truths endpoint when restoring deleted items
  - Handles ETag (`If-Match`) and 412 retry by refetching and retrying once
  - `export` returns JSON of cached assigned items; the UI’s Export button uses a separate backend snapshot endpoint for download

## Fingerprints (from `src/models/fingerprints.ts`)

- `itemVersionFingerprint(item)` – JSON of core content (id, providerId, question, answer, normalized refs sorted by id, tags sorted). Excludes status and version.
- `itemStateFingerprint(item)` – version fingerprint plus status and deleted flag. Used to detect no-op saves (content + status).
- Reference normalization ensures stable comparison: trims fields, normalizes selected to boolean, nulls visitedAt.

## Validation (from `src/models/validators.ts` + `gtHelpers.ts`)

- `refsApprovalReady(item)`
  - If references exist: all must be visited; selected references must have keyParagraph length >= 40
  - If no references: this primitive returns true, but is combined with:
- `canApproveCandidate(item)` – requires at least one selected reference, `refsApprovalReady(item)` to pass, and item not deleted

## UI/State Flow (from `src/hooks/useGroundTruth.ts` + `src/demo.tsx`)

High-level state:
- Provider instance ref – picks `JsonProvider` in demo mode, otherwise `ApiProvider`
- items: list shown in Queue, updated on save/refresh
- selectedId: current item id; `current`: editable clone
- qaChanged: computed against baseline
- viewMode: "curate" (default) vs "questions" (list-level delete/restore) vs "stats"
- right panel tab: "search" vs "selected"
- search state: query, results, selection set, searching flag
- ref opening: marks visited and opens in a new tab (in-app iframe preview is removed)
- saving and lastSavedStateFp: no-op and double-click idempotency
- toast system: via `useToasts`; keyboard shortcuts via `useGlobalHotkeys` (Save Draft, Approve)

Key flows:
1) Load + select first item – provider initialized on mount; list loaded; selection deep-cloned; QA baseline and search reset; saved fingerprint captured.
2) Edit Question/Answer – textareas bound to `current`; `qaChanged` reflects differences; change category is NOT required anymore.
3) References – right panel
  - Search tab: performs backend `searchReferences` (or `mockAiSearch` in demo), displays results, supports multi-select Add and individual Add; disabled when URL already present; de-dup by URL.
  - Selected tab: lists references with selection toggle, visit/open (sets `visitedAt`), key paragraph with counter; Remove supports Undo (8s window).
4) Generate Answer – opens modal listing selected references; on confirm, calls backend `callAgentChat`. UI currently applies the full answer at once.
5) Save – computes state fingerprint; if unchanged: returns "No changes". If approving, validates `canApproveCandidate`. On success, updates `items`, `current`, and lastSavedStateFp. Status-only saves do not bump version. Content changes (Q/A/refs/tags) bump version (self-tests run in dev).
6) Export – triggers backend snapshot download via `groundTruths.downloadSnapshot()`; no in-app JSON modal.
7) Soft delete – toggled via editor or Questions view; deleted items show a banner and cannot be approved; restore supported.
8) Self-serve assignments – Queue offers a button to request more assignments (limit via `VITE_SELF_SERVE_LIMIT`).

Self-tests: `runSelfTests()` asserts validator rules and provider bump rules in development only (console assertions).

## Components Quick Reference

- QueueSidebar
  - Inputs: items, selectedId, onSelect, onRefresh, onSelfServe
  - Shows id, status badge, version, and question (truncated); highlights deleted
- ReferencesTabs
  - Props split for SearchTab and SelectedTab; handles tab switch and counts selected refs
- SearchTab
  - Inputs: query, results, selection set, existingReferences, callbacks
  - Buttons: Search, Add, open in new tab, sticky "Add N to Selected"
- SelectedTab
  - Inputs: references and callbacks (update/remove/open)
  - Shows visit status, selection toggle, key paragraph with counter; Remove triggers confirmation and Undo toast
- TagsEditor
  - Inputs: selected tags; allows add/remove
- InstructionsPane
  - Inputs: markdown; collapsible curation instructions surfaced per item
- GenerateAnswerModal
  - Inputs: question + selected references; shows them and provides Generate & Apply
- ReferenceViewer
  - Legacy in-app iframe preview; not used in the current UI (links open in a new tab)
- Toasts
  - Inputs: toasts array; optional action handler; positioned bottom-right
- StatsView
  - Inputs: items and stats payload; renders simple counts across sprints

## Styling & UX Conventions

- Tailwind utility classes; purple/violet accent theme
- Buttons use rounded-xl + border; primary actions use violet background; destructive uses rose
- Truncation and text-xs for metadata; line-clamp used sparingly
- Accessibility: semantic buttons, labels; minimal titles
- Keyboard shortcuts: Cmd/Ctrl+S saves draft; Cmd/Ctrl+Enter attempts approve (gated)

## Extension Points and How-Tos

1) Integrate real services
  - Search: `services/search.ts` already calls backend `GET /v1/search` and accepts multiple response shapes; keep returning the `Reference` shape (id, url, title, snippet, visitedAt=null, keyParagraph="", selected=true). De-dup uses URL.
  - Provider: `ApiProvider` implements REST with ETag; if expanding endpoints, keep fingerprint/version semantics so status-only saves don’t bump version.

2) Add fields to GroundTruthItem or Reference
  - Update types in `models/groundTruth.ts`
  - Update normalization in `models/fingerprints.ts` if fields affect content equality (e.g., include in tags or refs)
  - Propagate through UI where needed; ensure providers preserve version rules

3) Add validation rules
  - Extend `models/validators.ts` and/or `gtHelpers.ts`
  - Enforce in `useGroundTruth.save` before invoking provider

4) Add a new tab to the right panel
  - Extend `ReferencesTabs.tsx` with a new discriminated union value and conditional render
  - Keep props isolated per tab to avoid cross-tab dependencies

5) Export mechanics
  - UI uses backend snapshot download (`groundTruths.downloadSnapshot`). If you need in-app preview, reintroduce an `ExportModal` backed by `provider.export()` and/or the snapshot payload.

6) Routing or multi-page
  - Current app is SPA without a router. Introduce React Router, and mount `GTAppDemo` within routes. Consider moving provider init into a context provider.

## Gotchas and Invariants

- Version rules: only content changes bump version. Content includes Q/A, references, and tags. Do not bump for status-only or no-op saves. Fingerprints enforce this—self-tests run in development.
- Approval gating: requires at least one selected reference; if references exist, all must be visited; selected refs require ≥ 40 chars key paragraph; deleted items cannot be approved.
- Undo delete window: 8 seconds via toast action; ensure timers cleared on unmount in `useToasts`.
- Deep clone on selection: ensures edits don’t mutate provider list until Save.
- De-dup by URL when adding references from search.
- Preview: links open in a new tab; the legacy in-app iframe preview is disabled due to site embedding policies.
- Concurrency: `ApiProvider` retries once on ETag (412) by refetching and resubmitting the update.

## Minimal “contract” summary

Inputs
- Initial JSON seed (demo), or real provider backend
- User edits: question, answer, references

Outputs
- Persisted items with stable versioning
- Snapshot JSON download for downstream pipelines

Error modes
- Network failures (replace mocks): show toast and keep state consistent
- Popup blocked on new tab: info toast prompts user

Success criteria
- No-op or status-only saves do not bump version
- Approval only allowed when validator passes
- Undo for ref deletion works within 8 seconds

## Running and Verifying

- Start: `npm run dev`
- Typecheck/Build: `npm run build`
- Lint/Format: `npm run lint`
- Unit tests: `npm test` or `npm run test:run`
- E2E tests: `npm run test:e2e` (optionally `:headed` or `:ui`)

Manual smoke test
- Load app, verify first item selected
- Toggle references visited and add key paragraphs; attempt Approve gating (requires ≥1 selected ref)
- Run Search, add results, ensure de-dup by URL
- Generate Answer populates answer text
- Save Draft vs Approve follows version bump rules
- Export triggers a JSON file download (snapshot)
- Use Questions view to delete/restore; Stats view loads metrics

## Future Ideas

- Extract a ProviderContext to support multiple providers and auth
- Replace inline self-tests with a dedicated test harness
- Streaming UI for generation
- Reintroduce in-app preview for sites that allow embedding
- Bulk actions for references
