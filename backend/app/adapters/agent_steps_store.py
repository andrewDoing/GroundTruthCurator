from __future__ import annotations

from typing import Any


class AgentStepsStore:
    """Placeholder interface for persisting agent step details."""

    async def save(
        self,
        *,
        user_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        raise NotImplementedError
