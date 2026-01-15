# Cosmos DB COUNT Query Production Failure (NonValueAggregate)

## Summary

A production 400 BadRequest occurred for a ground-truth pagination endpoint. The Cosmos DB service returned:

```text
Query contains the following features, which the calling client does not support: NonValueAggregate
```

The failing query used an object-style aggregate projection:

```sql
SELECT COUNT(1) AS count FROM c WHERE ...
```

Switching to the canonical VALUE aggregate form fixed the issue:

```sql
SELECT VALUE COUNT(1) FROM c WHERE ...
```

## Root Cause

Cosmos DB differentiates between:

- **VALUE aggregates**: `SELECT VALUE COUNT(1)` → scalar result (e.g. `[42]`)
- **Non-value (object) aggregates**: `SELECT COUNT(1) AS count` → object wrapper

The production account's query planner classified the aliased form as requiring a newer internal feature flag (`NonValueAggregate`). The Python SDK version in use did not advertise support for that capability in the `x-ms-cosmos-supported-query-features` header, so the gateway rejected the request.

In the local emulator the same query succeeded because:

1. Emulator query engine build lagged and did not require the feature, or
2. Simpler test data / indexing led to a plan that avoided the NonValueAggregate path.

## Contributing Factors

| Factor | Impact |
|--------|--------|
| Older `azure-cosmos` Python SDK | Missing advertised support for newer query plan feature |
| Object aggregate projection | Triggered NonValueAggregate plan classification in prod |
| Different data + composite indexes in prod | Allowed optimizer to select the newer feature path |
| Emulator version lag | Masked the incompatibility locally |

## Implemented Fix

1. Replaced non-tag count query with `SELECT VALUE COUNT(1)` (scalar form).
2. Defensive parsing for rare emulator dict forms (`{"$1": n}` / `{"count": n}`).
3. For tag-filtered counts, performed in-memory filtering (fetch tags only) to avoid complex aggregate + ARRAY_CONTAINS combination.
4. Added missing `settings` import to fix `NameError` uncovered during test run.

## Verification

- All relevant integration tests passed after the change (including snapshot + filters + pagination).
- No further 400 BadRequest reproductions locally.
- Logic matches Microsoft documentation examples for COUNT (VALUE syntax).

## Why In-Memory Tag Count?

COUNT with multiple `ARRAY_CONTAINS` predicates can push the planner toward fallback or unsupported feature flags when combined with ordering or other clauses. Fetching minimal fields (`c.tags`) and counting client-side keeps the server query simple and predictable.

## Prevention / Recommendations

| Action | Benefit |
|--------|---------|
| Prefer `SELECT VALUE` for scalar aggregates | Avoids NonValueAggregate path, maximizes portability |
| Periodically upgrade `azure-cosmos` SDK | Gains support for newer query features |
| Add a CI check hitting a staging container with representative aggregate queries | Early detection of capability mismatches |
| Log query + `ActivityId` + status on `CosmosHttpResponseError` | Speeds future root-cause analysis |
| Optionally capture `x-ms-documentdb-query-metrics` for performance tuning | Visibility into index utilization |

## Optional Future Hardening

- Add a unit test that mocks `query_items` returning scalar and `{ "$1": n }` forms.
- Add a diagnostic endpoint or script to print supported query features and SDK version.
- Introduce feature flag to experiment with server-side tag counting once SDK is upgraded.

## TL;DR

Production used a query plan feature (NonValueAggregate) unsupported by the deployed SDK because of the `SELECT COUNT(1) AS count` form. Switching to the documented `SELECT VALUE COUNT(1)` scalar aggregate removed the feature requirement and resolved the error.
