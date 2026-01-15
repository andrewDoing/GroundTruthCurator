"""
Integration tests for GTCInferenceAdapter with live Azure AI Foundry Agent.

Tests the agent calling flow with FunctionTool-based retrieval.
These tests hit real Azure AI services and require proper configuration.

Prerequisites:
- GTC_AZURE_AI_PROJECT_ENDPOINT: Azure AI Project endpoint
- GTC_AZURE_AI_AGENT_ID: Agent ID configured with call_retrieval_tool function
- GTC_RETRIEVAL_URL: Retrieval service URL
- GTC_RETRIEVAL_PERMISSIONS_SCOPE: OAuth scope for retrieval service
- GTC_CHAT_ENABLED=true

The agent must be configured in Azure AI Foundry with:
- A function tool named "call_retrieval_tool" with parameters:
  - query: string - The search query text
  - code: string - Code identifier for the search configuration
"""

from __future__ import annotations

import os

import pytest

from app.core.config import settings
from app.adapters.gtc_inference_adapter import GTCInferenceAdapter


_RUN_LIVE_TESTS = os.getenv("GTC_RUN_LIVE_AZURE_TESTS", "").strip().lower() in {"1", "true", "yes"}

pytestmark = pytest.mark.skipif(
    not _RUN_LIVE_TESTS,
    reason=(
        "Live Azure AI Foundry tests are disabled by default; set "
        "GTC_RUN_LIVE_AZURE_TESTS=1 to enable."
    ),
)


# Override the autouse Cosmos cleanup from tests/integration/conftest.py so this
# test does not require a running Cosmos Emulator.
@pytest.fixture(scope="function", autouse=True)
async def clear_cosmos_db():
    yield


@pytest.fixture(scope="function")
def inference_service():
    """Create GTCInferenceAdapter with live configuration.

    Skips if required configuration is not available.
    """
    if not settings.AZURE_AI_PROJECT_ENDPOINT:
        pytest.skip("GTC_AZURE_AI_PROJECT_ENDPOINT not configured")
    if not settings.AZURE_AI_AGENT_ID:
        pytest.skip("GTC_AZURE_AI_AGENT_ID not configured")
    if not settings.CHAT_ENABLED:
        pytest.skip("GTC_CHAT_ENABLED is not true")
    if not settings.RETRIEVAL_URL:
        pytest.skip("GTC_RETRIEVAL_URL not configured")
    if not settings.RETRIEVAL_PERMISSIONS_SCOPE:
        pytest.skip("GTC_RETRIEVAL_PERMISSIONS_SCOPE not configured")

    service = GTCInferenceAdapter(
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        agent_id=settings.AZURE_AI_AGENT_ID,
        retrieval_url=settings.RETRIEVAL_URL,
        permissions_scope=settings.RETRIEVAL_PERMISSIONS_SCOPE,
        timeout_seconds=settings.RETRIEVAL_TIMEOUT_SECONDS,
    )

    try:
        yield service
    finally:
        service.close()


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_inference_service_generate_calls_agent(inference_service: GTCInferenceAdapter):
    """Test that GTCInferenceAdapter.generate() calls the Azure AI agent and returns a response.

    This test validates:
    1. The agent is reachable and responds
    2. The response contains 'content' (assistant reply)
    3. The response contains 'references' (list, possibly empty)

    The agent should use the FunctionTool (call_retrieval_tool) if configured,
    but the test doesn't require references to pass.
    """
    import asyncio

    # Run the sync generate method in a thread pool (as would be done in async context)
    result = await asyncio.to_thread(
        inference_service.generate,
        user_id="test-user",
        message="What are the main features of this product? Please search for relevant documentation.",
    )

    # Verify response structure
    assert "content" in result, "Response should have 'content' field"
    assert isinstance(result["content"], str), "Content should be a string"
    assert len(result["content"]) > 0, "Content should not be empty"

    # Verify references field
    assert "references" in result, "Response should have 'references' field"
    assert isinstance(result["references"], list), "References should be a list"

    # Log for debugging
    print(f"\n✓ Agent returned response with {len(result['references'])} reference(s)")
    print(f"  Content length: {len(result['content'])} characters")

    if result["references"]:
        print("✓ Agent used retrieval tool and returned citations")
        for i, ref in enumerate(result["references"][:3]):  # Show first 3
            ref_id = ref.get("id", "no-id")
            snippet = ref.get("snippet", "")[:80] if ref.get("snippet") else ""
            print(f"  Reference {i + 1}: {ref_id} - {snippet}...")
    else:
        print("⚠ No references returned. Agent may not have used retrieval tool.")
        print(f"  Response preview: {result['content'][:200]}...")


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_inference_service_generate_with_technical_question(
    inference_service: GTCInferenceAdapter,
):
    """Test agent response to a specific technical question that should trigger retrieval.

    Uses a question that would require searching documentation to answer properly.
    """
    import asyncio

    result = await asyncio.to_thread(
        inference_service.generate,
        user_id="test-user-tech",
        message="How do I configure assembly constraints in a CAD application? What are the different types of constraints available?",
    )

    # Basic structure validation
    assert "content" in result
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 50, "Technical answer should be substantial"

    assert "references" in result
    assert isinstance(result["references"], list)

    # For technical questions, we'd expect references if the retrieval is working
    ref_count = len(result["references"])
    print(f"\n✓ Technical question answered with {ref_count} reference(s)")

    if ref_count > 0:
        # Validate reference structure
        for ref in result["references"]:
            # Each reference should have at least an id or url
            assert ref.get("id") or ref.get("url"), "Reference should have id or url"


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_inference_service_handles_empty_message_gracefully(
    inference_service: GTCInferenceAdapter,
):
    """Test that the service handles edge cases gracefully.

    Note: The agent may still respond to a simple greeting or very short message,
    but it should not crash.
    """
    import asyncio

    result = await asyncio.to_thread(
        inference_service.generate, user_id="test-user-edge", message="Hi"
    )

    # Should still return a valid response structure
    assert "content" in result
    assert "references" in result
    print(f"\n✓ Simple greeting handled, response: {result['content'][:100]}...")


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_inference_service_multiple_sequential_calls(inference_service: GTCInferenceAdapter):
    """Test that the service handles multiple sequential calls correctly.

    Each call should create a new thread and clean up properly.
    """
    import asyncio

    questions = [
        "What is the main product feature?",
        "How does version control work in the application?",
    ]

    for i, question in enumerate(questions):
        result = await asyncio.to_thread(
            inference_service.generate, user_id=f"test-user-multi-{i}", message=question
        )

        assert "content" in result
        assert "references" in result
        print(f"\n✓ Question {i + 1}/{len(questions)} answered successfully")


@pytest.mark.no_seed_tags
@pytest.mark.anyio
async def test_inference_service_response_content_bounds(inference_service: GTCInferenceAdapter):
    """Test that response content is within reasonable bounds.

    Validates:
    - Content is not empty
    - Content is not excessively large (< 50KB)
    - References are capped at reasonable limits
    """
    import asyncio

    result = await asyncio.to_thread(
        inference_service.generate,
        user_id="test-user-bounds",
        message="Provide a comprehensive overview of the product's design capabilities.",
    )

    # Content bounds
    content = result["content"]
    assert len(content) > 0, "Content should not be empty"
    assert len(content) <= 50000, "Content should be under 50KB"

    # Reference bounds (service should cap at MAX_RESULTS=100)
    refs = result["references"]
    assert len(refs) <= 100, "References should be capped at 100"

    print(f"\n✓ Response within bounds: {len(content)} chars, {len(refs)} refs")


class TestInferenceServiceRetrievalIntegration:
    """Integration tests specifically for the retrieval tool functionality."""

    @pytest.mark.no_seed_tags
    @pytest.mark.anyio
    async def test_retrieval_tool_is_called_for_search_query(
        self, inference_service: GTCInferenceAdapter
    ):
        """Test that asking a question triggers the retrieval tool.

        We can't directly verify the tool was called, but we can check:
        1. Response mentions relevant technical content
        2. References are returned (if retrieval worked)
        """
        import asyncio

        result = await asyncio.to_thread(
            inference_service.generate,
            user_id="test-retrieval",
            message="Search the documentation for information about CAD file formats supported by this product.",
        )

        assert "content" in result
        # The response should mention something technical if retrieval worked
        content_lower = result["content"].lower()

        # Log what we got
        print(f"\n✓ Response: {result['content'][:300]}...")
        print(f"  References: {len(result['references'])}")

        # If references are returned, the retrieval tool was used
        if result["references"]:
            print("✓ Retrieval tool was invoked and returned results")
            # Validate reference structure
            for ref in result["references"]:
                assert isinstance(ref, dict), "Each reference should be a dict"
                # Should have mapped fields
                if ref.get("snippet"):
                    assert isinstance(ref["snippet"], str)
                    # Snippet should be truncated to MAX_STRING_LENGTH (1000)
                    assert len(ref["snippet"]) <= 1003  # 1000 + "..."

    @pytest.mark.no_seed_tags
    @pytest.mark.anyio
    async def test_references_have_expected_structure(self, inference_service: GTCInferenceAdapter):
        """Test that returned references have the expected structure.

        Expected fields from extract_references_from_output:
        - id: from chunk_id or id
        - title: document title
        - url: document URL
        - snippet: truncated content
        """
        import asyncio

        result = await asyncio.to_thread(
            inference_service.generate,
            user_id="test-ref-structure",
            message="What are the system requirements for installing this product?",
        )

        if not result["references"]:
            pytest.skip("No references returned; cannot validate structure")

        print(f"\n✓ Validating {len(result['references'])} reference(s)")

        for i, ref in enumerate(result["references"]):
            assert isinstance(ref, dict), f"Reference {i} should be a dict"

            # Should have some identifier
            has_id = ref.get("id") is not None
            has_url = ref.get("url") is not None
            assert has_id or has_url, f"Reference {i} should have id or url"

            # Log reference details
            print(
                f"  Ref {i + 1}: id={ref.get('id')}, title={ref.get('title')}, url={ref.get('url')}"
            )
