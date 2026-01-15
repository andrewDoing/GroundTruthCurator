from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from app.adapters.gtc_inference_adapter import GTCInferenceAdapter
from app.adapters.agent_steps_store import AgentStepsStore

logger = logging.getLogger(__name__)

# Dedicated thread pool executor for blocking AI operations
# Sized to handle concurrent requests without exhausting resources
_executor: ThreadPoolExecutor | None = None
_EXECUTOR_MAX_WORKERS = 10  # Configurable based on expected concurrency


def _get_executor() -> ThreadPoolExecutor:
    """Get or create dedicated ThreadPoolExecutor for blocking operations."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=_EXECUTOR_MAX_WORKERS,
            thread_name_prefix="gtc_inference",
        )
        logger.info("Created ThreadPoolExecutor with %d workers", _EXECUTOR_MAX_WORKERS)
    return _executor


class ChatService:
    """Facade for generating chat responses via the inference service.

    Uses threadpool to run blocking sync inference calls without blocking FastAPI.
    """

    def __init__(
        self,
        inference_service: GTCInferenceAdapter | None,
        *,
        steps_store: AgentStepsStore | None = None,
        store_steps: bool = False,
    ) -> None:
        self._inference_service = inference_service
        self._steps_store = steps_store
        self._store_steps = store_steps and steps_store is not None

    @property
    def is_configured(self) -> bool:
        """Return True if inference service is configured and ready."""
        return self._inference_service is not None

    def set_steps_store(self, store: AgentStepsStore | None) -> None:
        self._steps_store = store
        if store is None:
            self._store_steps = False

    def set_store_steps(self, enabled: bool) -> None:
        self._store_steps = enabled and self._steps_store is not None

    async def generate_response(
        self,
        *,
        user_id: str,
        message: str,
        context: str | None,
    ) -> dict[str, Any]:
        """Generate a chat response using the inference service.

        Runs the blocking inference call in a threadpool to keep FastAPI responsive.

        Args:
            user_id: User identifier for logging
            message: User's question/message
            context: Optional context (currently unused)

        Returns:
            Dict with 'content' (assistant reply) and 'references' (list of citations)

        Raises:
            ValueError: If message is empty
            RuntimeError: If inference service not configured or request fails
        """
        if not message.strip():
            raise ValueError("message cannot be empty")

        logger.info(
            "Generating response for user=%s, using_agent=%s",
            user_id,
            self.is_configured,
        )

        if self._inference_service is not None:
            # Run blocking inference in threadpool
            loop = asyncio.get_event_loop()
            executor = _get_executor()

            try:
                response = await loop.run_in_executor(
                    executor,
                    partial(
                        self._inference_service.generate,
                        user_id=user_id,
                        message=message,
                    ),
                )
            except RuntimeError:
                # Re-raise RuntimeError (includes "retrieval not configured" errors)
                raise

            logger.info(
                "Agent returned response with %d references",
                len(response.get("references", [])),
            )
        else:
            logger.warning("Agent not configured, returning mock response")
            response = self._mock_response(message)

        await self._store_interaction(user_id, message, context, response)
        return response

    async def _store_interaction(
        self,
        user_id: str,
        message: str,
        context: str | None,
        response: dict[str, Any],
    ) -> None:
        if not self._store_steps or self._steps_store is None:
            return
        payload = {
            "message": message,
            "context": context,
        }
        try:
            await self._steps_store.save(
                user_id=user_id,
                request=payload,
                response=response,
            )
        except Exception:
            # Persisting steps is best-effort; never block the main response
            pass

    def _mock_response(self, message: str) -> dict[str, Any]:
        return {
            "content": (
                "No agent configuration detected. Returning mock response for testing purposes. "
                f"User message: {message}"
            ),
            "references": [],
        }
