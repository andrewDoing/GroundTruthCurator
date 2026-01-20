from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.tags import TAG_SCHEMA
from app.container import container
from app.plugins import get_default_registry
from app.core.config import settings


router = APIRouter()


class DependencyDTO(BaseModel):
    group: str
    value: str


class TagGroupDTO(BaseModel):
    name: str
    values: list[str]
    exclusive: bool
    depends_on: list[DependencyDTO] = Field(default_factory=list)


class TagSchemaResponse(BaseModel):
    version: str = "v1"
    groups: list[TagGroupDTO]


@router.get("/tags/schema", response_model=TagSchemaResponse)
async def get_tags_schema() -> TagSchemaResponse:
    groups = []
    for name, spec in sorted(TAG_SCHEMA.items(), key=lambda kv: kv[0]):
        depends = [DependencyDTO(group=g, value=v) for (g, v) in sorted(spec.depends_on or [])]
        groups.append(
            TagGroupDTO(
                name=name,
                values=sorted(list(spec.values)),
                exclusive=spec.exclusive,
                depends_on=depends,
            )
        )
    return TagSchemaResponse(groups=groups)


# --- Global tag registry endpoints ---


class TagListResponse(BaseModel):
    model_config = {"populate_by_name": True}

    tags: list[str]  # Manual tags only
    computed_tags: list[str] = Field(default_factory=list, alias="computedTags")


class AddTagsRequest(BaseModel):
    tags: list[str]


class RemoveTagsRequest(BaseModel):
    tags: list[str]


@router.get("/tags", response_model=TagListResponse)
async def get_tags() -> TagListResponse:
    try:
        registry = get_default_registry()
        computed_tag_keys = sorted(registry.get_static_keys())
        computed_tag_set = set(computed_tag_keys)

        # If ALLOWED_MANUAL_TAGS is set, use it as the source of truth for
        # manual tag selection (provider-style configuration).
        if settings.ALLOWED_MANUAL_TAGS:
            manual_tags = [
                t.strip() for t in settings.ALLOWED_MANUAL_TAGS.split(",") if t and t.strip()
            ]
        else:
            manual_tags = await container.tag_registry_service.list_tags()
        filtered_manual = sorted([t for t in manual_tags if t not in computed_tag_set])
        return TagListResponse(tags=filtered_manual, computedTags=computed_tag_keys)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tags", response_model=TagListResponse)
async def post_tags(req: AddTagsRequest) -> TagListResponse:
    try:
        tags = await container.tag_registry_service.add_tags(req.tags)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registry = get_default_registry()
    computed_tag_keys = sorted(registry.get_static_keys())
    return TagListResponse(tags=tags, computedTags=computed_tag_keys)


@router.delete("/tags", response_model=TagListResponse)
async def delete_tags(req: RemoveTagsRequest) -> TagListResponse:
    try:
        tags = await container.tag_registry_service.remove_tags(req.tags)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registry = get_default_registry()
    computed_tag_keys = sorted(registry.get_static_keys())
    return TagListResponse(tags=tags, computedTags=computed_tag_keys)
