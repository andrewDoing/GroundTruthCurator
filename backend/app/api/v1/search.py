from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_user, UserContext
from app.container import container


router = APIRouter()


@router.get("/search")
async def search(
    q: str | None = Query(default=None, description="Search query string"),
    top: int = Query(default=5, ge=1, le=50, description="Max results (1-50)"),
    user: UserContext = Depends(get_current_user),
):
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="q is required")
    try:
        results = await container.search_service.query(q=q, top=top)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    # Return normalized results directly
    return {"results": results}
