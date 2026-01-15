from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, status, Response
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, UserContext
from app.container import container
from app.domain.models import DatasetCurationInstructions

router = APIRouter()


class CurationInstructionsUpdate(BaseModel):
    instructions: str
    etag: str | None = Field(default=None, alias="_etag")


@router.get("/datasets", response_model=list[str])
async def list_datasets(user: UserContext = Depends(get_current_user)) -> list[str]:
    return await container.repo.list_datasets()


@router.get("/datasets/{datasetName}/curation-instructions")
async def get_curation_instructions(
    datasetName: str, user: UserContext = Depends(get_current_user)
) -> DatasetCurationInstructions:
    doc: DatasetCurationInstructions | None = await container.curation_service.get_for_dataset(
        datasetName
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


@router.put("/datasets/{datasetName}/curation-instructions", status_code=status.HTTP_200_OK)
async def put_curation_instructions(
    datasetName: str,
    payload: CurationInstructionsUpdate,
    response: Response,
    user: UserContext = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> DatasetCurationInstructions:
    existing = await container.curation_service.get_for_dataset(datasetName)
    etag = if_match or payload.etag
    if existing and not etag:
        raise HTTPException(status_code=412, detail="ETag required")

    try:
        doc = await container.curation_service.set_for_dataset(
            datasetName, payload.instructions, user.user_id, etag
        )
    except ValueError as e:
        if str(e) == "etag_mismatch":
            raise HTTPException(status_code=412, detail="ETag mismatch")
        if str(e) == "etag_required":
            raise HTTPException(status_code=412, detail="ETag required")
        raise

    # Set 201 only when creating a new doc without concurrency token (clear create intent)
    if existing is None and not (if_match or payload.etag):
        response.status_code = status.HTTP_201_CREATED

    return doc


@router.delete("/datasets/{datasetName}")
async def delete_dataset(
    datasetName: str, user: UserContext = Depends(get_current_user)
) -> dict[str, str]:
    """Hard-delete a dataset."""
    await container.repo.delete_dataset(datasetName)
    return {"status": "deleted"}
