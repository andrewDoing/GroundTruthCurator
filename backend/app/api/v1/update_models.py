from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HistoryEntryPatch(BaseModel):
    model_config = ConfigDict(
        title="HistoryEntryPatch",
        populate_by_name=True,
        extra="allow",
    )

    role: str
    msg: str | None = None
