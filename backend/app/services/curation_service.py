from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.adapters.repos.base import GroundTruthRepo
from app.domain.models import DatasetCurationInstructions


class CurationService:
    def __init__(self, repo: GroundTruthRepo):
        self.repo = repo

    async def get_for_dataset(self, dataset: str) -> DatasetCurationInstructions | None:
        return await self.repo.get_curation_instructions(dataset)

    async def set_for_dataset(
        self, dataset: str, instructions: str, user_id: str, etag: str | None
    ) -> DatasetCurationInstructions:
        # Build new or merge existing
        existing = await self.repo.get_curation_instructions(dataset)
        if existing:
            if etag is None:
                # Require concurrency token for updates
                raise ValueError("etag_required")
            doc = existing
            doc.instructions = instructions
            doc.updatedBy = user_id
            doc.etag = etag
        else:
            doc = DatasetCurationInstructions(
                id=f"curation-instructions|{dataset}",
                datasetName=str(dataset),
                bucket=UUID("00000000-0000-0000-0000-000000000000"),
                instructions=instructions,
                updatedBy=user_id,
            )
        # Ensure updatedAt is set; repo will also update, but keep model consistent
        doc.updated_at = datetime.now(timezone.utc)
        return await self.repo.upsert_curation_instructions(doc)
