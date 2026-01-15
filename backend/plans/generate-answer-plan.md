# Generate Answer API — Azure Foundry plan

## Short overview
- Add a minimal POST /v1/generate-answer endpoint that accepts a question and a set of references, calls an LLM hosted in Azure AI Foundry, and returns a single answer string.
- Keep scope tight: no retrieval, no history/multi-turn, no citations formatting in the response (answer string only), no provider fallback.
- Wire via a small LLM adapter interface, a concrete Azure Foundry implementation, and a thin service that builds a prompt/messages from inputs.

## What we will implement now (only what’s needed)
- HTTP API: POST /v1/generate-answer with body { question: string; references: ReferenceInput[] } → returns { answer: string }.
- Validation: require non-empty question; allow 0..N references with guardrails on count/size (basic bounds/checks).
- Service: build a compact system+user message set using the question and summarized references; call adapter; return the model’s text.
- Adapter: minimal Azure Foundry chat completions REST call using deployment name and API version; parse first choice text.
- Config: add only the few required env vars for endpoint, deployment, api-version, and key; defer MSI/token auth until later.
- No legacy fallbacks, no streaming, no tool-calls, no citations in output.

## API contract (MVP)
- Method/Path: POST /v1/generate-answer
- Request JSON:
  - question: string (required, non-empty)
  - references: Array<{ url: string; keyExcerpt?: string | null; content?: string | null; type?: string | null }>
- Response JSON: { answer: string }
- Errors: 422 for validation errors; 502 if the LLM provider errors/timeouts.

## Files to change / add
- app/api/v1/router.py — include new router for answers endpoint (prefix="", tags=["answers"]).
- app/api/v1/answers.py — new router and request/response DTOs; defines POST /generate-answer.
- app/services/llm_service.py — add real orchestration method that builds messages/prompt and calls adapter (replace stub or extend without breaking changes).
- app/adapters/llm/base.py — new protocol for LLMAdapter: generate from messages; minimal surface.
- app/adapters/llm/azure_foundry.py — concrete adapter calling Azure AI Foundry Chat Completions REST API.
- app/container.py — wire LLM service and set the Azure Foundry adapter based on settings; light init function.
- app/core/config.py — add GTC_AZ_FOUNDRY_* settings (endpoint, deployment, api version, api key) and LLM toggle; defaults safe for dev.
- tests/unit/test_generate_answer_endpoint.py — endpoint validation and happy-path using a fake adapter.
- tests/unit/test_llm_service_prompt.py — service builds messages correctly; truncation/limits respected.
- tests/unit/test_azure_foundry_llm_adapter.py — request formation, header/auth, response parsing, non-2xx handling.

## Function/class names and purposes
- app/api/v1/answers.py
  - class GenerateAnswerRequest(BaseModel): Defines request payload: question and references with minimal fields.
  - class GenerateAnswerResponse(BaseModel): Defines response payload with single field `answer`.
  - async def generate_answer(body: GenerateAnswerRequest, user=Depends(get_current_user)) -> GenerateAnswerResponse: Validates inputs, calls service, returns answer.

- app/services/llm_service.py
  - class LLMService:
    - async def generate_answer(self, *, question: str, references: list[Reference], max_context_chars: int = 4000) -> str: Build compact messages from question + summarized refs, call adapter, return answer text; truncate context to budget. Use datetime.now(timezone.utc) for any timestamps.
    - def _build_messages(self, question: str, references: list[Reference], max_context_chars: int) -> list[dict]: Create system and user messages; include reference snippets up to limit.

- app/adapters/llm/base.py
  - class LLMAdapter(Protocol): async def chat(self, messages: list[dict], *, max_tokens: int | None = None, temperature: float | None = None) -> str: Generic chat completion entrypoint; returns first completion text.

- app/adapters/llm/azure_foundry.py
  - class AzureFoundryLLMAdapter(LLMAdapter): Concrete adapter for Azure AI Foundry chat completions.
  - async def chat(self, messages: list[dict], *, max_tokens: int | None = None, temperature: float | None = None) -> str: POST to {endpoint}/openai/deployments/{deployment}/chat/completions?api-version={version}; return first message.content.
  - def _build_request(self, messages, max_tokens, temperature) -> (url, headers, params, body): Helper to construct REST call with key header and payload.
  - def _parse_answer(self, data: dict) -> str: Extract the first choice message content, or empty string on absence.

- app/container.py
  - def init_llm(self) -> None: Instantiate AzureFoundryLLMAdapter using settings and assign to llm_service.

- app/core/config.py
  - class Settings(BaseSettings): Add fields GTC_AZ_FOUNDRY_ENDPOINT, GTC_AZ_FOUNDRY_DEPLOYMENT, GTC_AZ_FOUNDRY_API_VERSION (default stable), GTC_AZ_FOUNDRY_KEY; optional LLM enabled flag.

## Tests (names and brief behaviors)
- tests/unit/test_generate_answer_endpoint.py
  - test_requires_question_field: 422 when question missing or empty.
  - test_accepts_optional_references_array: empty refs allowed, still succeeds.
  - test_returns_answer_string: happy path; fake adapter returns fixed text.
  - test_backend_error_maps_to_502: adapter raises → 502 from API.
  - test_rejects_oversized_payload: too many/large refs → 422.

- tests/unit/test_llm_service_prompt.py
  - test_messages_include_question_and_refs: system+user contain question and snippets.
  - test_truncates_context_to_budget: references content concatenation limited to budget.
  - test_omits_unknown_ref_fields: only url/keyExcerpt/content are included.
  - test_passes_through_temperature_tokens: optional knobs forwarded to adapter.

- tests/unit/test_azure_foundry_llm_adapter.py
  - test_builds_correct_request_shape: path, headers, api-version, body with messages.
  - test_parses_first_choice_text: extracts answer from choices[0].message.content.
  - test_handles_non_2xx_responses: raises with status/message for 4xx/5xx.
  - test_timeout_surface_as_error: client timeout → raised error handled by API 502.

## Constraints and assumptions
- Authentication/authorization mirrors existing pattern via get_current_user; no special roles or quotas yet.
- Reference input shape mirrors existing Reference model fields; content/keyExcerpt are optional and may be short.
- Basic bounds (e.g., max 20 refs, max 1k chars per ref processed) prevent oversized prompts; exact thresholds can be tuned in settings.
- Logging redacts secrets and large payloads; do not log full prompts or provider responses.

## Azure Foundry specifics (kept minimal)
- Use REST chat completions endpoint with deployment scoped to a single model; authenticate via api-key header.
- Add short timeouts and a single retry on transient 5xx; no exponential/backoff complexity for MVP.
- Prefer server-side max_tokens and temperature defaults if not provided; surface small knobs via service if needed later.

## Out of scope (explicitly not included now)
- Provider fallback (e.g., OpenAI, Azure OpenAI alternate deployments) — not included.
- Streaming responses, tool calls, function calling — not included.
- Citation markup or rich answer formatting — answer is plain text only.
- Prompt caching, safety filters, or moderation API — not included.

## Implementation notes (order of work)
1) Add DTOs and router in app/api/v1/answers.py; mount router in api/v1/router.py.
2) Extend LLMService with generate_answer and _build_messages.
3) Implement LLMAdapter protocol and AzureFoundryLLMAdapter with httpx.
4) Wire settings and container.init_llm to inject adapter into service.
5) Write unit tests (endpoint, service, adapter); run unit tests and mypy.

## Acceptance criteria
- POST /v1/generate-answer accepts valid payloads and returns { answer }.
- Empty or missing question returns 422; provider errors return 502.
- Service trims context to budget and includes at least url/keyExcerpt in prompt.
- Adapter sends correctly formed request and parses answer text.