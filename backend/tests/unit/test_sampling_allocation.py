from __future__ import annotations

import pytest

from app.core.config import parse_sampling_allocation_env, normalize_allocation
from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo


def test_parse_sampling_allocation_env_csv_simple():
    s = "a:50,b:50"
    got = parse_sampling_allocation_env(s)
    assert got == {"a": 50.0, "b": 50.0}


def test_normalize_allocation_normalizes_and_filters_nonpositive():
    raw = {"a": 0.0, "b": -10.0, "c": 30.0, "d": 70.0}
    norm = normalize_allocation(raw)
    assert set(norm.keys()) == {"c", "d"}
    assert pytest.approx(sum(norm.values()), rel=1e-6) == 1.0
    # c:d should be 30:70
    ratio = norm["c"] / norm["d"]
    assert pytest.approx(ratio, rel=1e-6) == 30 / 70


def test_compute_quotas_sums_to_k_with_largest_remainder():
    repo = CosmosGroundTruthRepo(
        endpoint="http://example",
        key="k",
        db_name="db",
        gt_container_name="gt",
        assignments_container_name="assign",
    )
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    q = repo._compute_quotas(weights, 10)
    assert sum(q.values()) == 10
    # Expected floors: 5,3,2 -> already sums to 10; largest remainder would keep same
    assert q["a"] == 5 and q["b"] == 3 and q["c"] == 2


def test_compute_quotas_handles_empty_or_zero_weights():
    repo = CosmosGroundTruthRepo(
        endpoint="http://example",
        key="k",
        db_name="db",
        gt_container_name="gt",
        assignments_container_name="assign",
    )
    assert repo._compute_quotas({}, 5) == {}
    q = repo._compute_quotas({"a": 0.0, "b": -1.0}, 7)
    assert q == {"a": 0, "b": 0}
