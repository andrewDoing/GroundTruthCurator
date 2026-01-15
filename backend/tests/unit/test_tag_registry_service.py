from __future__ import annotations

import pytest

from app.services.tag_registry_service import TagRegistryService


class InMemoryTagsRepo:
    def __init__(self) -> None:
        self.tags: list[str] = []

    async def get_global_tags(self) -> list[str]:
        return list(self.tags)

    async def save_global_tags(self, tags: list[str]) -> list[str]:
        self.tags = list(tags)
        return list(self.tags)

    async def upsert_add(self, tags_to_add):
        cur = set(self.tags)
        for t in tags_to_add:
            cur.add(str(t))
        self.tags = sorted(cur)
        return list(self.tags)

    async def upsert_remove(self, tags_to_remove):
        cur = set(self.tags)
        rem = {str(t) for t in tags_to_remove}
        self.tags = sorted(cur - rem)
        return list(self.tags)


@pytest.mark.anyio
async def test_list_initially_empty():
    svc = TagRegistryService(InMemoryTagsRepo())
    assert await svc.list_tags() == []


@pytest.mark.anyio
async def test_add_single_tag_canonicalized_and_sorted():
    svc = TagRegistryService(InMemoryTagsRepo())
    res = await svc.add_tags(["  Topic : Science "])
    assert res == ["topic:science"]
    # order stable
    res = await svc.add_tags(["source:SME"])
    assert res == ["source:sme", "topic:science"]


@pytest.mark.anyio
async def test_add_duplicates_are_deduped():
    repo = InMemoryTagsRepo()
    svc = TagRegistryService(repo)
    await svc.add_tags(["source:sme"])
    res = await svc.add_tags(["Source : SME  ", "source:sme"])
    assert res == ["source:sme"]


@pytest.mark.anyio
async def test_add_multiple_tags_merge_existing():
    repo = InMemoryTagsRepo()
    svc = TagRegistryService(repo)
    await svc.add_tags(["topic:general", "source:user"])
    res = await svc.add_tags(["topic:science", "source:sme"])
    assert res == ["source:sme", "source:user", "topic:general", "topic:science"]


@pytest.mark.anyio
async def test_remove_existing_tag():
    repo = InMemoryTagsRepo()
    svc = TagRegistryService(repo)
    await svc.add_tags(["source:sme", "topic:science"])
    res = await svc.remove_tags(["topic:science"])
    assert res == ["source:sme"]


@pytest.mark.anyio
async def test_remove_nonexistent_tag_noop():
    repo = InMemoryTagsRepo()
    svc = TagRegistryService(repo)
    await svc.add_tags(["source:sme"])
    res = await svc.remove_tags(["topic:science"])
    assert res == ["source:sme"]


@pytest.mark.anyio
async def test_invalid_format_rejected_by_service():
    repo = InMemoryTagsRepo()
    svc = TagRegistryService(repo)
    with pytest.raises(Exception):
        await svc.add_tags(["invalid-tag-without-colon"])
