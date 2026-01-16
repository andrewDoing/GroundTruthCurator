from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from fastapi.responses import Response

from app.adapters.repos.base import GroundTruthRepo
from app.domain.enums import GroundTruthStatus
from app.exports.models import ExportFilters, SnapshotExportRequest
from app.exports.pipeline import ExportPipeline
from app.exports.registry import ExportFormatterRegistry, ExportProcessorRegistry


class SnapshotService:
    def __init__(
        self,
        repo: GroundTruthRepo,
        export_pipeline: ExportPipeline,
        processor_registry: ExportProcessorRegistry,
        formatter_registry: ExportFormatterRegistry,
        default_processor_order: list[str],
    ):
        self.repo = repo
        self.export_pipeline = export_pipeline
        self.processor_registry = processor_registry
        self.formatter_registry = formatter_registry
        self.default_processor_order = default_processor_order

    async def collect_approved(self) -> list:
        """Return all approved GroundTruthItems from the repository.

        Errors are allowed to surface to callers; no legacy fallbacks.
        """
        items = await self.repo.list_all_gt(status=GroundTruthStatus.approved)
        return items

    async def build_snapshot_payload(self) -> dict:
        """Build an in-memory JSON payload of approved items.

        Shape:
            { schemaVersion: "v2", snapshotAt, datasetNames, count, filters, items }
        """
        request = SnapshotExportRequest()
        payload_bytes, _ = await self._format_payload(request)
        return json.loads(payload_bytes)

    async def export_snapshot(self, request: SnapshotExportRequest) -> Response | dict[str, str | int]:
        delivery_mode = request.delivery.mode if request.delivery else "attachment"
        if delivery_mode == "artifact":
            snapshot_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            items, filters = await self._collect_export_items(request)
            return await self.export_pipeline.deliver_artifacts(
                items=items,
                filters=filters,
                snapshot_at=snapshot_at,
            )

        payload_bytes, snapshot_at = await self._format_payload(request)
        filename = self._resolve_filename(request.format, snapshot_at)
        return await self.export_pipeline.deliver_attachment(payload_bytes, filename=filename)

    async def _collect_export_items(
        self, request: SnapshotExportRequest
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        filters = request.filters or ExportFilters()
        status_value = filters.status
        try:
            status = GroundTruthStatus(status_value) if status_value else None
        except ValueError as exc:
            raise ValueError(f"Invalid status value '{status_value}'") from exc

        items = await self.repo.list_all_gt(status=status)
        dataset_names = filters.dataset_names
        if dataset_names:
            items = [it for it in items if getattr(it, "datasetName", None) in dataset_names]

        out_items = [
            it.model_dump(mode="json", by_alias=True, exclude_none=True) for it in items
        ]
        processors = self.processor_registry.resolve_chain(
            request.processors,
            self.default_processor_order,
        )
        for processor in processors:
            out_items = processor.process(out_items)

        filters_payload: dict[str, Any] = {"status": status_value}
        if dataset_names is not None:
            filters_payload["datasetNames"] = dataset_names
        return out_items, filters_payload

    async def _format_payload(self, request: SnapshotExportRequest) -> tuple[bytes, str]:
        snapshot_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        items, filters = await self._collect_export_items(request)
        format_name = request.format or "json_snapshot_payload"
        formatter = self.formatter_registry.create(
            format_name,
            snapshot_at=snapshot_at,
            filters=filters,
        )
        formatted = formatter.format(items)
        payload_bytes = formatted if isinstance(formatted, bytes) else formatted.encode("utf-8")
        return payload_bytes, snapshot_at

    def _resolve_filename(self, format_name: str | None, snapshot_at: str) -> str:
        if (format_name or "json_snapshot_payload") == "json_items":
            return f"ground-truth-items-{snapshot_at}.json"
        return f"ground-truth-snapshot-{snapshot_at}.json"

