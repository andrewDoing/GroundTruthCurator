# E2E Backend Integration Test Plan

**Component:** QuestionsExplorer  
**Branch:** `SA-174/gtc-explorer`  
**Created:** October 2, 2025  
**Status:** Planning - Ready for Implementation

---

## **Overview**

Create a robust **end-to-end integration testing** setup that:

1. Manages the full test lifecycle (backend + frontend + database)
2. Seeds test data into Cosmos DB emulator
3. Runs tests against the real backend API
4. Cleans up test data after completion
5. Integrates with the existing Playwright test framework

This will be the **first production-quality integration test** that validates the QuestionsExplorer component against a real backend, complementing the existing E2E UI tests that use demo mode.

---

## **E2E UI Tests vs E2E Integration Tests**

### **E2E UI Tests (Existing - Demo Mode)**

- **Location**: `tests/e2e/*.spec.ts` (e.g., `app.smoke.spec.ts`, `queue-and-editor.spec.ts`)
- **Backend**: Mock data via JSON provider (`VITE_DEMO_MODE=1`)
- **Focus**: UI component behavior, interactions, accessibility
- **Speed**: Fast (~10-30 seconds)
- **Run Command**: `npm run test:e2e`
- **Use Case**: Component behavior validation during development

### **E2E Integration Tests (New - Real Backend)**

- **Location**: `tests/e2e/*-integration.spec.ts` (e.g., `questions-explorer-integration.spec.ts`)
- **Backend**: Real FastAPI + Cosmos DB emulator
- **Focus**: Full-stack workflows, data persistence, API contracts
- **Speed**: Slower (~60-120 seconds)
- **Run Command**: `npm run test:e2e:integration`
- **Use Case**: Feature validation before merges/releases

### **Naming Convention**

- **UI Tests**: `{feature}.spec.ts` - Uses demo mode, fast feedback
- **Integration Tests**: `{feature}-integration.spec.ts` - Uses real backend, comprehensive validation

### **Test Strategy**

```text
Development: Write UI tests first → Fast feedback
Pre-merge: Run integration tests → Validate full stack
CI/CD: UI tests on every commit, integration tests nightly
```

---

## **Files to Create/Modify**

### **New Files**

1. **`tests/e2e/setup/backend-manager.ts`**
   - Manages backend lifecycle (start/stop uvicorn)
   - Waits for backend health check
   - Captures backend logs for debugging

2. **`tests/e2e/setup/integration-helpers.ts`**
   - Shared utilities for integration tests
   - Backend health checks
   - API request helpers

3. **`tests/e2e/setup/test-data.ts`**
   - Defines test data fixtures for QuestionsExplorer
   - Reusable test data across multiple tests

4. **`tests/e2e/setup/api-seeder.ts`**
   - Seeds test data via backend API endpoints
   - Uses `/v1/ground-truths` POST for bulk import
   - Cleanup via DELETE endpoints

5. **`tests/e2e/questions-explorer-integration.spec.ts`**
   - First real integration test for QuestionsExplorer
   - Tests filtering, sorting, pagination against real backend

6. **`tests/e2e/global-setup-integration.ts`**
   - Enhanced global setup for integration tests
   - Starts backend, seeds data, validates infrastructure

7. **`tests/e2e/global-teardown-integration.ts`**
   - Stops backend server
   - Cleans up test data
   - Captures logs on failure

8. **`.env.e2e.integration`**
   - Environment variables for integration tests
   - Cosmos emulator connection strings
   - Backend configuration

9. **`scripts/run-integration-tests.sh`**
   - Shell script to run full integration test suite
   - Validates prerequisites (Cosmos emulator running)

10. **`playwright.config.integration.ts`**
    - Separate Playwright config for integration tests
    - Filters to only run `*-integration.spec.ts` files
    - Different timeouts, webServer config, workers (serial execution)

### **Modified Files**

1. **`package.json`**
   - Add script: `test:e2e:integration` - Run integration tests headless
   - Add script: `test:e2e:integration:ui` - Run integration tests with UI
   - Add script: `test:e2e:all` - Run both UI and integration tests
   - Add dependencies if needed (none expected)

2. **`playwright.config.ts`**
   - Keep existing demo-mode config intact
   - Exclude `*-integration.spec.ts` files from UI test runs
   - Add comment explaining the distinction

3. **`tests/e2e/global-setup.ts`**
   - No changes needed - continues to work for UI tests
   - Integration tests use separate `global-setup-integration.ts`

---

## **Function Names and Purposes**

### **backend-manager.ts**

- **`startBackendServer(port: number): Promise<BackendProcess>`**
  - Spawns uvicorn process using Node child_process
  - Returns process handle and PID for cleanup

- **`waitForBackendHealth(url: string, timeoutMs: number): Promise<void>`**
  - Polls /healthz endpoint until 200 OK
  - Throws error if backend doesn't start in time

- **`stopBackendServer(process: BackendProcess): Promise<void>`**
  - Gracefully stops uvicorn (SIGTERM, then SIGKILL)
  - Waits for process to exit

- **`captureBackendLogs(process: BackendProcess): void`**
  - Pipes stdout/stderr to test output
  - Saves logs to file for debugging failures

### **api-seeder.ts**

- **`seedTestDataViaApi(backendUrl: string, data: TestDataSet): Promise<void>`**
  - Calls `POST /v1/ground-truths` to bulk import test items
  - Uses backend API for all data operations

- **`cleanupTestDataViaApi(backendUrl: string, datasetNames: string[]): Promise<void>`**
  - Calls `DELETE /v1/ground-truths/{dataset}/{bucket}/{id}` for each test item
  - Or uses bulk delete endpoint if available

- **`createQuestionsExplorerTestData(): TestDataSet`**
  - Generates 50+ ground truth items with varied properties
  - Multiple datasets, tags, statuses for filter/sort testing

- **`verifyDataSeededViaApi(backendUrl: string, datasetName: string): Promise<boolean>`**
  - Calls `GET /v1/ground-truths/{dataset}` to verify data exists
  - Returns true if all expected items are retrievable via API

### **test-data.ts**

- **`createGroundTruthItem(overrides?: Partial<GroundTruthItem>): GroundTruthItem`**
  - Factory function for creating test ground truths
  - Randomizes fields for realistic test scenarios

- **`QUESTIONS_EXPLORER_DATASETS: string[]`**
  - Array of dataset names for QuestionsExplorer tests

- **`QUESTIONS_EXPLORER_TAGS: string[]`**
  - Array of tag values for filter testing

- **`QUESTIONS_EXPLORER_TEST_ITEMS: GroundTruthItem[]`**
  - Pre-defined test items with specific properties for assertions

### **integration-helpers.ts**

- **`apiPost(url: string, body: unknown): Promise<Response>`**
  - Helper for POST requests to backend API
  - Includes proper headers and error handling

- **`apiGet(url: string): Promise<Response>`**
  - Helper for GET requests to backend API
  - Includes proper headers and error handling

- **`apiDelete(url: string): Promise<Response>`**
  - Helper for DELETE requests to backend API
  - Includes proper headers and error handling

- **`waitForApiReady(url: string, timeoutMs: number): Promise<void>`**
  - Polls backend until healthy
  - Used in global setup

- **`isIntegrationTest(): boolean`**
  - Returns true if running integration tests
  - Checks for environment variables or config

### **questions-explorer-integration.spec.ts**

- **`test("should load questions from backend")`**
  - Navigates to Questions View
  - Verifies items from seeded data appear in table

- **`test("should filter by status")`**
  - Clicks draft/approved/deleted filter tabs
  - Asserts correct items displayed

- **`test("should filter by dataset")`**
  - Selects dataset from dropdown
  - Verifies only items from that dataset appear

- **`test("should filter by tags (AND logic)")`**
  - Selects multiple tags
  - Asserts only items with ALL selected tags appear

- **`test("should sort by references count")`**
  - Clicks "Refs" column header
  - Verifies ascending/descending sort order

- **`test("should paginate results")`**
  - Changes items per page to 10
  - Navigates through pages
  - Verifies correct items on each page

- **`test("should apply multiple filters together")`**
  - Combines status + dataset + tags filters
  - Verifies intersection logic works

- **`test("should delete item from explorer")`**
  - Clicks delete button on an item
  - Confirms deletion
  - Verifies item moves to "Deleted" filter

### **global-setup-integration.ts**

- **`export default async function globalSetup(config: FullConfig)`**
  - Checks if Cosmos emulator is running (optional health check)
  - Starts backend server via backend-manager
  - Seeds test data via API (api-seeder)
  - Waits for frontend dev server (handled by Playwright webServer)
  - Stores process info in global state file

### **global-teardown-integration.ts**

- **`export default async function globalTeardown(config: FullConfig)`**
  - Reads process info from global state file
  - Stops backend server
  - Cleans up test data via API
  - Captures and saves logs if tests failed

### **run-integration-tests.sh**

- Checks if Cosmos emulator is running on localhost:8081
- Sets environment variables for backend (Cosmos connection string)
- Runs `npx playwright test --config playwright.config.integration.ts`
- Exits with non-zero code if prerequisites not met

---

## **Test Scenarios to Cover**

### **QuestionsExplorer Integration Tests**

1. **Load and Display**
   - Fetches all ground truths across datasets
   - Displays question, status, tags, refs count, reviewed date

2. **Status Filtering**
   - Filter by draft shows only draft items
   - Filter by approved shows only approved items
   - Filter by deleted shows only deleted items
   - Filter by "all" shows all items

3. **Dataset Filtering**
   - Dropdown populated with correct datasets
   - Selecting dataset shows only matching items
   - "All datasets" option shows all items

4. **Tag Filtering (AND logic)**
   - Selecting one tag shows items with that tag
   - Selecting multiple tags shows only items with ALL tags
   - Clearing tags shows all items again

5. **Sorting**
   - Sort by "Has Answer" (Yes before No or vice versa)
   - Sort by "Refs" count (ascending/descending)
   - Sort by "Reviewed" date (most recent first/last)

6. **Pagination**
   - Default page size is 25 items
   - Changing page size updates display
   - Next/Previous buttons work correctly
   - Page count updates based on filters

7. **Combined Filters**
   - Status + Dataset filter combination
   - Status + Tags filter combination
   - Dataset + Tags + Sort combination
   - All filters applied together

8. **Actions**
   - Inspect button opens detail modal
   - Delete button soft-deletes item
   - Deleted item appears in "Deleted" filter

9. **Backend Pagination**
   - Only requested page of items fetched from backend
   - Pagination metadata correct
   - No client-side filtering of large datasets

10. **Error Handling**
    - Backend unavailable shows error message
    - Invalid filter combinations handled gracefully

---

## **Key Implementation Details**

### **Backend Startup Process**

```typescript
// Pseudo-code showing backend startup flow
const backendProcess = spawn('python', [
  '-m', 'uvicorn',
  'app.main:app',
  '--host', '0.0.0.0',
  '--port', '8000',
  '--reload'  // for dev, remove for CI
], {
  cwd: path.resolve(__dirname, '../../../backend'),
  env: {
    ...process.env,
    COSMOS_ENDPOINT: 'https://localhost:8081',
    COSMOS_KEY: 'C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==',
    COSMOS_DB_NAME: 'gtc-test-db',
    // ... other env vars
  },
  stdio: ['pipe', 'pipe', 'pipe']
});
```

### **Data Seeding Strategy**

```typescript
// Create diverse test data for comprehensive testing
const testData = createQuestionsExplorerTestData();

// Seed via API
async function seedData() {
  const response = await fetch('http://localhost:8000/v1/ground-truths', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(testData.items)
  });
  
  if (!response.ok) {
    throw new Error(`Failed to seed data: ${response.status}`);
  }
  
  console.log(`Seeded ${testData.items.length} test items via API`);
}

// Sample test data structure
const testData = {
  datasets: ['e2e-test-dataset-a', 'e2e-test-dataset-b', 'e2e-test-dataset-c'],
  items: [
    // Draft items with varying properties
    ...Array.from({ length: 15 }, (_, i) => createGroundTruthItem({
      id: `e2e-draft-${i}`,
      status: 'draft',
      datasetName: `e2e-test-dataset-${['a','b','c'][i % 3]}`,
      tags: ['tag1', 'tag2'].slice(0, (i % 2) + 1),
      references: Array(i % 5).fill(null).map(() => createReference()),
      reviewedAt: null,
    })),
    // Approved items
    ...Array.from({ length: 20 }, (_, i) => createGroundTruthItem({
      id: `e2e-approved-${i}`,
      status: 'approved',
      datasetName: `e2e-test-dataset-${['a','b','c'][i % 3]}`,
      tags: ['tag2', 'tag3'].slice(0, (i % 3) + 1),
      references: Array((i % 10) + 1).fill(null).map(() => createReference()),
      reviewedAt: new Date(Date.now() - i * 86400000).toISOString(),
      answer: 'This is an approved answer.',
    })),
    // Deleted items
    ...Array.from({ length: 5 }, (_, i) => createGroundTruthItem({
      id: `e2e-deleted-${i}`,
      status: 'deleted',
      datasetName: `e2e-test-dataset-${['a','b','c'][i % 3]}`,
      tags: ['tag1', 'tag3'],
      deleted: true,
    })),
  ],
};
```

### **Cleanup Strategy**

- Use dataset name prefix `e2e-test-` for all test data
- Delete via API endpoints: `DELETE /v1/ground-truths/{dataset}/{bucket}/{id}`
- Run cleanup in global teardown AND before each test (idempotent)
- On test failure, capture API state for debugging
- Alternative: Use bulk delete endpoint if backend provides one

### **Environment Variable Management**

```bash
# .env.e2e.integration
COSMOS_ENDPOINT=https://localhost:8081
COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
COSMOS_DB_NAME=gtc-e2e-tests
COSMOS_CONTAINER_GT=ground-truths
COSMOS_CONTAINER_ASSIGNMENTS=assignments
COSMOS_CREATE_IF_NOT_EXISTS=true
BACKEND_PORT=8000
FRONTEND_PORT=5173
E2E_BACKEND_URL=http://localhost:8000
E2E_WAIT_FOR_BACKEND=1
```

---

## **Prerequisites and Assumptions**

1. **Cosmos DB Emulator** must be running on `localhost:8081`
   - Script checks for emulator health before starting tests
   - Uses well-known emulator key

2. **Backend** is a Python FastAPI app using uvicorn
   - Located at `../backend` relative to frontend
   - Has virtual environment or globally available Python packages

3. **Frontend** dev server managed by Playwright's `webServer` config
   - Remains unchanged from current setup

4. **Test Isolation**: Each test run uses unique database name with timestamp
   - Pattern: `gtc-e2e-tests-{timestamp}`
   - Prevents conflicts between concurrent test runs

5. **No Legacy Fallback**: This is the first real backend integration
   - Demo mode tests remain separate with existing config
   - Integration tests are opt-in via separate command

---

## **Test Execution Flow**

```text
1. Developer runs: npm run test:e2e:integration

2. playwright.config.integration.ts loads

3. globalSetup runs:
   a. Check Cosmos emulator health (optional)
   b. Start backend server (uvicorn)
   c. Wait for backend /healthz
   d. Seed test data via POST /v1/ground-truths API
   e. Playwright starts frontend dev server (automatic)

4. Test suites run:
   - questions-explorer-integration.spec.ts
   - (future: other integration tests)

5. globalTeardown runs:
   a. Stop backend server
   b. Delete test data via DELETE API endpoints
   c. Save logs if failures occurred

6. Exit with test results
```

---

## **Out of Scope (Deliberately Avoided)**

- **Docker Compose**: Keep it simple; assume emulator already running
- **Test Containers**: Not needed for first iteration
- **Multiple Browser Profiles**: Chromium only for integration tests
- **Parallel Workers**: Run integration tests serially to avoid port conflicts
- **CI/CD Integration**: Plan for it, but implement later
- **Backend Test Data Factories**: Use simple TypeScript factories for now
- **Mocking External Services**: Integration tests hit real backend services (search, LLM) if configured

---

## **Success Criteria**

✅ Tests run end-to-end against real backend  
✅ Test data correctly seeded and cleaned up  
✅ All QuestionsExplorer features validated  
✅ Backend logs captured for debugging  
✅ Zero manual setup after Cosmos emulator is running  
✅ Fast feedback loop (< 60 seconds for full suite)  
✅ Failures are debuggable with saved logs and screenshots  

---

## **Summary**

This plan creates a **production-grade e2e test infrastructure** that:

- Manages full application lifecycle (DB → Backend → Frontend)
- Validates the QuestionsExplorer component against a real API
- Provides reusable patterns for future integration tests
- Maintains separation from existing demo-mode tests
- Requires minimal prerequisites (just Cosmos emulator)

The initial test suite will cover **10 core scenarios** for QuestionsExplorer, providing confidence that the component works correctly with the backend API including pagination, filtering, sorting, and CRUD operations.

---

## **Development Workflow**

### **Daily Development (UI Tests)**

```bash
# Fast feedback while developing components
npm run test:e2e          # Run all UI tests
npm run test:e2e:headed   # Debug in browser
npm run test:e2e:ui       # Interactive UI mode
```

### **Pre-Commit (Integration Tests)**

```bash
# Validate full-stack before committing
npm run test:e2e:integration     # Run integration tests
npm run test:e2e:all             # Run both UI + integration
```

### **CI/CD Pipeline**

```yaml
# Example GitHub Actions
on: [push]
jobs:
  ui-tests:
    runs-on: ubuntu-latest
    steps:
      - run: npm run test:e2e
  
  integration-tests:
    runs-on: ubuntu-latest
    services:
      cosmos:
        image: mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator
    steps:
      - run: npm run test:e2e:integration
```

---

## **Implementation Checklist**

### **Phase 1: Setup Infrastructure (Day 1-2)**

- [ ] Create `playwright.config.integration.ts`
- [ ] Create `tests/e2e/setup/backend-manager.ts`
- [ ] Create `tests/e2e/setup/integration-helpers.ts`
- [ ] Create `tests/e2e/global-setup-integration.ts`
- [ ] Create `tests/e2e/global-teardown-integration.ts`
- [ ] Create `scripts/run-integration-tests.sh`
- [ ] Add npm scripts to `package.json`
- [ ] Update `playwright.config.ts` to exclude integration tests

### **Phase 2: Test Data Setup (Day 3)**

- [ ] Create `tests/e2e/setup/test-data.ts`
- [ ] Create `tests/e2e/setup/api-seeder.ts`
- [ ] Implement data seeding via API
- [ ] Implement cleanup via API
- [ ] Test seeding/cleanup manually

### **Phase 3: First Integration Test (Day 4-5)**

- [ ] Create `questions-explorer-integration.spec.ts`
- [ ] Test 1: Load questions from backend
- [ ] Test 2: Filter by status
- [ ] Test 3: Filter by dataset
- [ ] Test 4: Pagination
- [ ] Test 5: Delete item
- [ ] Verify all tests pass

### **Phase 4: Additional Tests (Day 6-7)**

- [ ] Test 6: Filter by tags
- [ ] Test 7: Sort by refs count
- [ ] Test 8: Combined filters
- [ ] Test 9: Error handling
- [ ] Test 10: Backend pagination
- [ ] Add debugging aids (screenshots, logs)

---

**Document Version:** 1.1  
**Last Updated:** October 2, 2025  
**Status:** Ready for Implementation Review
