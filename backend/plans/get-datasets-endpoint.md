# Get Datasets Endpoint Plan

## Overview

We will add a new `GET /v1/datasets` endpoint that queries Cosmos DB for distinct dataset names from the ground truth items. This replaces the current frontend workaround that parses the `/v1/schemas` endpoint (which returns OpenAPI schemas, not actual data). The endpoint will return a simple list of dataset names that actually exist in the database, with proper integration tests, and update the frontend to consume this new endpoint.

---

## Files to Change

### Backend (5 files)

1. `backend/app/adapters/repos/base.py` — Add protocol method
2. `backend/app/adapters/repos/cosmos_repo.py` — Implement Cosmos query
3. `backend/app/api/v1/datasets.py` — Add GET endpoint
4. `backend/tests/integration/test_datasets_api.py` — New integration test file
5. `backend/app/domain/models.py` — Add response model (if needed)

### Frontend (1 file)

1. `frontend/src/services/datasets.ts` — Update `fetchAvailableDatasets` function

---

## Function Definitions

### 1. Repository Protocol Method

**File:** `backend/app/adapters/repos/base.py`

**Function:** `async def list_datasets(self) -> list[str]`

- **Purpose:** Protocol method that returns a list of distinct dataset names from the ground truth repository.

---

### 2. Cosmos Repository Implementation

**File:** `backend/app/adapters/repos/cosmos_repo.py`

**Function:** `async def list_datasets(self) -> list[str]`

- **Purpose:** Execute a Cosmos SQL query `SELECT DISTINCT VALUE c.datasetName FROM c WHERE c.docType = 'ground-truth-item' ORDER BY c.datasetName` to retrieve unique dataset names.
- **Implementation:** Use `enable_scan_in_query=True` for cross-partition query, iterate results, return sorted list.

---

### 3. API Endpoint

**File:** `backend/app/api/v1/datasets.py`

**Function:** `@router.get("/datasets")`

- **Purpose:** FastAPI GET handler that calls `container.repo.list_datasets()` and returns the list.
- **Response:** `list[str]` (simple JSON array of dataset names)
- **Auth:** Requires user context via `Depends(get_current_user)`

---

### 4. Response Model (Optional)

**File:** `backend/app/domain/models.py`

**Class:** `DatasetsListResponse(BaseModel)` (only if we want structured response)

- **Fields:** `datasets: list[str]`
- **Purpose:** Provide OpenAPI schema for the response; may be overkill for simple list.
- **Decision:** Return plain `list[str]` for simplicity unless structured response needed.

---

### 5. Frontend Service Update

**File:** `frontend/src/services/datasets.ts`

**Function:** `async function fetchAvailableDatasets(): Promise<string[]>`

- **Purpose:** Replace current schemas endpoint parsing with direct call to `GET /v1/datasets`.
- **Implementation:** Use `client.GET("/v1/datasets", {})`, extract data, return sorted list.

---

## Integration Tests

### Test File: `backend/tests/integration/test_datasets_api.py`

**Test 1:** `test_list_datasets_empty_returns_empty_array`

- Import no data, call `GET /v1/datasets`, assert returns `[]`.

**Test 2:** `test_list_datasets_returns_distinct_sorted_names`

- Bulk import items from datasets "alpha", "beta", "alpha" (duplicate), call endpoint, assert returns `["alpha", "beta"]`.

**Test 3:** `test_list_datasets_ignores_non_ground_truth_docs`

- Insert curation-instructions doc with `docType != "ground-truth-item"`, assert not included in results.

**Test 4:** `test_list_datasets_requires_authentication`

- Call endpoint without auth headers, assert 401/403 response.

**Test 5:** `test_list_datasets_with_multiple_buckets_same_dataset`

- Import items from same dataset across different buckets, assert dataset name appears once.

---

## Implementation Notes

- **Cosmos Query:** Use `SELECT DISTINCT VALUE c.datasetName FROM c WHERE c.docType = 'ground-truth-item'` with `ORDER BY c.datasetName` for sorted results. Enable cross-partition scanning.
- **Filter by docType:** Ensure only ground-truth items are counted (exclude curation-instructions, assignment docs, tags).
- **Return Format:** Plain `list[str]` keeps it simple; OpenAPI will auto-generate schema.
- **Error Handling:** If Cosmos query fails, log and return 500; empty results return `[]`.
- **Frontend:** Remove complex parsing logic from `fetchAvailableDatasets`, replace with single API call.

---

## Out of Scope

- ❌ Dataset metadata (counts, last updated, etc.) — keep response minimal
- ❌ Caching or pagination — datasets list expected to be small (<100)
- ❌ Legacy fallback to schemas endpoint — remove old workaround entirely

---

## Validation Steps

1. Run integration test task: `pytest backend/tests/integration/test_datasets_api.py -v`
2. Start backend with Cosmos, seed data, curl `GET /v1/datasets`, verify JSON array
3. Start frontend, verify datasets dropdown populates from new endpoint
4. Check OpenAPI docs at `/v1/docs` — verify `/v1/datasets` appears with correct schema

---

**This plan provides a clean, minimal implementation focused on delivering working functionality without over-engineering.**
