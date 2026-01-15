from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.container import container
from app.core.auth import Principal, require_user
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_SCRIPT_PATTERN = re.compile(r"<\s*/?\s*script\b", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Safe error messages that don't leak internal details
SAFE_ERROR_MESSAGES = {
    "invalid_input": "Invalid request format",
    "service_unavailable": "Service temporarily unavailable",
    "processing_error": "Unable to process request",
}


def sanitize_message(raw: str) -> str:
    """Normalize whitespace and reject obvious script tags."""
    if not raw:
        return ""

    cleaned = _WHITESPACE_PATTERN.sub(" ", raw).strip()
    if not cleaned:
        return ""

    if _SCRIPT_PATTERN.search(cleaned):
        raise ValueError("message contains disallowed content")

    return cleaned


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    context: str | None = Field(default=None)

    @field_validator("message")
    @classmethod
    def _validate_message(_cls, value: str) -> str:
        sanitized = sanitize_message(value)
        if not sanitized:
            raise ValueError("message cannot be empty")
        return sanitized

    @field_validator("context")
    @classmethod
    def _trim_context(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ChatReference(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    keyParagraph: str | None = None


class ChatResponse(BaseModel):
    content: str
    references: list[ChatReference] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    principal: Principal = Depends(require_user),
) -> ChatResponse:
    if not settings.CHAT_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat is disabled",
        )

    user_id = principal.email or principal.oid or principal.name or "anonymous"

    # Generate correlation ID for error tracking without exposing internals
    correlation_id = str(uuid.uuid4())

    logger.info(
        "Chat request correlation_id=%s user=%s message_length=%d has_context=%s",
        correlation_id,
        user_id,
        len(body.message),
        body.context is not None,
    )

    try:
        result = await container.chat_service.generate_response(
            user_id=user_id,
            message=body.message,
            context=body.context,
        )
        logger.info(
            "Chat success correlation_id=%s ref_count=%d",
            correlation_id,
            len(result.get("references", [])),
        )
        # Don't log full result at INFO level - may contain PII or sensitive data
        logger.debug("Chat result correlation_id=%s", correlation_id)
    except ValueError as exc:
        # Log validation errors server-side with details
        logger.warning("Validation error correlation_id=%s error=%s", correlation_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=SAFE_ERROR_MESSAGES["invalid_input"],
            headers={"X-Correlation-ID": correlation_id},
        )
    except RuntimeError as exc:
        # Log runtime errors server-side with details
        logger.error("Runtime error correlation_id=%s error=%s", correlation_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=SAFE_ERROR_MESSAGES["service_unavailable"],
            headers={"X-Correlation-ID": correlation_id},
        )
    except Exception:  # pragma: no cover - safeguard unexpected failures
        # Log unexpected errors with full stack trace server-side only
        logger.error("Unexpected error correlation_id=%s", correlation_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SAFE_ERROR_MESSAGES["processing_error"],
            headers={"X-Correlation-ID": correlation_id},
        )

    try:
        response = ChatResponse(**result)
        logger.info(
            "Returning ChatResponse correlation_id=%s content_length=%d references_count=%d",
            correlation_id,
            len(response.content),
            len(response.references),
        )
        return response
    except Exception:
        # Log response parsing errors server-side only with stack trace
        logger.error("Response parsing error correlation_id=%s", correlation_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=SAFE_ERROR_MESSAGES["processing_error"],
            headers={"X-Correlation-ID": correlation_id},
        )
