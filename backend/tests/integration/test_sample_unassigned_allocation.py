from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest
from httpx import AsyncClient


def make_item(dataset: str) -> dict[str, Any]:
    return {
        "id": f"gt-{uuid4().hex[:8]}",
        "datasetName": dataset,
        "bucket": "00000000-0000-0000-0000-000000000000",
        "status": "draft",
        "samplingBucket": 0,
        "synthQuestion": "Q?",
        "answer": None,
        "refs": [],
        "manualTags": ["source:synthetic", "split:validation"],
    }


@pytest.mark.anyio
async def test_sample_unassigned_zero_limit_returns_empty(async_client: AsyncClient, user_headers):
    # No env var required; zero limit should return empty list via /self-serve
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 0}, headers=user_headers
    )
    assert r.status_code == 200
    data = cast(dict[str, Any], r.json())
    assert data.get("assignedCount") == 0
    assert data.get("assigned") == []


@pytest.mark.anyio
async def test_sample_unassigned_respects_50_50_across_two_groups(
    async_client: AsyncClient, user_headers, monkeypatch
):
    # Force allocation 50/50
    monkeypatch.setenv("GTC_SAMPLING_ALLOCATION", "dsA:50,dsB:50")
    dsA = f"dsA-{uuid4().hex[:4]}"
    dsB = f"dsB-{uuid4().hex[:4]}"
    items = [make_item(dsA) for _ in range(50)] + [make_item(dsB) for _ in range(50)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # ask for 20
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 20}, headers=user_headers
    )
    assert r.status_code == 200
    data = cast(dict[str, Any], r.json())
    assigned = cast(list[dict[str, Any]], data.get("assigned") or [])
    assert len(assigned) == 20
    a = sum(1 for it in assigned if it.get("datasetName") == dsA)
    b = sum(1 for it in assigned if it.get("datasetName") == dsB)
    # within tolerance of target 10/10 -> ±max(1, 20% of target=2) => ±2
    assert abs(a - 10) <= 2
    assert abs(b - 10) <= 2


@pytest.mark.anyio
async def test_sample_unassigned_three_way_50_25_25_distribution(
    async_client: AsyncClient, user_headers, monkeypatch
):
    monkeypatch.setenv("GTC_SAMPLING_ALLOCATION", "dsX:50,dsY:25,dsZ:25")
    dsX = f"dsX-{uuid4().hex[:4]}"
    dsY = f"dsY-{uuid4().hex[:4]}"
    dsZ = f"dsZ-{uuid4().hex[:4]}"
    items = (
        [make_item(dsX) for _ in range(60)]
        + [make_item(dsY) for _ in range(40)]
        + [make_item(dsZ) for _ in range(40)]
    )
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 20}, headers=user_headers
    )
    assert r.status_code == 200
    assigned = cast(list[dict[str, Any]], r.json().get("assigned") or [])
    counts = {
        dsX: sum(1 for it in assigned if it.get("datasetName") == dsX),
        dsY: sum(1 for it in assigned if it.get("datasetName") == dsY),
        dsZ: sum(1 for it in assigned if it.get("datasetName") == dsZ),
    }
    # targets: 10,5,5 with tolerance ±2
    assert abs(counts[dsX] - 10) <= 2
    assert abs(counts[dsY] - 5) <= 2
    assert abs(counts[dsZ] - 5) <= 2


@pytest.mark.anyio
async def test_sample_unassigned_handles_dataset_shortfall_reallocates_leftover(
    async_client: AsyncClient, user_headers, monkeypatch
):
    monkeypatch.setenv("GTC_SAMPLING_ALLOCATION", "few:50,many:50")
    few = f"few-{uuid4().hex[:4]}"
    many = f"many-{uuid4().hex[:4]}"
    items = [make_item(few) for _ in range(3)] + [make_item(many) for _ in range(100)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200
    r = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 20}, headers=user_headers
    )
    assert r.status_code == 200
    assigned = cast(list[dict[str, Any]], r.json().get("assigned") or [])
    c_few = sum(1 for it in assigned if it.get("datasetName") == few)
    c_many = sum(1 for it in assigned if it.get("datasetName") == many)
    # few has at most 3, remaining should be filled by many
    assert c_few <= 3
    assert c_many >= 17
    assert c_few + c_many == 20


@pytest.mark.anyio
async def test_sample_unassigned_includes_already_assigned_first(
    async_client: AsyncClient, user_headers, monkeypatch
):
    monkeypatch.setenv("GTC_SAMPLING_ALLOCATION", "A:50,B:50")
    A = f"A-{uuid4().hex[:4]}"
    B = f"B-{uuid4().hex[:4]}"
    items = [make_item(A) for _ in range(10)] + [make_item(B) for _ in range(10)]
    r = await async_client.post("/v1/ground-truths", json=items, headers=user_headers)
    assert r.status_code == 200

    # First self-serve: take 5
    r1 = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 5}, headers=user_headers
    )
    assert r1.status_code == 200
    first = cast(list[dict[str, Any]], r1.json().get("assigned") or [])
    assert len(first) == 5
    first_ids = {it["id"] for it in first}

    # Second self-serve: request 5 again; should include previously assigned first
    r2 = await async_client.post(
        "/v1/assignments/self-serve", json={"limit": 5}, headers=user_headers
    )
    assert r2.status_code == 200
    second = cast(list[dict[str, Any]], r2.json().get("assigned") or [])
    assert len(second) == 5
    second_ids = {it["id"] for it in second}
    # All second ids should be a superset or equal to first_ids (already assigned items are included)
    assert first_ids.issubset(second_ids)
