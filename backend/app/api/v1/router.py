from fastapi import APIRouter

from app.api.v1 import (
    ground_truths,
    stats,
    assignments,
    schemas,
    tags,
    datasets,
    search,
    chat,
)
from app.api.v1 import config

api_router = APIRouter()

api_router.include_router(config.router, prefix="", tags=["config"])  # /config endpoint
api_router.include_router(stats.router, prefix="", tags=["stats"])  # expose /ground-truths/stats
api_router.include_router(ground_truths.router, prefix="/ground-truths", tags=["ground-truths"])
api_router.include_router(assignments.router, prefix="/assignments", tags=["assignments"])
api_router.include_router(schemas.router, prefix="", tags=["schemas"])  # /schemas endpoints
api_router.include_router(tags.router, prefix="", tags=["tags"])  # /tags endpoints
api_router.include_router(datasets.router, prefix="", tags=["datasets"])  # /datasets endpoints
api_router.include_router(search.router, prefix="", tags=["search"])  # /search endpoint
api_router.include_router(chat.router, prefix="", tags=["chat"])  # /chat endpoint
