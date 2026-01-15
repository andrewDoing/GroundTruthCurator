# Simplified dataset allocation sampling plan

## Overview

We will replace the current bucket-based sampling with a simple, configuration-driven allocation by dataset. The configuration maps dataset names to percentages (weights). The `sample_unassigned(user_id, limit)` method will:
1) Include items already assigned to the user.
2) Compute per-dataset quotas from the remaining needed count based on configured percentages.
3) Query each dataset for unassigned (or skipped by others) items up to its quota.
4) If any dataset is short, reallocate leftover slots across the remaining datasets and then, if still short, fill from any dataset.
5) Return the combined results; “roughly” matching the requested distribution via integer rounding (largest remainder), with a small tolerance.

We will not implement legacy bucket logic or complex fallback. We’ll start with a single env-based config. If the config is missing, we’ll default to a single “any dataset” pull (i.e., no allocation logic).

## Files to change

- [app/core/config.py](app/core/config.py)
  - Add simple parsing for an environment variable defining dataset sampling allocation.
  - Provide a helper to normalize and validate allocations.

- [app/adapters/repos/cosmos_repo.py](app/adapters/repos/cosmos_repo.py)
  - Simplify [`CosmosGroundTruthRepo.sample_unassigned`](app/adapters/repos/cosmos_repo.py) to use dataset allocation quotas instead of bucket sampling.
  - Add a small helper to query unassigned by dataset with the current filtering (draft unassigned, skipped not assigned to the requesting user).
  - Add a helper to compute integer quotas from percentages (largest remainder method).

- tests/unit/
  - New unit tests for allocation parsing and quota computation helpers.

- tests/integration/
  - Integration tests for the simplified sampling distribution and shortfall handling using the Cosmos emulator.

- environments/
  - Add an example allocation to `.dev.env` and `integration-tests.env`.

## Functions to add or modify

- core/config.py
  - get_sampling_allocation() -> dict[str, float]
    - Reads env var (e.g., GTC_SAMPLING_ALLOCATION) to return a mapping of dataset -> percentage weight. If unspecified or invalid, return an empty dict to signal “no allocation specified.”
  - parse_sampling_allocation_env(value: str) -> dict[str, float]
    - Parse a simple CSV string like "dataset1:50,dataset2:50" or JSON. Keep parsing minimal: support CSV first; later we can add JSON if needed.
  - normalize_allocation(weights: dict[str, float]) -> dict[str, float]
    - Filter out nonpositive entries; normalize to sum to 1.0. If empty after filtering, return {}.

- app/adapters/repos/cosmos_repo.py
  - async def sample_unassigned(self, user_id: str, limit: int) -> list[GroundTruthItem]
    - New logic: return already assigned items first; compute remaining; derive quotas; query per dataset up to quota; handle shortfalls with simple reallocation and final global fill if needed; deduplicate and cap to limit.
  - async def _query_unassigned_by_dataset(self, dataset: str, user_id: str, take: int) -> list[GroundTruthItem]
    - Query for “draft and unassigned” or “skipped and assignedTo != user,” restricted to the dataset; cap to `take` items.
  - def _compute_quotas(weights: dict[str, float], k: int) -> dict[str, int]
    - Convert percentages to integer quotas summing to k using the largest remainder method, ensuring the total equals k.

## Behavior details and constraints

- Configuration source
  - Env var name: GTC_SAMPLING_ALLOCATION
  - Format: CSV "dataset1:50,dataset2:50" (integers or floats allowed).
  - If not set or invalid: no allocation used; we do a simple global unassigned pull as today (but without bucket logic).
- Filtering logic (retain current intent):
  - draft items: (NOT IS_DEFINED(assignedTo) OR IS_NULL(assignedTo) OR assignedTo = '')
  - skipped items: assignedTo != @user_id (to avoid giving the user their own skipped items again)
- Rounding and tolerance
  - Quotas: largest remainder method to exactly sum to remaining limit.
  - Shortfall in a dataset: collect what’s available; keep a leftover counter.
  - Reallocation pass: distribute leftover to other datasets with available supply, roughly in weight order.
  - Final fill: if still short, run a global unassigned query to top up.
  - “Roughly” check: tests assert proportions within ±max(1, 20% of target) to keep it simple and stable for small samples.
- Simplicity choices
  - No bucket scans; no per-bucket balancing.
  - No per-dataset randomization beyond what cross-partition queries provide by default; acceptable for initial version.
  - We avoid adding assignment writes here; assignment remains a separate step.

## Test plan

Unit tests (tests/unit/test_sampling_allocation.py):
- test_parse_sampling_allocation_env_csv_simple
  - Parses "a:50,b:50" into expected weights.
- test_normalize_allocation_normalizes_and_filters_nonpositive
  - Normalizes to sum 1.0; drops zeros/negatives.
- test_compute_quotas_sums_to_k_with_largest_remainder
  - Quotas sum to k; bigger remainders get extra.
- test_compute_quotas_handles_empty_or_zero_weights
  - Returns empty dict or all zeros appropriately.

Integration tests (tests/integration/test_sample_unassigned_allocation.py):
- test_sample_unassigned_respects_50_50_across_two_groups
  - Returned counts per dataset within small tolerance.
- test_sample_unassigned_three_way_50_25_25_distribution
  - Proportions roughly matched with integer rounding.
- test_sample_unassigned_handles_dataset_shortfall_reallocates_leftover
  - If a dataset has few unassigned, others fill the gap.
- test_sample_unassigned_includes_already_assigned_first
  - Starts result with user’s existing assigned items.
- test_sample_unassigned_zero_limit_returns_empty
  - Returns empty when limit <= 0.

Optional integration test (if fixtures exist) (tests/integration/test_sample_unassigned_filters.py):
- test_sample_unassigned_filters_draft_and_skipped_not_assigned_to_user
  - Only draft-unassigned and skipped-assigned-to-other included.

## Minimal config examples

- environments/.dev.env
  - GTC_SAMPLING_ALLOCATION="dataset1:50,dataset2:50"
- environments/integration-tests.env
  - GTC_SAMPLING_ALLOCATION="dsA:50,dsB:25,dsC:25"

## Rollout steps

1) Implement config parsing helper in `app/core/config.py`.
2) Implement `_compute_quotas` and `_query_unassigned_by_dataset` and simplify `sample_unassigned` in `app/adapters/repos/cosmos_repo.py`.
3) Add unit tests for parsing and quotas; add integration tests for distributions and shortfalls.
4) Update `.dev.env` and integration `*.env` with example allocation.
5) Run unit tests and integration tests; iterate if filters/queries need adjustment.
