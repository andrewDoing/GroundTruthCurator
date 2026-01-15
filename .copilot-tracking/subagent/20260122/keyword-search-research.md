# Keyword Search Research

## Research Questions Answered

### 1. How does the Explorer currently fetch and display ground truth items?

The Explorer component ([frontend/src/components/app/QuestionsExplorer.tsx](../../../frontend/src/components/app/QuestionsExplorer.tsx)) fetches data via `listAllGroundTruths()` from the groundTruths service. Key behaviors:

- **Server-side pagination and filtering**: Uses `GET /v1/ground-truths` with query parameters
- **Filter state vs applied state**: Separates filter UI state from applied/committed filters to batch changes
- **Explicit Apply button**: Users must click "Apply Filters" to send filter changes to backend
- **Parameters supported**: `status`, `dataset`, `tags`, `itemId`, `refUrl`, `sortBy`, `sortOrder`, `page`, `limit`

### 2. What data fields exist on ground truth items that would need to be searched?

From [frontend/src/models/groundTruth.ts](../../../frontend/src/models/groundTruth.ts) and [backend/app/domain/models.py](../../../backend/app/domain/models.py):

**Primary text fields for keyword search:**
| Field | Type | Description |
|-------|------|-------------|
| `question` | string | The question text (derived from `synthQuestion` or `editedQuestion`) |
| `answer` | string | The answer text |
| `history` | ConversationTurn[] | Multi-turn conversation history |
| `history[].content` (msg) | string | Individual turn content (user or agent) |
| `comment` | string | Free-form curator notes |

**History/ConversationTurn structure (multi-turn):**
```typescript
type ConversationTurn = {
  role: "user" | "agent";
  content: string;
  expectedBehavior?: ExpectedBehavior[];
};
```

**Backend HistoryItem model:**
```python
class HistoryItem(BaseModel):
    role: HistoryItemRole  # User or Assistant
    msg: str
    refs: Optional[list[Reference]] = None
    expected_behavior: Optional[list[ExpectedBehavior]]
```

### 3. Is there any existing search functionality in the frontend or backend?

**Backend search service exists but serves a different purpose:**

- **File:** [backend/app/api/v1/search.py](../../../backend/app/api/v1/search.py)
- **Endpoint:** `GET /v1/search?q=<query>&top=<limit>`
- **Purpose:** Queries an external AI Search index for reference documents (not ground truth items)
- **Implementation:** Delegates to `SearchService.query()` which uses a `SearchAdapter` for external search backends

**Current filtering in Explorer (not keyword search):**
- `itemId`: Case-sensitive partial match on item ID
- `refUrl`: Case-sensitive partial match on reference URLs (item-level and history-level)
- `tags`: Filter by manual/computed tags (AND logic)
- `status`, `dataset`: Exact match filters

**No existing keyword search for question/answer/history text content.**

### 4. What API endpoints does the Explorer use to fetch items?

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /v1/ground-truths` | GET | List/filter ground truths with pagination |
| `GET /v1/ground-truths/{datasetName}/{bucket}/{item_id}` | GET | Get single item by ID |
| `PUT /v1/ground-truths/{datasetName}/{bucket}/{item_id}` | PUT | Update item |
| `DELETE /v1/ground-truths/{datasetName}/{bucket}/{item_id}` | DELETE | Soft-delete item |

**List endpoint query parameters:**
- `status`: Filter by status (draft, approved, skipped, deleted)
- `dataset`: Filter by dataset name
- `tags`: Comma-separated list of tags (AND logic)
- `itemId`: Partial ID match
- `refUrl`: Partial reference URL match
- `sortBy`: Sort field (reviewedAt, totalReferences, hasAnswer)
- `sortOrder`: asc or desc
- `page`, `limit`: Pagination

### 5. How is the data structured in Cosmos DB and what indexes exist?

**Container structure:**
- Uses MultiHash partition key: `[/datasetName, /bucket]`
- Ground truth items have `docType: "ground-truth-item"`

**Indexing policy** from [backend/scripts/indexing-policy.json](../../../backend/scripts/indexing-policy.json):

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [{ "path": "/*" }],
  "excludedPaths": [{ "path": "/\"_etag\"/?" }],
  "compositeIndexes": [
    // For sorting by reviewedAt, updatedAt, totalReferences
    [{"path": "/reviewedAt", "order": "descending"}, {"path": "/id", "order": "ascending"}],
    [{"path": "/totalReferences", "order": "descending"}, {"path": "/id", "order": "ascending"}],
    // ... more composite indexes for combined status + sort scenarios
  ],
  "fullTextIndexes": []  // Currently empty - no full-text search indexes
}
```

**Key finding:** `fullTextIndexes` array is empty. Cosmos DB does support full-text search via `FullTextContains()` function, but requires explicit full-text indexing configuration.

---

## Key Findings Summary

### Current State
1. **No keyword search exists** for searching text content in questions, answers, or multi-turn history
2. Explorer supports filtering by ID, URL, tags, status, and dataset - but not text content
3. An external search service exists but searches reference documents, not ground truth items
4. Cosmos DB full-text indexing is not currently configured

### Fields to Search
For comprehensive keyword search across all conversation text:
- `synthQuestion` / `editedQuestion` (question text)
- `answer`
- `history[*].msg` (all turn content - both user and agent messages)
- Optionally: `comment` (curator notes)

### Implementation Considerations

**Option A: In-memory filtering (simple, limited scale)**
- Fetch all items matching other filters, filter in memory
- Pros: No infrastructure changes
- Cons: Poor performance with large datasets, RU cost for fetching all items

**Option B: Cosmos DB full-text search**
- Add full-text indexes to indexing policy
- Use `FullTextContains()` or `FullTextScore()` in queries
- Pros: Native Cosmos support, server-side filtering
- Cons: Requires index configuration, may not work with Cosmos emulator

**Option C: Azure AI Search integration**
- Index ground truth items in Azure AI Search
- Leverage existing `SearchService` pattern
- Pros: Advanced search capabilities, ranking
- Cons: Additional infrastructure, sync complexity

### Recommended Next Steps
1. Determine scale requirements (how many items, how often searched)
2. Decide on search scope (question only vs all text fields vs multi-turn history)
3. Evaluate Cosmos DB full-text search feasibility (emulator compatibility)
4. Design API contract for keyword search parameter

---

## Sources Consulted

### Codebase Files
- [frontend/src/components/app/QuestionsExplorer.tsx](../../../frontend/src/components/app/QuestionsExplorer.tsx) - Explorer component implementation
- [frontend/src/models/groundTruth.ts](../../../frontend/src/models/groundTruth.ts) - Frontend data model
- [frontend/src/services/groundTruths.ts](../../../frontend/src/services/groundTruths.ts) - API service layer
- [backend/app/api/v1/ground_truths.py](../../../backend/app/api/v1/ground_truths.py) - Ground truths API endpoints
- [backend/app/api/v1/search.py](../../../backend/app/api/v1/search.py) - Existing search endpoint
- [backend/app/domain/models.py](../../../backend/app/domain/models.py) - Backend data models
- [backend/app/services/search_service.py](../../../backend/app/services/search_service.py) - Search service implementation
- [backend/app/adapters/repos/cosmos_repo.py](../../../backend/app/adapters/repos/cosmos_repo.py) - Cosmos DB repository
- [backend/scripts/indexing-policy.json](../../../backend/scripts/indexing-policy.json) - Cosmos DB index configuration
