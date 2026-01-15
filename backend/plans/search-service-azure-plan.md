# Azure AI Search service plan

Short overview
- Add a minimal, production-ready search path that queries Azure AI Search and returns only `url` and `title` fields.
- Expose a new FastAPI endpoint `GET /v1/search` that delegates to a thin service wired via the existing `container`.
- Implement a new adapter for Azure AI Search that performs the HTTP query and maps results to a lean response schema.
- Keep scope tight: no legacy fallbacks, no content/embeddings, no pagination unless trivial, no write paths.

What we will implement now
- Only the functionality required to serve `GET /v1/search?q=...` and respond with a list of results where each item has `{ url, title }`.
- Parameter(s): `q` (string, required), optional `top` (int, default 5) to constrain results.
- Auth: reuse the app’s existing auth middleware strategy; if none enforced on other simple endpoints, mirror that level.

Files to change / add
- app/api/v1/router.py: include the new router module for search endpoints.
- app/api/v1/search.py: new router exposing `GET /search`.
- app/adapters/search/azure_ai_search.py: new adapter to call Azure AI Search REST API.
- app/services/search_service.py: add a query method that uses the configured search adapter to fetch results (non-breaking, preserve existing attach/detach methods).
- app/container.py: wire `search_service` with Azure adapter and configuration.
- app/core/config.py: add Azure AI Search settings (endpoint, index name, api key or MSI toggle, api version, fields).
- tests/unit/test_search_endpoint.py: unit tests for API contract and field filtering.
- tests/unit/test_azure_search_adapter.py: unit tests for adapter mapping and query string formation.

Functions and purposes
- app/api/v1/search.py
  - router.get("/search") -> search(): Accepts query params `q`, `top`; calls service; returns list of `{url, title}`.
- app/services/search_service.py
  - async def query(self, q: str, top: int = 5) -> list[dict]: Delegates to search adapter; ensures field filtering and stable shape.
- app/adapters/search/azure_ai_search.py
  - class AzureAISearchAdapter(SearchAdapter): Concrete adapter for Azure AI Search.
  - async def query(self, q: str, top: int = 5) -> list[dict]: Calls Azure REST API with select=URL,TITLE, parses hits, returns mapped list.
  - _build_request(self, q: str, top: int) -> (url, headers, params): Helper to construct request.
  - _map_hit(self, hit: dict) -> dict: Extracts `{url, title}` from a single result; ignores extras.
- app/container.py
  - def init_search(self): Configures and assigns the chosen search adapter (Azure now) to search_service.
- app/core/config.py
  - Add fields: `AZ_SEARCH_ENDPOINT`, `AZ_SEARCH_INDEX`, `AZ_SEARCH_KEY` (dev only), `AZ_SEARCH_API_VERSION` (default), `AZ_SEARCH_USE_MSI` (bool). Keep names `GTC_*` env-prefixed.

API contract
- Method: GET
- Path: /v1/search
- Query params: q (required), top (optional, default 5, 1-50 bound)
- Response: 200 OK, body: `{ "results": [ { "url": str, "title": str | null } ] }`
- Errors: 400 for missing q or invalid top; 502 for Azure search errors.

Test names and behaviors
- tests/unit/test_search_endpoint.py
  - test_search_requires_q: 400 when q missing
  - test_search_returns_only_url_title: strips extra fields
  - test_search_top_default_and_bounds: default=5, clamps to 50
  - test_search_propagates_backend_error_as_502: adapter error -> 502
- tests/unit/test_azure_search_adapter.py
  - test_builds_correct_request_params: q, top, select fields
  - test_maps_hits_to_url_title: hit mapping extracts expected fields
  - test_gracefully_handles_missing_title: title may be absent/null

Edge cases considered
- Empty results -> `results: []`.
- Some hits missing `title` -> return `title: null`.
- Non-2xx from Azure -> raise adapter error; API translates to 502.
- top too large/small -> bound to [1, 50].

Notes
- We intentionally do not implement legacy fallback adapters or embeddings.
- MSI vs API key: for dev, accept key; for prod, prefer MSI token in future work.
