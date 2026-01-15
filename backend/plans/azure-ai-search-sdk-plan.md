## Ultra-Minimal Plan: Azure AI Search SDK Swap

Goal: Keep the existing adapter interface (`async query(q, top=5) -> list[dict]`) but replace the manual REST + `httpx` call with the official SDK so we stop hand-crafting requests. Nothing else changes.

### Change ONLY One File
`app/adapters/search/azure_ai_search.py`

### Minimal Implementation Steps
1. Remove: `httpx`, `_build_request`, `_auth_headers`, and `SearchIndexClient` usage.
2. Add imports: `SearchClient` (async), `AzureKeyCredential` (only if api_key), `HttpResponseError`.
3. In `__init__`: choose credential (api key -> `AzureKeyCredential`; else provided token; else `DefaultAzureCredential()`), build `SearchClient` and store as `self.client`.
4. In `query`: clamp `top` to 1–50, run `results = await self.client.search(search_text=q, top=top)`, iterate async results, coerce each to `dict(...)` if needed, return list. Wrap `HttpResponseError` -> `RuntimeError("Azure Search error <status>: <message>")`.

### Functions (Only What We Need)
* `__init__(...)`: set up credential + `SearchClient`.
* `async query(q: str, top: int = 5)`: perform search and return raw hit dicts.

No helpers, no extra abstraction, no new classes.

### Assumptions
* SDK result objects are dict-like; `dict(r)` will work for now.
* No need to alter downstream code because return type unchanged.
* Leaving dependency cleanup (removing `httpx` from project) for later.

### Done When
* Adapter compiles, tests above pass, and no other code required edits.

That’s it—no extra layers, no future-planning code.
