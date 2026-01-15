# Plan: Port Chat (Foundry Agent) Functionality into GroundTruthCurator Backend

## Overview
Implement a minimal chat endpoint in GroundTruthCurator (`/v1/chat`) that sends a user message to the agent and returns a single generated response with references found from one search. This is specifically for generating agent responses during ground truth curation - send a user question, get back an AI-generated answer plus the references/citations the agent found during its search. Single synchronous request/response (no streaming, no multi-turn thread management). Just enough to support the curation workflow: question in → answer + references out.

## What We Need (Right Now Only)
- Public FastAPI route under existing versioned router: `POST /v1/chat` (tag: `chat`).
- Request model: `message` (user question, validated + sanitized), optional `context` (application context string).
- Response model: `content` (agent's generated answer), `references` (list of references/citations from the search).
- Service function to invoke agent: accept `user_id`, `message`, optional `context` → returns dict with `content` and `references`.
- Config additions (if missing): agent endpoint/base URL/API key or SDK parameters needed to call the agent.
- Security/auth: require user (reuse `require_user` dependency) and sanitize message to prevent script injection (basic validation).
- No persistence needed - this is a stateless generation endpoint for the curation workflow.

## Files To Add / Modify

1. `app/api/v1/chat.py` (NEW) – Route + Pydantic models + handler.
2. `app/services/chat_service.py` (NEW) – `async generate_response(...)` wrapper that calls agent to get answer + references.
3. `app/adapters/agent_client.py` (NEW, minimal) – Encapsulate outbound call to agent (HTTP or SDK). Start with placeholder that raises if not configured or returns mock response in dev.
4. `app/core/config.py` (MODIFY) – Add settings: `CHAT_ENABLED: bool = True`, `AGENT_ENDPOINT: str | None`, `AGENT_API_KEY: str | None` (or whatever params needed to call agent).
5. `app/container.py` (MODIFY) – Wire `agent_client` and expose via container for service.
6. `tests/api/test_chat.py` (NEW) – API tests for chat route behavior.
7. `tests/services/test_chat_service.py` (NEW) – Unit test for `generate_response` producing expected dict shape with mock agent client.
8. `tests/adapters/test_agent_client.py` (NEW) – Minimal test ensuring behavior for configured vs unconfigured state.
9. `plans/gtc-chat-port-plan.md` (THIS PLAN) – Document plan.

## Minimal Data / Object Shapes

Agent response dict (service return):

```json
{
  "content": "The generated answer from the agent",
  "references": [
    {
      "id": "ref-1",
      "title": "Document Title",
      "url": "https://example.com/doc",
      "snippet": "Preview text...",
      "keyParagraph": "The most relevant paragraph..."
    }
  ]
}
```

Reference object minimal fields:
- `id` - unique identifier
- `title` - document title (optional)
- `url` - source URL
- `snippet` - preview/excerpt (optional)
- `keyParagraph` - most relevant content section (optional)

(Keep flexible - pass through whatever the agent returns)


## Function Definitions (Initial Minimal Set)

- `chat(request: ChatRequest, user=Depends(require_user))` (route) – Validate message, call service, return response.
- `sanitize_message(raw: str) -> str` – Deduplicate whitespace, basic unsafe pattern rejection.
- `async generate_response(user_id: str, message: str, context: str | None) -> dict` – Call agent to generate answer + references; return dict with `content` and `references`.
- `class AgentClient:`
  - `async def generate(self, *, user_id: str, message: str, context: str | None) -> dict` – Outbound call to agent endpoint; returns parsed response with answer and references from search.

## Test Names & Purpose

- `test_chat_rejects_empty_message` – Whitespace-only message returns 422 / validation error.
- `test_chat_rejects_suspicious_content` – `<script>` triggers validation error.
- `test_chat_returns_expected_fields` – Happy path contains `content` and `references`.
- `test_generate_response_mock_fallback` – Service returns mock structure when no agent configured.
- `test_generate_response_passes_through_agent_response` – With fake agent client response.
- `test_agent_client_raises_when_no_endpoint` – Proper exception on misconfiguration.
- `test_agent_client_success_parses_json` – Returns structured dict with content and references.

## Configuration Additions

Environment variables (mapped in settings):
- `CHAT_ENABLED` (default true)
- `AGENT_ENDPOINT` (required for production - URL to agent service)
- `AGENT_API_KEY` (optional secret for auth)

## Simplifications (Intentional)

- No streaming or SSE.
- No multi-turn thread state - stateless single Q&A generation.
- No step tracking or persistence - just get the final answer and references.
- Minimal schema; pass through references list as-is from agent.
- Agent client pluggable later; start with basic HTTP call or mock.

## Edge Cases Considered

- Missing agent configuration (fallback mock so UI can integrate early).
- Malformed JSON from agent (return 502 style error translated to 500 minimal; log parse failure).
- Oversized message (Pydantic max_length enforced).
- Suspicious content rejection.

## Incremental Implementation Order

1. Config + container wiring (feature flag & client).
2. Adapter + service (mock fallback).
3. Route + models.
4. Tests (service + route + adapter).

## Implementation Status

✅ **COMPLETED** - All features implemented and tested using Azure AI Foundry Agent Service.

### Changes Made

1. **Configuration** (`app/core/config.py`)
   - Added `CHAT_ENABLED: bool = True`
   - Added `AZURE_AI_PROJECT_ENDPOINT: str | None` - Azure AI Foundry project endpoint
   - Added `AZURE_AI_AGENT_ID: str | None` - Agent/assistant ID from Azure AI Foundry
   - Added `AGENT_TIMEOUT_SECONDS: int = 30`
   - Added `STORE_AGENT_STEPS: bool = False`
   - **Uses DefaultAzureCredential** for Azure AI authentication

2. **Agent Client** (`app/adapters/agent_client.py`)
   - Uses Azure AI Projects SDK (`azure-ai-projects`) with async client
   - Authenticates via `DefaultAzureCredential` 
   - Creates thread, sends message, runs agent via `create_and_process`
   - Extracts assistant response and references from run steps
   - Returns `{"content": str, "references": list}`
   - Raises `RuntimeError` when not configured or on failures

3. **Chat Service** (`app/services/chat_service.py`)
   - Orchestrates agent calls and optional step persistence
   - Falls back to mock response when agent not configured
   - Sanitizes and validates messages
   - Optional integration with `AgentStepsStore` for tracing

4. **API Route** (`app/api/v1/chat.py`)
   - `POST /v1/chat` endpoint
   - Request: `{message: str, context?: str}`
   - Response: `{content: str, references: list}`
   - Validates message (1-2000 chars, rejects `<script>` tags)
   - Returns 503 when `CHAT_ENABLED=False`
   - Returns 422 for validation errors
   - Returns 502 for agent failures

5. **Container Wiring** (`app/container.py`, `app/main.py`)
   - `init_chat()` method creates credential and wires services
   - Called during app startup after LLM initialization

6. **Tests**
   - `test_chat_endpoint.py` - API route validation and responses
   - `test_chat_service.py` - Service logic and mock fallback
   - `test_agent_client.py` - Agent client configuration validation
   - `test_chat_agent_live.py` - Integration test that calls real Azure AI Foundry agent

### Azure AI Foundry Agent Service Integration

The implementation uses the **Azure AI Projects SDK** to interact with Azure AI Foundry Agent Service:

1. **AIProjectClient** - Connects to Azure AI Foundry project endpoint
2. **Agent Operations** - Via `project_client.agents`:
   - `threads.create()` - Creates conversation thread
   - `messages.create()` - Adds user message
   - `runs.create_and_process()` - Executes agent and waits for completion
   - `messages.list()` - Retrieves assistant responses
   - `run_steps.list()` - Extracts references/citations from tool calls

### Authentication Flow

When configured:
1. Container creates `DefaultAzureCredential` instance
2. Agent client receives credential and project/agent config
3. On each request, `AIProjectClient` uses credential for authentication
4. Agent service executes using the specified assistant ID
5. Results and references returned to client

When not configured:
- Chat service returns mock responses for development/testing

### Configuration

**Environment Variables:**

```bash
# Required for production
GTC_AZURE_AI_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
GTC_AZURE_AI_AGENT_ID=asst_<agent_id>

# Optional
GTC_CHAT_ENABLED=true
```

**Example from Azure AI Foundry:**
- Project endpoint: Found in project Overview page
- Agent ID: Found in Agents section (assistant ID starting with `asst_`)

### Authentication Options

DefaultAzureCredential automatically tries (in order):
1. **Environment variables** - `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
2. **Managed Identity** - In Azure (Container Apps, VMs, etc.)
3. **Azure CLI** - Locally via `az login`
4. **VS Code** - Azure Account extension
5. **Azure PowerShell** - Locally logged in

---

## Acceptance Criteria

✅ POST /v1/chat returns 200 with expected JSON structure (`content` + `references`) when in mock mode.
✅ Validation & rejection cases covered by tests.
✅ Feature protected by `CHAT_ENABLED` (route returns 503 if disabled).
✅ No unhandled exceptions bubble (except FastAPI 500 with generic msg).
✅ Uses DefaultAzureCredential for Azure AI authentication.
✅ Integrates with Azure AI Foundry Agent Service using official SDK.

---

## Future (Out of Scope Now)

- Streaming responses.
- Multi-turn thread persistence and conversation management.
- Advanced auth-based rate limiting.
- Retry / circuit breaker patterns.
- Step-by-step execution tracking.

