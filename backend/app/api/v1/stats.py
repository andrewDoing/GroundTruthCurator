from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user, UserContext
from app.container import container

router = APIRouter()


@router.get("/ground-truths/stats")
async def get_stats(user: UserContext = Depends(get_current_user)):
    base_stats = await container.repo.stats()
    return container.plugin_pack_registry.collect_stats(base_stats.model_dump())


# todo: add endpoint for all user stats
# should be broken down by tag
