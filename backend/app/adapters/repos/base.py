from __future__ import annotations

from typing import Protocol, Optional
from uuid import UUID

from app.domain.models import (
    GroundTruthItem,
    Stats,
    DatasetCurationInstructions,
    AssignmentDocument,
    BulkImportResult,
    PaginationMetadata,
)
from app.domain.enums import GroundTruthStatus, SortField, SortOrder


class GroundTruthRepo(Protocol):
    # Core ground truth operations
    async def import_bulk_gt(
        self, items: list[GroundTruthItem], buckets: int | None = None
    ) -> BulkImportResult: ...
    async def list_gt_by_dataset(
        self, dataset: str, status: Optional[GroundTruthStatus] = None
    ) -> list[GroundTruthItem]: ...
    async def list_all_gt(
        self, status: Optional[GroundTruthStatus] = None
    ) -> list[GroundTruthItem]: ...
    async def list_gt_paginated(
        self,
        status: Optional[GroundTruthStatus] = None,
        dataset: str | None = None,
        tags: list[str] | None = None,
        item_id: str | None = None,
        ref_url: str | None = None,
        sort_by: SortField | None = None,
        sort_order: SortOrder | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> tuple[list[GroundTruthItem], PaginationMetadata]: ...
    async def get_gt(self, dataset: str, bucket: UUID, item_id: str) -> GroundTruthItem | None: ...
    async def upsert_gt(self, item: GroundTruthItem) -> GroundTruthItem: ...
    async def soft_delete_gt(self, dataset: str, bucket: UUID, item_id: str) -> None: ...
    async def delete_dataset(self, dataset: str) -> None: ...
    async def stats(self) -> Stats: ...
    async def list_datasets(self) -> list[str]: ...

    # Assignment helpers (ground truth assignment lifecycle)
    async def list_unassigned(self, limit: int) -> list[GroundTruthItem]: ...
    async def sample_unassigned(
        self, user_id: str, limit: int, exclude_ids: list[str] | None = None
    ) -> list[GroundTruthItem]: ...
    async def assign_to(self, item_id: str, user_id: str) -> bool: ...
    async def list_assigned(self, user_id: str) -> list[GroundTruthItem]: ...

    # SME Assignment documents (secondary container)
    async def upsert_assignment_doc(
        self, user_id: str, gt: GroundTruthItem
    ) -> AssignmentDocument: ...
    async def list_assignments_by_user(self, user_id: str) -> list[AssignmentDocument]: ...
    async def get_assignment_by_gt(
        self, user_id: str, ground_truth_id: str
    ) -> AssignmentDocument | None: ...
    async def delete_assignment_doc(
        self, user_id: str, dataset: str, bucket: UUID, ground_truth_id: str
    ) -> bool: ...

    # Curation instructions (stored in GT container with datasetName PK and bucket=0)
    async def get_curation_instructions(
        self, dataset: str
    ) -> DatasetCurationInstructions | None: ...
    async def upsert_curation_instructions(
        self, doc: DatasetCurationInstructions
    ) -> DatasetCurationInstructions: ...
