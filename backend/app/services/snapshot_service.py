from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from app.adapters.repos.base import GroundTruthRepo
from app.domain.enums import GroundTruthStatus


class SnapshotService:
    def __init__(self, repo: GroundTruthRepo, base_dir: str = "./exports/snapshots"):
        self.repo = repo
        self.base_dir = Path(base_dir)

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
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        items = await self.collect_approved()
        dataset_names: set[str] = set()
        out_items: list[dict] = []
        for it in items:
            dataset_names.add(getattr(it, "datasetName", ""))
            out_items.append(it.model_dump(mode="json", by_alias=True, exclude_none=True))

        payload: dict = {
            "schemaVersion": "v2",
            "snapshotAt": ts,
            "datasetNames": sorted(n for n in dataset_names if n),
            "count": len(out_items),
            "filters": {"status": "approved"},
            "items": out_items,
        }
        return payload

    async def export_json(self) -> dict[str, str | int]:
        """Export approved items as individual JSON documents and a manifest.

        Layout:
          ./exports/snapshots/{ts}/ground-truth-{id}.json
          ./exports/snapshots/{ts}/manifest.json
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = self.base_dir / ts
        out_dir.mkdir(parents=True, exist_ok=True)

        # Collect approved items (no fallback; surface errors)
        items = await self.collect_approved()

        # Write each item as its own JSON file
        dataset_names: set[str] = set()
        count = 0
        for it in items:
            dataset_names.add(getattr(it, "datasetName", ""))
            obj = it.model_dump(mode="json", by_alias=True, exclude_none=True)
            # Ensure schemaVersion/docType present from model defaults
            file_path = out_dir / f"ground-truth-{it.id}.json"
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
            count += 1

        manifest = {
            "schemaVersion": "v2",
            "snapshotAt": ts,
            "datasetNames": sorted(n for n in dataset_names if n),
            "count": count,
            "filters": {"status": "approved"},
        }
        with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return {
            "snapshotDir": str(out_dir.resolve()),
            "count": count,
            "manifestPath": str((out_dir / "manifest.json").resolve()),
        }
