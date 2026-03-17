from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Iterable
from uuid import UUID

from app.domain.conversation_fields import answer_text_from_item, question_text_from_item
from app.domain.enums import GroundTruthStatus, SortField, SortOrder
from app.domain.models import (
    AgenticGroundTruthEntry,
    AssignmentDocument,
    BulkImportPersistenceError,
    BulkImportResult,
    DatasetCurationInstructions,
    PaginationMetadata,
    Stats,
)
from app.plugins.base import PluginPackRegistry
from app.plugins.pack_registry import get_default_pack_registry

ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")


class InMemoryGroundTruthRepo:
    def __init__(
        self,
        *,
        items: list[AgenticGroundTruthEntry] | None = None,
        curation_instructions: list[DatasetCurationInstructions] | None = None,
        plugin_pack_registry: PluginPackRegistry | None = None,
    ) -> None:
        self.items: dict[str, AgenticGroundTruthEntry] = {}
        self._locations: dict[tuple[str, UUID, str], str] = {}
        self._assignment_docs: dict[tuple[str, str], AssignmentDocument] = {}
        self._curation: dict[str, DatasetCurationInstructions] = {}
        self._etag_version = 0
        self._plugin_pack_registry = plugin_pack_registry or get_default_pack_registry()

        for item in items or []:
            self._store_initial_item(item)
        for doc in curation_instructions or []:
            self._curation[doc.datasetName] = self._clone_instruction(doc)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _next_etag(self) -> str:
        self._etag_version += 1
        return f"memory-etag-{self._etag_version}"

    def _clone_item(self, item: AgenticGroundTruthEntry) -> AgenticGroundTruthEntry:
        return AgenticGroundTruthEntry.model_validate(
            item.model_dump(by_alias=True, exclude={"tags"})
        )

    def _clone_instruction(self, doc: DatasetCurationInstructions) -> DatasetCurationInstructions:
        return DatasetCurationInstructions.model_validate(doc.model_dump(by_alias=True))

    def _location_key(
        self, dataset: str, bucket: UUID | None, item_id: str
    ) -> tuple[str, UUID, str]:
        return (dataset, bucket or ZERO_UUID, item_id)

    def _store_initial_item(self, item: AgenticGroundTruthEntry) -> None:
        stored = self._clone_item(item)
        now = stored.updated_at or self._now()
        if stored.created_at is None:
            stored.created_at = now
        stored.updated_at = now
        stored.etag = self._next_etag()
        if stored.bucket is None:
            stored.bucket = ZERO_UUID
        self.items[stored.id] = stored
        self._locations[self._location_key(stored.datasetName, stored.bucket, stored.id)] = (
            stored.id
        )
        if stored.assignedTo:
            self._assignment_docs[(stored.assignedTo, stored.id)] = AssignmentDocument(
                id=f"{stored.assignedTo}:{stored.id}",
                pk=stored.assignedTo,
                ground_truth_id=stored.id,
                datasetName=stored.datasetName,
                bucket=stored.bucket,
            )

    def _save_item(self, item: AgenticGroundTruthEntry) -> AgenticGroundTruthEntry:
        stored = self._clone_item(item)
        if stored.bucket is None:
            stored.bucket = ZERO_UUID
        if stored.created_at is None:
            stored.created_at = self._now()
        stored.updated_at = self._now()
        stored.etag = self._next_etag()
        self.items[stored.id] = stored
        self._locations[self._location_key(stored.datasetName, stored.bucket, stored.id)] = (
            stored.id
        )
        return self._clone_item(stored)

    def _get_stored(self, item_id: str) -> AgenticGroundTruthEntry | None:
        return self.items.get(item_id)

    def _matches_location(
        self, item: AgenticGroundTruthEntry, dataset: str, bucket: UUID, item_id: str
    ) -> bool:
        return (
            item.id == item_id
            and item.datasetName == dataset
            and (item.bucket or ZERO_UUID) == bucket
        )

    def _collect_urls(self, item: AgenticGroundTruthEntry) -> Iterable[str]:
        for doc in self._plugin_pack_registry.collect_search_documents(item):
            url = doc.get("url")
            if isinstance(url, str) and url:
                yield url

    def _collect_text(self, item: AgenticGroundTruthEntry) -> str:
        parts = [
            item.id,
            item.datasetName,
            question_text_from_item(item),
            answer_text_from_item(item),
            item.comment or "",
        ]
        for turn in item.history or []:
            parts.append(turn.msg)
        for doc in self._plugin_pack_registry.collect_search_documents(item):
            parts.extend(
                [
                    str(doc.get("id") or ""),
                    str(doc.get("title") or ""),
                    str(doc.get("url") or ""),
                    str(doc.get("chunk") or ""),
                ]
            )
        return " ".join(parts).lower()

    def _is_unassigned_candidate(self, item: AgenticGroundTruthEntry) -> bool:
        return not item.assignedTo and item.status in {
            GroundTruthStatus.draft,
            GroundTruthStatus.skipped,
        }

    def _sort_items(
        self,
        items: list[AgenticGroundTruthEntry],
        sort_by: SortField | None,
        plugin_sort: str | None,
        sort_order: SortOrder | None,
    ) -> list[AgenticGroundTruthEntry]:
        field = sort_by or SortField.reviewed_at
        reverse = (sort_order or SortOrder.desc) == SortOrder.desc

        def key(item: AgenticGroundTruthEntry):
            if plugin_sort:
                plugin_value = self._plugin_pack_registry.plugin_sort_value(item, plugin_sort)
                return (
                    plugin_value if plugin_value is not None else -1,
                    item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
                    item.id,
                )
            if field == SortField.updated_at:
                return item.updated_at or datetime.min.replace(tzinfo=timezone.utc)
            if field == SortField.id:
                return item.id
            if field == SortField.has_answer:
                return (
                    1 if answer_text_from_item(item) else 0,
                    item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
                )
            if field == SortField.tag_count:
                return (
                    len(item.tags),
                    item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
                )
            return item.reviewed_at or datetime.min.replace(tzinfo=timezone.utc)

        return sorted(items, key=key, reverse=reverse)

    async def import_bulk_gt(
        self, items: list[AgenticGroundTruthEntry], buckets: int | None = None
    ) -> BulkImportResult:
        imported = 0
        persistence_errors: list[BulkImportPersistenceError] = []
        for index, item in enumerate(items):
            if item.id in self.items:
                persistence_errors.append(
                    BulkImportPersistenceError(
                        message=f"duplicate_id (id: {item.id})",
                        item_id=item.id,
                        persistence_index=index,
                    )
                )
                continue
            self._save_item(item)
            imported += 1
        return BulkImportResult(imported=imported, persistence_errors=persistence_errors)

    async def list_gt_by_dataset(
        self, dataset: str, status: GroundTruthStatus | None = None
    ) -> list[AgenticGroundTruthEntry]:
        items = [item for item in self.items.values() if item.datasetName == dataset]
        if status is not None:
            items = [item for item in items if item.status == status]
        return [
            self._clone_item(item)
            for item in self._sort_items(items, SortField.updated_at, None, SortOrder.desc)
        ]

    async def list_all_gt(
        self, status: GroundTruthStatus | None = None
    ) -> list[AgenticGroundTruthEntry]:
        items = list(self.items.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        return [
            self._clone_item(item)
            for item in self._sort_items(items, SortField.updated_at, None, SortOrder.desc)
        ]

    async def list_gt_paginated(
        self,
        status: GroundTruthStatus | None = None,
        dataset: str | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        item_id: str | None = None,
        plugin_filters: dict[str, str] | None = None,
        keyword: str | None = None,
        sort_by: SortField | None = None,
        plugin_sort: str | None = None,
        sort_order: SortOrder | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> tuple[list[AgenticGroundTruthEntry], PaginationMetadata]:
        filtered = list(self.items.values())
        if status is not None:
            filtered = [item for item in filtered if item.status == status]
        if dataset:
            filtered = [item for item in filtered if item.datasetName == dataset]
        if tags:
            required = set(tags)
            filtered = [item for item in filtered if required.issubset(set(item.tags))]
        if exclude_tags:
            banned = set(exclude_tags)
            filtered = [item for item in filtered if not banned.intersection(set(item.tags))]
        if item_id:
            filtered = [item for item in filtered if item_id in item.id]
        if plugin_filters:
            filtered = [
                item
                for item in filtered
                if self._plugin_pack_registry.matches_query_filters(item, plugin_filters)
            ]
        if keyword:
            lowered = keyword.lower()
            filtered = [item for item in filtered if lowered in self._collect_text(item)]

        sorted_items = self._sort_items(filtered, sort_by, plugin_sort, sort_order)
        total = len(sorted_items)
        start = (page - 1) * limit
        end = start + limit
        page_items = [self._clone_item(item) for item in sorted_items[start:end]]
        total_pages = ceil(total / limit) if total else 0
        metadata = PaginationMetadata(
            page=page,
            limit=limit,
            total=total,
            totalPages=total_pages,
            hasNext=end < total,
            hasPrev=page > 1 and total > 0,
        )
        return page_items, metadata

    async def get_gt(
        self, dataset: str, bucket: UUID, item_id: str
    ) -> AgenticGroundTruthEntry | None:
        item = self._get_stored(item_id)
        if item is None or not self._matches_location(item, dataset, bucket, item_id):
            return None
        return self._clone_item(item)

    async def upsert_gt(self, item: AgenticGroundTruthEntry) -> AgenticGroundTruthEntry:
        existing = self._get_stored(item.id)
        if existing is not None and item.etag and existing.etag != item.etag:
            raise ValueError("etag_mismatch")
        candidate = self._clone_item(item)
        if existing is not None and candidate.created_at is None:
            candidate.created_at = existing.created_at
        saved = self._save_item(candidate)
        if saved.assignedTo:
            await self.upsert_assignment_doc(saved.assignedTo, saved)
        else:
            stale_docs = [key for key in self._assignment_docs if key[1] == saved.id]
            for key in stale_docs:
                self._assignment_docs.pop(key, None)
        return saved

    async def soft_delete_gt(self, dataset: str, bucket: UUID, item_id: str) -> None:
        existing = self._get_stored(item_id)
        if existing is None or not self._matches_location(existing, dataset, bucket, item_id):
            return
        existing.status = GroundTruthStatus.deleted
        existing.assignedTo = None
        existing.assigned_at = None
        self._save_item(existing)
        stale_docs = [key for key in self._assignment_docs if key[1] == item_id]
        for key in stale_docs:
            self._assignment_docs.pop(key, None)

    async def delete_dataset(self, dataset: str) -> None:
        ids = [item.id for item in self.items.values() if item.datasetName == dataset]
        for item_id in ids:
            self.items.pop(item_id, None)
            stale_docs = [key for key in self._assignment_docs if key[1] == item_id]
            for key in stale_docs:
                self._assignment_docs.pop(key, None)
        self._curation.pop(dataset, None)
        self._locations = {
            key: value for key, value in self._locations.items() if key[0] != dataset
        }

    async def stats(self) -> Stats:
        stats = Stats()
        for item in self.items.values():
            if item.status == GroundTruthStatus.draft:
                stats.draft += 1
            elif item.status == GroundTruthStatus.approved:
                stats.approved += 1
            elif item.status == GroundTruthStatus.deleted:
                stats.deleted += 1
        return stats

    async def list_datasets(self) -> list[str]:
        return sorted({item.datasetName for item in self.items.values()})

    async def list_unassigned(self, limit: int) -> list[AgenticGroundTruthEntry]:
        items = [item for item in self.items.values() if self._is_unassigned_candidate(item)]
        return [
            self._clone_item(item)
            for item in self._sort_items(items, SortField.updated_at, None, SortOrder.desc)[:limit]
        ]

    async def sample_unassigned(
        self, user_id: str, limit: int, exclude_ids: list[str] | None = None
    ) -> list[AgenticGroundTruthEntry]:
        return await self.query_unassigned_global(user_id, limit, exclude_ids)

    async def query_unassigned_by_dataset_prefix(
        self, dataset_prefix: str, user_id: str, take: int, exclude_ids: list[str] | None = None
    ) -> list[AgenticGroundTruthEntry]:
        blocked = set(exclude_ids or [])
        items = [
            item
            for item in self.items.values()
            if item.datasetName.startswith(dataset_prefix)
            and self._is_unassigned_candidate(item)
            and item.id not in blocked
        ]
        return [
            self._clone_item(item)
            for item in self._sort_items(items, SortField.updated_at, None, SortOrder.desc)[:take]
        ]

    async def query_unassigned_global(
        self, user_id: str, take: int, exclude_ids: list[str] | None = None
    ) -> list[AgenticGroundTruthEntry]:
        blocked = set(exclude_ids or [])
        items = [
            item
            for item in self.items.values()
            if self._is_unassigned_candidate(item) and item.id not in blocked
        ]
        return [
            self._clone_item(item)
            for item in self._sort_items(items, SortField.updated_at, None, SortOrder.desc)[:take]
        ]

    async def assign_to(self, item_id: str, user_id: str) -> bool:
        existing = self._get_stored(item_id)
        if existing is None:
            return False
        if (
            existing.assignedTo
            and existing.assignedTo != user_id
            and existing.status == GroundTruthStatus.draft
        ):
            return False
        existing.assignedTo = user_id
        existing.assigned_at = self._now()
        existing.status = GroundTruthStatus.draft
        self._save_item(existing)
        return True

    async def clear_assignment(self, item_id: str) -> bool:
        existing = self._get_stored(item_id)
        if existing is None:
            return False
        existing.assignedTo = None
        existing.assigned_at = None
        self._save_item(existing)
        stale_docs = [key for key in self._assignment_docs if key[1] == item_id]
        for key in stale_docs:
            self._assignment_docs.pop(key, None)
        return True

    async def list_assigned(self, user_id: str) -> list[AgenticGroundTruthEntry]:
        items = [
            item
            for item in self.items.values()
            if item.assignedTo == user_id and item.status == GroundTruthStatus.draft
        ]
        return [
            self._clone_item(item)
            for item in self._sort_items(items, SortField.updated_at, None, SortOrder.desc)
        ]

    async def upsert_assignment_doc(
        self, user_id: str, gt: AgenticGroundTruthEntry
    ) -> AssignmentDocument:
        bucket = gt.bucket or ZERO_UUID
        doc = AssignmentDocument(
            id=f"{user_id}:{gt.id}",
            pk=user_id,
            ground_truth_id=gt.id,
            datasetName=gt.datasetName,
            bucket=bucket,
        )
        self._assignment_docs[(user_id, gt.id)] = doc
        return AssignmentDocument.model_validate(doc.model_dump(by_alias=True))

    async def list_assignments_by_user(self, user_id: str) -> list[AssignmentDocument]:
        docs = [
            doc
            for (assigned_user, _), doc in self._assignment_docs.items()
            if assigned_user == user_id
        ]
        return [AssignmentDocument.model_validate(doc.model_dump(by_alias=True)) for doc in docs]

    async def get_assignment_by_gt(
        self, user_id: str, ground_truth_id: str
    ) -> AssignmentDocument | None:
        doc = self._assignment_docs.get((user_id, ground_truth_id))
        if doc is None:
            return None
        return AssignmentDocument.model_validate(doc.model_dump(by_alias=True))

    async def delete_assignment_doc(
        self, user_id: str, dataset: str, bucket: UUID, ground_truth_id: str
    ) -> bool:
        return self._assignment_docs.pop((user_id, ground_truth_id), None) is not None

    async def get_curation_instructions(self, dataset: str) -> DatasetCurationInstructions | None:
        doc = self._curation.get(dataset)
        if doc is None:
            return None
        return self._clone_instruction(doc)

    async def upsert_curation_instructions(
        self, doc: DatasetCurationInstructions
    ) -> DatasetCurationInstructions:
        stored = self._clone_instruction(doc)
        stored.updated_at = self._now()
        stored.etag = self._next_etag()
        self._curation[stored.datasetName] = stored
        return self._clone_instruction(stored)
