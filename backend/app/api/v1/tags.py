from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.tags import TAG_SCHEMA
from app.domain.manual_tags_provider import JsonFileManualTagProvider
from app.container import container
from app.plugins import get_default_registry
from app.core.config import settings
from pathlib import Path


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


# --- Glossary endpoint ---


class TagDefinitionDTO(BaseModel):
    key: str
    description: str | None = None


class TagGroupGlossaryDTO(BaseModel):
    name: str
    description: str | None = None
    type: str  # "manual" | "computed" | "custom"
    tags: list[TagDefinitionDTO]


class GlossaryResponse(BaseModel):
    version: str = "v1"
    groups: list[TagGroupGlossaryDTO]


@router.get("/tags/glossary", response_model=GlossaryResponse)
async def get_tags_glossary() -> GlossaryResponse:
    """Returns comprehensive tag glossary with definitions from all sources."""
    groups: list[TagGroupGlossaryDTO] = []

    # Load manual tag groups with descriptions
    config_path = settings.MANUAL_TAGS_CONFIG_PATH
    if config_path:
        path = Path(config_path)
        provider = JsonFileManualTagProvider(path)
        manual_groups = provider.get_default_tag_groups()

        for group in manual_groups:
            tags_with_desc: list[TagDefinitionDTO] = []

            # Use tag_definitions if available (new format), otherwise fall back to tags
            if group.tag_definitions:
                for tag_def in group.tag_definitions:
                    key = f"{group.group}:{tag_def.value}"
                    tags_with_desc.append(
                        TagDefinitionDTO(key=key, description=tag_def.description)
                    )
            else:
                for tag_val in group.tags:
                    key = f"{group.group}:{tag_val}"
                    tags_with_desc.append(TagDefinitionDTO(key=key, description=None))

            groups.append(
                TagGroupGlossaryDTO(
                    name=group.group,
                    description=group.description,
                    type="manual",
                    tags=tags_with_desc,
                )
            )

    # Add computed tags from registry
    # For now, computed tags have no descriptions (Phase 1)
    # Phase 2 can add plugin.description property
    registry = get_default_registry()
    computed_keys = sorted(registry.get_static_keys())

    if computed_keys:
        computed_tags = [TagDefinitionDTO(key=key, description=None) for key in computed_keys]
        groups.append(
            TagGroupGlossaryDTO(
                name="computed",
                description="Automatically computed tags based on item content",
                type="computed",
                tags=computed_tags,
            )
        )

    return GlossaryResponse(version="v1", groups=groups)
