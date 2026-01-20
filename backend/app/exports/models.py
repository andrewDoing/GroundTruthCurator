from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExportFormat = Literal["json_snapshot_payload", "json_items"]
ExportDeliveryMode = Literal["attachment", "artifact"]


class ExportFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    dataset_names: list[str] | None = Field(default=None, alias="datasetNames")
    status: str = Field(default="approved")


class ExportDeliveryOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mode: ExportDeliveryMode = Field(default="artifact")


class SnapshotExportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    format: ExportFormat | None = None
    filters: ExportFilters | None = None
    processors: list[str] | None = None
    delivery: ExportDeliveryOptions | None = Field(default_factory=ExportDeliveryOptions)
