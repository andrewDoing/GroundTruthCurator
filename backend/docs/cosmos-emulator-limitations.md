# Cosmos DB Emulator Limitations

This document outlines known limitations of the Azure Cosmos DB Emulator that affect testing and development.

## ARRAY_CONTAINS SQL Function Not Supported

**Issue:** The Cosmos DB Emulator does not support the `ARRAY_CONTAINS` SQL function, which is used for filtering documents by array field values (such as tags).

**Impact:**
- Tag filtering queries that use `ARRAY_CONTAINS` will fail when run against the emulator
- Integration tests that test tag filtering functionality must be skipped when using the emulator
- Tag filtering works correctly in production Azure Cosmos DB instances

**Affected Features:**
- Ground truth filtering by tags (`/v1/ground-truths?tags=tag1,tag2`)
- Any query that filters on array fields using `ARRAY_CONTAINS`

**Affected Tests:**
- `test_list_all_ground_truths_filter_by_tags` - Tests tag filtering
- `test_list_all_ground_truths_combined_filters` - Tests combined filters including tags

**Workaround:**
- Tests that use tag filtering are marked with `@pytest.mark.skip` and will not run during CI/CD
- These tests should be run manually against a real Cosmos DB instance before production deployment
- In development, tag filtering can be tested using the in-memory fallback path in `cosmos_repo.py`

**Implementation Details:**

The `_list_gt_paginated_with_tags` method in `cosmos_repo.py` implements a fallback mechanism:
1. When tags are provided with sorting, it fetches items without tag filtering
2. Applies tag filtering in-memory in Python
3. Then applies sorting and pagination

This approach works in the emulator but has performance implications for large datasets.

**Production Behavior:**

In production Azure Cosmos DB, the `ARRAY_CONTAINS` function works correctly and enables:
- Server-side tag filtering
- Better performance for queries with tags
- Lower RU consumption

**References:**
- [GitHub Issue: ARRAY_CONTAINS not supported in emulator](https://github.com/Azure/azure-cosmos-db-emulator-docker/issues/45)
- [Cosmos DB SQL Query Reference](https://docs.microsoft.com/en-us/azure/cosmos-db/sql/sql-query-array-contains)

**Testing Recommendations:**

1. **Local Development:** Use emulator for non-tag-filtering tests
2. **Pre-Production:** Run tag filtering tests against a dedicated test Cosmos DB instance
3. **CI/CD:** Skip emulator-incompatible tests, run them in a separate stage against real Cosmos DB
4. **Production Deployment:** Verify tag filtering works correctly in staging environment

**Environment Variable for Test Selection:**

Consider setting an environment variable to conditionally skip/run these tests:

```bash
# Run all tests including those that need real Cosmos DB
GTC_USE_REAL_COSMOS=1 pytest tests/integration/

# Skip tests that don't work with emulator (default behavior)
pytest tests/integration/
```

This could be implemented by replacing `@pytest.mark.skip` with:

```python
import os
pytestmark = pytest.mark.skipif(
    not os.getenv("GTC_USE_REAL_COSMOS"),
    reason="ARRAY_CONTAINS not supported by Cosmos DB Emulator"
)
```

## Intermittent "jsonb type as object key" Delete Errors

**Issue:** The Cosmos DB Emulator occasionally throws intermittent errors when deleting items:

```
azure.cosmos.exceptions.CosmosHttpResponseError: (InternalServerError) unexpected jsonb type as object key
Code: InternalServerError  
Message: unexpected jsonb type as object key
```

Or:

```
azure.cosmos.exceptions.CosmosHttpResponseError: (InternalServerError) unknown type of jsonb container
Code: InternalServerError  
Message: unknown type of jsonb container
```

**Impact:**
- Affects bulk delete operations (like dataset deletion) 
- Error occurs sporadically during `delete_item()` operations
- Does not occur in production Azure Cosmos DB instances

**Affected Operations:**
- Dataset deletion (`/v1/datasets/{datasetName}` DELETE)
- Any operation that deletes multiple items in sequence

**Workaround:**
The `delete_dataset` method in `cosmos_repo.py` implements automatic retry logic:
- Detects the specific error message and emulator environment
- Retries up to 3 times with exponential backoff (0.1s, 0.2s, 0.3s)
- Only retries when using the emulator (localhost endpoint)
- Logs warnings when retries occur

**Implementation Details:**
```python
# Retry logic for intermittent Cosmos DB emulator errors
max_retries = 3
for attempt in range(max_retries):
    try:
        await gt.delete_item(item=it.id, partition_key=[dataset, str(it.bucket)])
        break
    except CosmosHttpResponseError as e:
        error_msg = str(e)
        is_jsonb_error = (
            "unexpected jsonb type as object key" in error_msg
            or "unknown type of jsonb container" in error_msg
        )
        if (
            attempt < max_retries - 1
            and is_jsonb_error
            and self.is_cosmos_emulator_in_use()
        ):
            # Retry with exponential backoff
            await asyncio.sleep(0.1 * (attempt + 1))
            continue
        else:
            raise
```

**Testing:** This fix resolves intermittent test failures in `test_delete_item_and_dataset`.

## Other Known Emulator Limitations

As of November 2025, other known limitations include:

1. **Performance:** Emulator is slower than production Cosmos DB
2. **Partition Key Limits:** Some partition key configurations may behave differently
3. **Consistency Levels:** Emulator always uses "Session" consistency
4. **Regional Failover:** Cannot test multi-region scenarios

For a complete list of emulator limitations, see:
https://docs.microsoft.com/en-us/azure/cosmos-db/emulator#differences-between-the-emulator-and-the-cloud-service

---

**Last Updated:** October 7, 2025
