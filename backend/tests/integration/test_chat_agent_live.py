from __future__ import annotations

from typing import cast

import pytest
from httpx import AsyncClient
from httpx import ASGITransport

from app.core.config import settings
from app.main import create_app


# Override the autouse Cosmos cleanup from tests/integration/conftest.py so this
# test does not require a running Cosmos Emulator just to exercise the agent.
@pytest.fixture(scope="function", autouse=True)
async def clear_cosmos_db():
    yield


# Provide a local async_client that doesn't depend on the Cosmos-backed app fixture.
@pytest.fixture(scope="function")
async def async_client():
    app = create_app()
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield client
    finally:
        try:
            await client.aclose()
        finally:
            try:
                await transport.aclose()
            except Exception:
                pass


@pytest.mark.no_seed_tags
@pytest.mark.requires_chat
@pytest.mark.anyio
async def test_chat_endpoint_hits_azure_ai_agent(
    async_client: AsyncClient, user_headers: dict[str, str]
):
    """End-to-end call that hits the configured Azure AI Foundry Agent Service.

    This test will be skipped unless the integration environment provides
    valid Azure AI Foundry agent settings and the chat feature is enabled.

    Tests that the agent can respond to questions and validates the response structure.

    CITATIONS/REFERENCES:
    For the agent to return citations, it must be configured in Azure AI Foundry with
    one or more search/grounding tools:

    1. Azure AI Search:
       - Add the "azure_ai_search" tool to the agent
       - Configure connection to an Azure AI Search index
       - Requires the search index to be populated with documents

    2. File Search:
       - Add the "file_search" tool to the agent
       - Upload files to a vector store
       - Attach the vector store to the agent

    3. Bing Grounding:
       - Enable Bing grounding in the agent configuration
       - Requires Bing Search API resource

    Without any of these tools, the agent will respond from its training data
    without citations. The test validates the response structure but does not
    require citations to pass.
    """
    # Ensure Azure AI Foundry agent is configured; otherwise skip gracefully.
    if not (
        settings.AZURE_AI_PROJECT_ENDPOINT and settings.AZURE_AI_AGENT_ID and settings.CHAT_ENABLED
    ):
        pytest.skip(
            "Azure AI Foundry agent not configured; set GTC_AZURE_AI_PROJECT_ENDPOINT, "
            "GTC_AZURE_AI_AGENT_ID, and GTC_CHAT_ENABLED=true"
        )

    # Use a question that would likely trigger a search if the agent has search tools
    # Ask about a specific technical topic that should be in the indexed documents
    r = await async_client.post(
        "/v1/chat",
        json={
            "message": "What are the key features and capabilities of the product? Please provide specific details from the documentation.",
        },
        headers=user_headers,
    )

    # If Azure AI credentials are invalid or the service is unreachable, the API maps
    # adapter errors to 502 or 503. Treat that as a skip so CI without creds doesn't fail.
    if r.status_code in (502, 503):
        pytest.skip("Azure AI Foundry agent not reachable or unauthorized; skipping live test")

    assert r.status_code == 200
    body = cast(dict[str, object], r.json())

    # Verify response structure
    assert "content" in body, "Response should have 'content' field"
    assert isinstance(body["content"], str), "Content should be a string"
    assert len(body["content"]) > 0, "Content should not be empty"

    # Sanity bound: ensure content isn't outrageously large
    assert len(cast(str, body["content"])) <= 50000, "Content should be under 50k characters"

    # Verify references field exists
    assert "references" in body, "Response should have 'references' field"
    assert isinstance(body["references"], list), "References should be a list"

    # Log reference count for debugging
    ref_count = len(body["references"])
    print(f"\n✓ Agent returned {ref_count} reference(s)")

    # If there are references, validate their structure
    if ref_count > 0:
        print("✓ Agent has search tools enabled and returned citations")
        for i, ref in enumerate(body["references"]):
            assert isinstance(ref, dict), f"Reference {i} should be a dict"
            # Validate reference has expected fields
            assert "id" in ref or "url" in ref, f"Reference {i} should have either 'id' or 'url'"
            if ref.get("snippet"):
                print(f"  Reference {i + 1}: {ref.get('snippet', '')[:100]}...")
            elif ref.get("url"):
                print(f"  Reference {i + 1}: {ref.get('url')}")
    else:
        # No references - this could mean:
        # 1. Agent doesn't have search tools enabled
        # 2. Agent chose not to use search for this query
        # 3. Search didn't return results
        print("⚠ Warning: No references returned. This may indicate:")
        print("  - Agent doesn't have search tools (Azure AI Search, file_search, or Bing) enabled")
        print("  - Agent chose not to search for this particular query")
        print("  - Search tools didn't return any relevant documents")
        print(f"\nAgent response preview: {body['content'][:200]}...")

        # Don't fail the test, but print a warning
        # In a real scenario, you'd want to verify with Azure portal that search tools are configured
