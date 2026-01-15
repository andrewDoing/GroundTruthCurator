# Connect Frontend to Backend and Generate TS Models

## Overview

We’ll:

- Generate TypeScript types from the backend’s OpenAPI spec (assume http://localhost:8000/openapi.json; make configurable).
- Add a single source of truth for the API base URL via Vite envs and a light dev proxy to avoid CORS.
- Introduce a tiny typed HTTP helper and minimally type the existing service layer using the generated types.
- Keep scope to “types-only” generation (no client codegen) and minimal wiring in services.

Progress note:

- I scanned your repo: no current Vite dev proxy, and services like `search.ts` build URLs by hand. This plan adds a minimal proxy and a lightweight typed fetch without broader refactors.

---

## Implementation plan (only the functionality needed now)

### 1) Generate TS types from OpenAPI

- Tool: openapi-typescript (types-only; lightweight, framework-agnostic).
- Output: `src/api/generated.ts` kept in source control for deterministic builds.
- Script: add npm script to generate from a configurable URL; provide a default local URL.

### 2) Configure API base URL and dev proxy

- Env: add `VITE_API_BASE_URL=http://localhost:8000`.
- Dev proxy: configure Vite `server.proxy` to forward `/v1` to `http://localhost:8000` (no rewrite) to avoid CORS in development. Frontend calls remain relative to `/v1/...` which matches the backend API prefix.
- Optional dev auth: expose `VITE_DEV_USER_ID` and, when set, send `X-User-Id` header to exercise assigned/assignments endpoints in dev mode.

### 3) Minimal typed HTTP helper

Create `src/services/http.ts` with:

- `getApiBaseUrl()` reading `import.meta.env.VITE_API_BASE_URL` and using relative `/v1` paths in dev (via Vite proxy) so we don’t hardcode localhost.
- `fetchJson<T>()` generic wrapper for JSON requests that returns typed results.
- `withEtag(init, etag)` helper to add `If-Match` header for update calls.
- `withDevUser(init)` helper to add `X-User-Id` from `VITE_DEV_USER_ID` when present.

### 4) Use generated types in service layer

- Replace demo service usage with API-aligned services using generated types:
	- `src/services/groundTruths.ts` for ground-truths CRUD-ish operations:
		- `listGroundTruths(datasetName: string, status?: GroundTruthStatus)` → `GET /v1/ground-truths/{datasetName}`
		- `importGroundTruths(items: GroundTruthItem[])` → `POST /v1/ground-truths`
		- (temporarily removed) `PUT /v1/ground-truths/{datasetName}/{id}` – direct admin update endpoint removed pending redesign; all curator edits flow through assignments API.
		- `deleteGroundTruth(datasetName: string, id: string)` → `DELETE /v1/ground-truths/{datasetName}/{id}`
		- `getStats()` → `GET /v1/ground-truths/stats`
		- `createSnapshot()` → `POST /v1/ground-truths/snapshot`
	- `src/services/assignments.ts` for SME assignment flows:
		- `getAssignedGroundTruths()` → `GET /v1/assigned-ground-truths`
		- `requestAssignmentsSelfServe(limit: number)` → `POST /v1/assignments/self-serve`
		- `getMyAssignments()` → `GET /v1/assignments/my`
		- `updateAssignedGroundTruth(itemId: string, body: { approve?: boolean; answer?: string })` → `PUT /v1/assigned-ground-truths/{item_id}`
- Migrate away from demo `search.ts` and `llm.ts` endpoints; these were placeholders not present in the backend API. Where UI features depend on them, adapt to use list/assignment flows or mark as future work.
- Use generated types from `src/api/generated.ts` (e.g., `components["schemas"]["GroundTruthItem"]`, `components["schemas"]["Stats"]`, and parameter/response shapes under `paths`).

### 5) Developer workflow and guardrails

- Commands:
	- Generate types: `npm run api:types` (defaults to local OpenAPI URL).
	- Optionally add `api:types:check` to ensure the generated file is up-to-date in CI (compare diff).
- Docs:
	- Note how to point generation at other environments using CLI param.

### 6) Out-of-scope (deliberately avoided now)

- Full client codegen, auth/interceptors, error toast plumbing, request retry, pagination helpers, and any legacy fallbacks.

---

## Files to change (and why)

- package.json
	- Add devDependency: `openapi-typescript`.
	- Add scripts:
		- `api:types`: generate types from OpenAPI to `src/api/generated.ts`.
		- `api:types:env`: convenience target using `VITE_OPENAPI_URL`.

- vite.config.ts
	- Add `server.proxy` mapping `/v1` → `http://localhost:8000` with `changeOrigin` and `secure=false` for local.

- .env.local (new) and .env.example (new)
	- `VITE_API_BASE_URL=http://localhost:8000`
	- `VITE_OPENAPI_URL=${VITE_API_BASE_URL}/openapi.json` (documented; optional for script convenience).
	- `VITE_DEV_USER_ID=alice@example.com` (optional; used to send `X-User-Id` header in dev)

- src/api/generated.ts (new, generated)
	- Types produced by openapi-typescript.

- src/services/http.ts (new)
	- `getApiBaseUrl`, `fetchJson<T>`, `withEtag`, `withDevUser`, simple error handling.

- src/services/groundTruths.ts, src/services/assignments.ts (new)
	- Implement calls to `/v1/...` endpoints listed above using `fetchJson` and helpers.
	- Add request/response typing from `src/api/generated.ts`.
- src/services/search.ts, src/services/stats.ts
	- Deprecate or adapt to call real API as applicable; remove demo-only URLs and types.

- README.md (optional)
	- Short section: “Generating API Types” and local dev notes.

Note: I won’t edit any code now—this is a plan only.

---

## Function names with purposes

- `getApiBaseUrl(): string`
	- Reads `import.meta.env.VITE_API_BASE_URL` and returns a normalized base for non-proxied scenarios; in dev, prefer relative `/v1` to use Vite proxy.

- `fetchJson<T>(path: string, init?: RequestInit): Promise<T>`
	- Generic JSON fetch wrapper; resolves relative path with base URL if needed, sets headers (JSON, optional `X-User-Id`), throws on non-2xx with parsed error body when possible.

- `withEtag(init: RequestInit, etag: string): RequestInit`
	- Adds `If-Match` header for concurrency when performing updates.

- `withDevUser(init: RequestInit): RequestInit`
	- Adds `X-User-Id` header when `VITE_DEV_USER_ID` is set (dev-only helper).

- `listGroundTruths(datasetName: string, status?: GroundTruthStatus): Promise<GroundTruthItem[]>`
	- Calls `GET /v1/ground-truths/{datasetName}` with optional `status`.

- `importGroundTruths(items: GroundTruthItem[]): Promise<void>`
	- Calls `POST /v1/ground-truths` to bulk import; handle 409 on duplicates.

	(Removed) direct `updateGroundTruth` helper – use assignments update flow instead.
	- Calls `PUT /v1/ground-truths/{datasetName}/{id}` with `If-Match`.

- `deleteGroundTruth(datasetName: string, id: string): Promise<void>`
	- Calls `DELETE /v1/ground-truths/{datasetName}/{id}`.

- `getStats(): Promise<Stats>`
	- Calls `GET /v1/ground-truths/stats`.

- `createSnapshot(): Promise<SnapshotManifest | void>`
	- Calls `POST /v1/ground-truths/snapshot` and returns manifest if provided.

- `getAssignedGroundTruths(): Promise<GroundTruthItem[]>`
	- Calls `GET /v1/assigned-ground-truths` (sends `X-User-Id` in dev).

- `requestAssignmentsSelfServe(limit: number): Promise<AssignmentDocument[]>`
	- Calls `POST /v1/assignments/self-serve`.

- `getMyAssignments(): Promise<AssignmentDocument[]>`
	- Calls `GET /v1/assignments/my`.

- `updateAssignedGroundTruth(itemId: string, body: { approve?: boolean; answer?: string }): Promise<GroundTruthItem>`
	- Calls `PUT /v1/assigned-ground-truths/{item_id}`.

- `mapApiErrorToMessage(err: unknown): string`
	- Converts fetch/HTTP errors (status + backend error shape) to concise UI messages.

Note: Replace endpoint paths and names with the actual operations from your generated OpenAPI types; for example, use `paths['/v1/ground-truths/{datasetName}']['get']` for request/response typing when needed, and `components['schemas']` for shared models like `GroundTruthItem`, `Stats`, and `AssignmentDocument`.

---

## Test names and behaviors to cover

- generates types from local OpenAPI URL
	- Running script outputs file without errors.

- uses Vite proxy for /v1 during dev
	- Requests to `/v1` route to localhost:8000.

- getApiBaseUrl prefers relative /v1 in dev
	- Avoids hard-coded localhost in browser code.

- fetchJson returns typed body on 2xx
	- Parses JSON and respects generic type.

- fetchJson throws on non-2xx with details
	- Includes status and backend-provided error fields.

- listGroundTruths filters by status and parses response
	- Uses generated request/response types correctly.

- updates use ETag concurrency via If-Match
	- Sends `If-Match` header and handles 412 on mismatch.

- assignments endpoints send X-User-Id in dev
	- Header is present when `VITE_DEV_USER_ID` is set.

- types regeneration is deterministic (no drift)
	- Re-run generation yields identical file.

---

## Minimal command examples (for docs; not executed here)

- Local types generation:

	```bash
	npm run api:types
	# Or
	npx openapi-typescript http://localhost:8000/openapi.json -o src/api/generated.ts
	```

- Dev server:

	```bash
	npm run dev
	```

---

## Assumptions

- OpenAPI spec available at http://localhost:8000/openapi.json (adjustable via `VITE_OPENAPI_URL`).
- Service endpoints are reachable under `/v1/...` or can be proxied to it (dev proxy maps `/v1` → backend root). If your backend changes `API_PREFIX`, adjust the proxy and paths accordingly.
- We’ll keep existing domain models; OpenAPI types will be used for transport (request/response) shapes in the service layer only.

---

## Requirements coverage

- Connect to backend at localhost:8000: planned via Vite proxy and env base URL. Done (plan).
- Leverage OpenAPI to generate TS models: openapi-typescript + script + generated file. Done (plan).
- Identify files to change: listed above with reasons. Done (plan).
- Only needed functionality: types-only generation and minimal HTTP helper; no client codegen. Done (plan).
- Overview, function names, and tests: provided above. Done (plan).