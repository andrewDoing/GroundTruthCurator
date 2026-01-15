# Playwright E2E Test Plan (App + API + DB)

This plan outlines a minimal, working Playwright test suite to prove the primary workflows of the UI against a real backend and database. It prioritizes simplicity, avoids legacy fallbacks and mocks, and tests only what exists today.

## Overview

We will add a lightweight Playwright setup that launches the Vite app and validates these flows end-to-end against the backend and database:
- App boot and navigation (curate, questions, stats)
- Queue selection and editor updates
- Saving (draft), skip behavior, and approval gating
- References search, add, de-duplication, and selection
- Selected references: visit, key paragraph, remove/undo
- Draft answer generation modal and apply
- Soft delete/restore (both in curate and questions views)
- Export JSON modal
- Assignments self-serve and my assignments

Keep it simple: use existing visible text/roles for selectors, avoid test-only code and heavy page objects, and run entirely against real services (no demo mode, no network mocks).

---

## Prerequisites and orchestration

- Backend and database are running and reachable at `http://localhost:8000` (adjust if different). Health endpoint: `GET /healthz`.
- Frontend is configured per `CONNECT_TO_BACKEND.md` (Vite dev proxy for `/v1` → backend or `VITE_API_BASE_URL` pointing at backend).
- Use a dedicated dataset for tests, e.g., `datasetName = e2e` to isolate state.

Local options
- Start backend+DB as you normally do (e.g., docker-compose in backend repo) and run tests locally. We will reuse an existing dev server for fast feedback.

CI options
- Start backend+DB via your pipeline (docker compose or service env). Frontend uses a build + preview server for stability. Global setup waits for backend health and seeds deterministic data.

---

## Files to add/change (plan only)

- `package.json`
  - devDependencies: `@playwright/test`
  - scripts:
    - `test:e2e`: run Playwright tests headless
    - `test:e2e:headed`: run headed for debugging
    - `test:e2e:ui`: open PW UI mode
    - `test:e2e:debug`: run with PWDEBUG=1
    - `test:e2e:install-browsers`: install Playwright browsers
- `playwright.config.ts`
  - Local: `webServer` runs `npm run dev` (fast feedback) with `reuseExistingServer: true`.
  - CI: `webServer` runs `npm run preview` after a build for stability (no HMR noise).
  - `use.baseURL`: `http://localhost:5173` (dev) or `http://localhost:4173` (preview). Switch with `process.env.CI`.
  - Browser: chromium only; `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`.
  - Timeouts: `timeout: 30_000`, `expect: { timeout: 5_000 }`.
  - Retries: `retries: process.env.CI ? 1 : 0`.
- `tests/e2e/fixtures/fixtures.ts`
  - Shared helpers, stable selectors, toast expectations, and common actions.
- `tests/e2e/global-setup.ts`
  - Waits for backend `GET /healthz` to be healthy.
  - Seeds a deterministic dataset (e.g., `datasetName=e2e`) via real endpoints (import ground truths, tags schema, etc.).
- Specs (see names below) under `tests/e2e/`.

No code changes in `src/`; selectors rely on visible labels/roles (e.g., “Export JSON”, “Search”, “Selected (N)”, “Save Draft”, “Approve”). If a single spot proves flaky, prefer an ARIA role+name refinement over adding test IDs.

---

## Helper functions (names + short purpose)

- `startApp(page)`
  - Navigates to baseURL, waits for header text and initial queue load.
- `toggleSidebar(page, show: boolean)`
  - Clicks “Hide Sidebar”/“Show Sidebar” to reach desired state.
- `switchToQuestionsView(page)` / `switchToCurateView(page)`
  - Uses the header toggle to switch between views.
- `openStats(page)`
  - Clicks “Stats” and waits for stats content (or loading placeholder then content).
- `selectQueueItemByLabel(page, idStartsWith: string)`
  - Clicks queue row whose visible ID starts with given prefix (e.g., `GT-0001`).
- `saveDraft(page)`
  - Clicks “Save Draft”; expects success toast.
- `approve(page)`
  - Clicks “Approve”; expects success toast and approved status chip.
- `runSearch(page, query: string)`
  - Enters query and clicks “Search”; waits for result cards to appear (real API).
- `addSearchResultByTitle(page, title: string)`
  - Clicks “Add” on a result card by title; asserts button becomes “Added”.
- `addSelectedFromResults(page)`
  - Clicks sticky “Add {N} to Selected” button; Selected tab count increments.
- `goToSelectedTab(page)`
  - Clicks “Selected (N)” tab and asserts active content.
- `fillKeyParagraphForSelectedIndex(page, index: number, text: string)`
  - Enters 40+ chars into key paragraph for N-th selected row; counter turns green.
- `markReferenceVisited(page, index: number)`
  - Clicks “Open” for that ref; expects “✓ Visited …” chip appears.
- `openGenerateModal(page)` / `confirmGenerateAndApply(page)`
  - Opens Generate modal; applies; answer textarea updated.
- `softDeleteCurrent(page)` / `restoreCurrent(page)`
  - Toggles Delete/Restore; confirms banner/toast/controls update.
- `exportJson(page)`
  - Clicks “Export JSON”; verifies modal textarea has non-empty JSON.
- `awaitBackendHealthy()`
  - Polls `GET /healthz` until healthy (used in global setup).
- `seedDataset()`
  - Imports a small, deterministic set of items into dataset `e2e` (id prefixes like `GT-0001`), plus any minimal tags schema required for UI.
- `expectToast(page, pattern: RegExp)`
  - Asserts a toast/snackbar via `role=alert`/`role=status` contains expected text.

---

## Test files and coverage notes

App bootstrap — `app.smoke.spec.ts`
- `should load app and render header`
  - Header visible; queue items listed (from seeded dataset); curate view initial sections present.

Sidebar & view switching — `queue-and-editor.spec.ts`
- `should toggle sidebar visibility`
  - Hide sidebar removes queue; show restores it.
- `should switch between curate and questions views`
  - Toggle button changes content accordingly.
- `should select queue item and show its details`
  - Selecting `GT-0001` updates question/answer editors.
- `should edit question and show unsaved indicator`
  - Type in question; sidebar shows “unsaved” chip for that item.

Saving & skip — `queue-and-editor.spec.ts`
- `should save draft and show success toast`
  - Click Save Draft; toast.
- `should skip item and advance selection`
  - Click Skip; selection advances to next item.

References: search and selected — `references-search-and-selected.spec.ts`
- `should run search and show results`
  - Enter query and Search; result cards appear (real API).
- `should add single result and disable its button`
  - Click Add; button becomes “Added”; Selected count increments.
- `should multi-select results and add from sticky bar`
  - Select checkboxes; Add {N} to Selected; count increases.
- `should not duplicate references by URL`
  - Adding same URL again doesn’t increase count.

Selected references editing — `references-search-and-selected.spec.ts`
- `should mark reference visited and show visited chip`
  - Click Open; “✓ Visited …” appears; “Needs visit” removed.
- `should enter 40+ char key paragraph and update counter`
  - Counter changes to green; “Needs 40+ chars” removed.
- `should remove a reference and undo restore`
  - Remove → toast with Undo; click Undo → reference restored.

Approval flow — `approval-flow.spec.ts`
- `should keep Approve disabled until refs ready`
  - Approve disabled if refs unvisited or KP < 40.
- `should enable Approve after visiting and KPs provided`
  - Visit each; fill KP; Approve enabled.
- `should approve and show success toast`
  - Click Approve; toast; status chip becomes approved.

Generation modal — `generation.spec.ts`
- `should require eligible references to open modal`
  - If no eligible refs, show guidance; no modal.
- `should generate and apply draft answer`
  - With eligible refs, open modal; Generate & Apply fills answer.

Soft delete & restore — `delete-restore.spec.ts`
- `should soft delete current item and show banner`
  - Delete → info toast; banner “marked as deleted” appears.
- `should restore current item and remove banner`
  - Restore → success toast; banner removed.

Questions view triage — `questions-view.spec.ts`
- `should soft delete and restore from questions view`
  - Row Delete/Restore; toasts; item opacity toggles.

Export JSON — `export-json.spec.ts`
- `should open export modal and show non-empty JSON`
  - Modal textarea contains JSON; “Exported to clipboard” toast observed.

Stats view — `stats.spec.ts`
- `should open stats and render summary`
  - Stats view loads; shows totals or sample chart/cards.

Assignments self‑serve — `assignments-self-serve.spec.ts`
- `should request self-serve and show assigned count toast`
  - Real POST; button shows “Requesting…” then success toast with assigned count.

---

## Keep it simple constraints

- No demo mode; run against real backend+DB (E2E).
- Use visible labels and roles; no code edits or test IDs.
- No network interceptions/mocks; seed deterministic data instead.
- Single browser (chromium) and default viewport; enable traces on retry.
- Isolate state by using a dedicated dataset and resetting selection/state per test.

---

## Stability and speed quick wins

- Server strategy
  - Local: dev server (`npm run dev`), `reuseExistingServer: true` for fast runs.
  - CI: build + preview (`npm run build` then `npm run preview`) for stability.
  - Global setup waits for `GET /healthz` and seeds dataset `e2e`.
- Timeouts/retries/parallelism
  - `timeout: 30s`, `expect.timeout: 5s`.
  - Retries: 1 on CI, 0 locally. `fullyParallel: true` except suites that mutate shared items can be `serial`.
- Deterministic data
  - `seedDataset()` inserts a tiny fixed set (e.g., 5 items) with predictable IDs and content used by selectors.
- Selectors
  - Prefer ARIA roles and accessible names. Centralize common selectors in fixtures.
- Toasts/snackbars
  - Use `expectToast()` helper targeting `role=alert`/`role=status`.
- Clipboard/export
  - Assert JSON shape in modal textarea. Avoid clipboard APIs in headless CI unless explicitly permitted.
- Smoke lane
  - Tag a fast subset (`@smoke`) to run on every PR (under 2 minutes): app bootstrap, save draft, add one ref, export JSON.
- Dev ergonomics
  - Add `test:e2e:debug`, `test:e2e:install-browsers` scripts. Ignore `playwright-report/`, `test-results/`, `blob-report/` in `.gitignore`.
- CI
  - Use official Playwright action, cache browsers, upload traces/videos on failure. Ensure backend+DB are started before tests.

---

## Minimal run instructions (for later adoption)

- Ensure backend+DB are running and healthy at the configured URL.
- Install `@playwright/test` and create `playwright.config.ts` with:
  - Local dev web server; CI preview web server; retries/timeouts as above.
- Add npm scripts: `test:e2e`, `test:e2e:headed`, `test:e2e:ui`, `test:e2e:debug`.
- Execute tests via `npm run test:e2e` (or headed/UI/Debug variants).

---

## Assumptions

- Backend exposes `GET /healthz`, `/v1/ground-truths`, `/v1/search`, `/v1/generate-answer`, `/v1/tags`, assignments endpoints, etc. (per generated OpenAPI types).
- Frontend is configured with a dev proxy or `VITE_API_BASE_URL` as documented in `CONNECT_TO_BACKEND.md`.
- Labels/buttons remain stable: “Search”, “Selected (N)”, “Save Draft”, “Approve”, “Generate Answer”, “Generate & Apply”, “Export JSON”, “Stats”, “Skip”, “Delete”, “Restore”.
- Approve gating is governed by current validation rules (all refs visited; selected refs have ≥ 40 chars key paragraphs; deleted items cannot be approved).

---

## Requirements coverage

- No demo mode; test end-to-end against backend+DB: satisfied (plan updated)
- Identify files to add/change: listed
- Function names + 1–3 sentence purposes: provided
- Test names + 5–10 word behavior notes: provided
- Stability quick wins integrated: server strategy, retries/timeouts, seeding, selectors, toasts, smoke lane, CI notes
