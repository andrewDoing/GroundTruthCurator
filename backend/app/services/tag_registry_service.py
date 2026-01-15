from __future__ import annotations

from typing import Iterable, Protocol
from app.services.tagging_service import normalize_tag


class TagsRepo(Protocol):
    async def get_global_tags(self) -> list[str]: ...

    async def save_global_tags(self, tags: list[str]) -> list[str]: ...


class TagRegistryService:
    def __init__(self, repo: TagsRepo):
        self.repo = repo

    @staticmethod
    def normalize_and_canonicalize(tags: Iterable[str]) -> list[str]:
        normed: list[str] = []
        seen: set[str] = set()
        for t in tags:
            s = normalize_tag(t)
            if s not in seen:
                seen.add(s)
                normed.append(s)
        return sorted(normed)

    async def list_tags(self) -> list[str]:
        tags = await self.repo.get_global_tags()
        # Ensure deterministic sort
        return sorted([normalize_tag(t) for t in tags])

    async def add_tags(self, tags: Iterable[str]) -> list[str]:
        to_add = self.normalize_and_canonicalize(tags)
        current = await self.repo.get_global_tags()
        merged = sorted(set([normalize_tag(t) for t in current]) | set(to_add))
        return await self.repo.save_global_tags(merged)

    async def remove_tags(self, tags: Iterable[str]) -> list[str]:
        to_remove = self.normalize_and_canonicalize(tags)
        current = set(await self.repo.get_global_tags())
        res = sorted(current - set(to_remove))
        return await self.repo.save_global_tags(res)
