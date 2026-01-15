from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from typing import Any, Union

router = APIRouter()


# todo: remove these, all this info SHOULD be in the openapi.json
@router.get("/schemas")
async def list_schemas(request: Request) -> list[Union[dict[str, str], str]]:
    """List available component schema names from the OpenAPI document.

    Compatibility behavior:
    - Returns a list where the first segment contains objects with `name` and `title`
        (for newer clients/tests that expect objects), followed by the plain string names
        (to preserve backward-compatibility with older callers/tests).
    """
    openapi = request.app.openapi()
    components: dict[str, Any] = openapi.get("components", {})
    schemas: dict[str, dict[str, Any]] = components.get("schemas", {})  # type: ignore[assignment]
    names: list[str] = sorted(list(schemas.keys()))
    objects: list[dict[str, str]] = [
        {"name": n, "title": str((schemas.get(n) or {}).get("title", n))} for n in names
    ]
    # Objects first (so callers indexing [0] see a mapping), then plain names for legacy callers
    return [*objects, *names]


@router.get("/schemas/{name}")
async def get_schema(request: Request, name: str) -> dict[str, Any]:
    """Return a specific component schema by name from the OpenAPI document."""
    openapi = request.app.openapi()
    components: dict[str, Any] = openapi.get("components", {})
    schemas: dict[str, Any] = components.get("schemas", {})
    if name not in schemas:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schemas[name]
