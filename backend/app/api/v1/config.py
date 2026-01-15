"""
Configuration endpoint for exposing frontend runtime configuration.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import UserContext, get_current_user
from app.core.config import settings

router = APIRouter(tags=["config"])


class FrontendConfig(BaseModel):
    """Frontend runtime configuration."""

    requireReferenceVisit: bool
    requireKeyParagraph: bool
    selfServeLimit: int
    trustedReferenceDomains: list[str]


@router.get("/config", response_model=FrontendConfig)
async def get_frontend_config(user: UserContext = Depends(get_current_user)) -> FrontendConfig:
    """
    Get frontend runtime configuration.

    This endpoint exposes backend configuration to the frontend,
    allowing runtime configuration without rebuilding the frontend.

    Returns:
        FrontendConfig: Configuration values for frontend validation behavior
    """
    trusted_domains_raw = settings.TRUSTED_REFERENCE_DOMAINS or ""
    trusted_domains = [d.strip().lower() for d in trusted_domains_raw.split(",") if d.strip()]

    return FrontendConfig(
        requireReferenceVisit=settings.REQUIRE_REFERENCE_VISIT,
        requireKeyParagraph=settings.REQUIRE_KEY_PARAGRAPH,
        selfServeLimit=settings.SELF_SERVE_LIMIT,
        trustedReferenceDomains=trusted_domains,
    )
