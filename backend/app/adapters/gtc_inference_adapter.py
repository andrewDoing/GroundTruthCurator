"""
GTC Inference Adapter - wraps test-client's InferenceService for GTC's simplified interface.

This adapter provides a shim layer between:
- GTC's ChatService which expects: generate(user_id, message) -> {content, references}
- test-client's InferenceService which expects: process_inference_request(history, bus) -> {response_text, calls, ...}

The underlying inference.py from test-client remains UNCHANGED.
"""

from __future__ import annotations

import logging
from typing import Any

from azure.identity import DefaultAzureCredential

from app.adapters.inference import (
    EventBus,
    InferenceService,
    ConversationTurn,
)

logger = logging.getLogger(__name__)

# Limits for reference extraction (matching original inference_service.py)
MAX_RESULTS = 100
MAX_STRING_LENGTH = 1000  # For content/title fields


class GTCInferenceAdapter:
    """
    Adapter that wraps test-client's InferenceService for GTC's simplified interface.

    This adapter:
    - Converts GTC's (user_id, message) input to ConversationTurn history
    - Creates a no-op EventBus (with optional logging handlers)
    - Calls the underlying InferenceService.process_inference_request()
    - Converts the response {response_text, calls} to GTC's {content, references}
    """

    def __init__(
        self,
        *,
        project_endpoint: str,
        agent_id: str,
        retrieval_url: str,
        permissions_scope: str,
        timeout_seconds: int = 30,
        credential: DefaultAzureCredential | None = None,
    ) -> None:
        """
        Initialize the GTC Inference Adapter.

        Args:
            project_endpoint: Azure AI Project endpoint
            agent_id: Azure AI Agent ID
            retrieval_url: URL for the retrieval service
            permissions_scope: OAuth scope for retrieval service authentication
            timeout_seconds: Timeout for HTTP requests (passed to underlying service)
            credential: Optional Azure credential (creates DefaultAzureCredential if None)
        """
        self._project_endpoint = project_endpoint
        self._agent_id = agent_id
        self._retrieval_url = retrieval_url
        self._permissions_scope = permissions_scope
        self._timeout_seconds = timeout_seconds

        # Use provided credential or create new one
        self._credential = credential or DefaultAzureCredential(
            exclude_shared_token_cache_credential=True
        )

        # Create the underlying InferenceService from test-client
        # Note: The test-client's InferenceService doesn't accept timeout_seconds,
        # but the retrieval tool inside uses a hardcoded 30s timeout
        self._inference_service = InferenceService(
            project_endpoint=self._project_endpoint,
            agent_id=self._agent_id,
            retrieval_url=self._retrieval_url,
            permissions_scope=self._permissions_scope,
            client=None,  # Use real client
            logger_override=None,  # Use default logger
        )

        logger.info(
            "GTCInferenceAdapter initialized (endpoint=%s, agent=%s, retrieval_host=%s)",
            self._project_endpoint,
            self._agent_id,
            self._retrieval_url.split("/")[2] if self._retrieval_url else "none",
        )

    def close(self) -> None:
        """Close the underlying inference service."""
        if hasattr(self._inference_service, "_safe_close_client"):
            self._inference_service._safe_close_client()

    def _create_event_bus(self) -> EventBus:
        """Create an EventBus for the inference call."""
        return EventBus()

    def _extract_references(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Extract references from tool call results.

        Converts the 'calls' structure from InferenceService to GTC's 'references' format.
        Each call contains 'results' which are the retrieved documents.

        Args:
            calls: List of tool calls from InferenceService

        Returns:
            List of references in GTC format: {id, title, url, snippet}
        """
        references: list[dict[str, Any]] = []

        for call in calls:
            if not isinstance(call, dict):
                continue

            # Skip calls with errors
            if call.get("error"):
                logger.warning("Skipping call with error: %s", call.get("error"))
                continue

            # Extract results from the call
            results = call.get("results", [])
            for doc in results:
                if not isinstance(doc, dict):
                    continue

                ref = {
                    "id": doc.get("chunk_id") or doc.get("id"),
                    "title": doc.get("title"),
                    "url": doc.get("url"),
                    "snippet": doc.get("content"),  # Map content -> snippet for ChatReference
                }

                # Truncate snippet to prevent excessive data
                if ref["snippet"] and len(ref["snippet"]) > MAX_STRING_LENGTH:
                    ref["snippet"] = ref["snippet"][:MAX_STRING_LENGTH] + "..."

                references.append(ref)

        # Cap total references
        if len(references) > MAX_RESULTS:
            logger.warning(
                "Truncating %d references to %d to prevent resource exhaustion",
                len(references),
                MAX_RESULTS,
            )
            references = references[:MAX_RESULTS]

        return references

    def generate(self, *, user_id: str, message: str) -> dict[str, Any]:
        """
        Generate a response using the Azure AI Foundry Agent.

        This method provides the interface expected by GTC's ChatService.

        Args:
            user_id: User identifier for logging
            message: User's question/message

        Returns:
            Dict with 'content' (assistant reply) and 'references' (list of citations)

        Raises:
            RuntimeError: If agent processing fails
        """
        if not message.strip():
            raise ValueError("message cannot be empty")

        # Create EventBus for this request
        bus = self._create_event_bus()

        # Convert message to ConversationTurn history
        history = [ConversationTurn(role="user", msg=message)]

        try:
            # Call the underlying InferenceService
            logger.debug("Calling InferenceService for user=%s", user_id)
            result = self._inference_service.process_inference_request(
                history=history,
                bus=bus,
                disable_retry=False,
                max_retries=3,
            )

            # Extract response text
            response_text = result.get("response_text", "")
            if not response_text or not response_text.strip():
                raise RuntimeError("Agent returned empty response")

            # Extract references from calls
            calls = result.get("calls", [])
            references = self._extract_references(calls)

            logger.info(
                "Agent response generated for user=%s, refs=%d, content_len=%d",
                user_id,
                len(references),
                len(response_text),
            )

            return {"content": response_text, "references": references}

        except Exception as exc:
            # Convert various exceptions to RuntimeError for consistent interface
            error_msg = str(exc)
            logger.error("Agent request failed for user=%s: %s", user_id, error_msg)
            raise RuntimeError(f"Agent request failed: {error_msg}") from exc
