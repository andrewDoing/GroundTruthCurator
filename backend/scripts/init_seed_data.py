from __future__ import annotations

# Seed script: create N ground truth items and register default tags by exercising the API.
#
# Usage examples:
#   uv run python scripts/init_seed_data.py --dataset demo --count 100
#   uv run python scripts/init_seed_data.py --base-url http://localhost:8000 --user alice
#   GTC_ENV_FILE=environments/sample.env uv run python scripts/init_seed_data.py
#
# This script talks to the running FastAPI app instead of importing repository/services directly.

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable, Any

import httpx

# Ensure repository root (which contains the 'app' package) is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _build_item(dataset: str, idx: int) -> Any:
    from app.domain.models import GroundTruthItem, Reference
    from app.domain.enums import GroundTruthStatus

    # Vary some fields for realism while keeping validation simple
    qlen = ["short", "medium", "long"][idx % 3]
    split = "validation" if (idx % 4 != 0) else "train"
    tags: list[str] = [
        "source:synthetic",
        f"split:{split}",
        "answerability:answerable",
        f"question_length:{qlen}",
        "topic:general",
    ]
    # Only include judge_training when split=train to satisfy dependency
    if split == "train":
        tags.append("judge_training:train" if (idx % 2 == 0) else "judge_training:validation")
    # Build via model_validate with alias field names to satisfy static analyzers
    data = {
        "id": f"{dataset}-q{idx:04d}",
        "datasetName": dataset,
        "status": GroundTruthStatus.draft.value,
        "synthQuestion": f"What is item {idx} about in dataset '{dataset}'?",
        "refs": [
            Reference(url=f"https://example.com/{dataset}/{idx}").model_dump(
                mode="json", by_alias=True
            )
        ],
        "tags": tags,
    }
    return GroundTruthItem.model_validate(data)


def _default_registry_tags() -> list[str]:
    from app.domain.tags import TAG_SCHEMA

    res: list[str] = []
    for group, spec in TAG_SCHEMA.items():
        for value in sorted(spec.values):
            res.append(f"{group}:{value}")
    return sorted(res)


async def _seed(dataset: str, count: int, buckets: int | None) -> None:
    raise RuntimeError("_seed is unused in API-only mode")


async def _seed_via_api(
    base_url: str,
    api_prefix: str,
    user_id: str,
    dataset: str,
    count: int,
    buckets: int | None,
    approve: bool,
) -> int:
    # Build items payloads
    items = [_build_item(dataset, i + 1) for i in range(count)]
    payload = [it.model_dump(mode="json", by_alias=True) for it in items]

    # Compose URLs
    api_root = base_url.rstrip("/") + api_prefix
    gt_url = f"{api_root}/ground-truths"
    tags_url = f"{api_root}/tags"
    healthz_url = base_url.rstrip("/") + "/healthz"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-User-Id": user_id,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        # Health check first (non-fatal)
        try:
            r = await client.get(healthz_url)
            if r.status_code == 200:
                h = r.json()
                print(
                    f"Healthz OK: repoBackend={h.get('repoBackend')} endpoint={h.get('cosmos', {}).get('endpoint')}"
                )
            else:
                print(f"Warning: /healthz returned {r.status_code}")
        except Exception as e:
            print(f"Warning: /healthz check failed: {e}")

        # Import ground truths
        params: dict[str, str | int | float | bool | None] = {}
        if buckets is not None:
            params["buckets"] = int(buckets)
        if approve:
            params["approve"] = True
        resp = await client.post(gt_url, headers=headers, params=params, json=payload)
        if resp.status_code != 200:
            print("Error importing ground truths:", resp.status_code, resp.text)
            return 1
        res = resp.json()
        imported = int(res.get("imported", 0))
        errors = list(res.get("errors", []))
        print(f"Imported {imported} ground truth items into dataset '{dataset}'.")
        if errors:
            print("Import errors (not fatal):")
            for err in errors:
                print(" -", err)

        # Register default tags in global registry
        defaults = _default_registry_tags()
        resp2 = await client.post(tags_url, headers=headers, json={"tags": defaults})
        if resp2.status_code != 200:
            print("Error registering default tags:", resp2.status_code, resp2.text)
            return 1
        tag_res = resp2.json()
        total_tags = len(tag_res.get("tags", []))
        print(f"Registered default tags in global registry (now {total_tags} total).")

    return 0


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed ground truth items and default tags via API")
    p.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    p.add_argument(
        "--api-prefix",
        default=None,
        help="API prefix path (default: value from settings, e.g., /v1)",
    )
    p.add_argument(
        "--user",
        dest="user_id",
        default="seed-script",
        help="X-User-Id to send for dev auth (default: seed-script)",
    )
    p.add_argument("--dataset", default="demo", help="Dataset name to seed (default: demo)")
    p.add_argument(
        "--count", type=int, default=100, help="Number of items to create (default: 100)"
    )
    p.add_argument(
        "--buckets",
        type=int,
        default=None,
        help="Optional number of sampling buckets to distribute new items across",
    )
    p.add_argument(
        "--approve",
        action="store_true",
        help="If set, mark all imported items as approved on import",
    )
    return p.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = _parse_args(argv)
    # Resolve API prefix from settings if not provided
    if not args.api_prefix:
        try:
            from app.core.config import settings  # type: ignore

            args.api_prefix = settings.API_PREFIX
        except Exception:
            args.api_prefix = "/v1"
    try:
        rc = asyncio.run(
            _seed_via_api(
                base_url=args.base_url,
                api_prefix=args.api_prefix,
                user_id=args.user_id,
                dataset=args.dataset,
                count=max(1, int(args.count)),
                buckets=args.buckets,
                approve=args.approve,
            )
        )
        return rc
    except Exception as e:
        print("Error during seeding:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
