# Keyword Search

**JTBD:** JTBD-002 - Help users find and filter ground truth items  
**Issue:** SA-828

## Problem Statement

Users cannot search ground truth items by text content. The Explorer supports filtering by status, dataset, tags, item ID, and reference URL, but provides no way to find items containing specific words or phrases in questions, answers, or conversation history.

This limitation forces users to manually scan through paginated results or rely on memory to locate items. As the ground truth collection grows, finding specific items becomes increasingly time-consuming.

## Requirements

### REQ-1: Explorer keyword search input

The Explorer view includes a search input that accepts keyword text.

**Acceptance Criteria:**

- [ ] Search input is visible in the Explorer filter area.
- [ ] Input accepts free-form text entry.
- [ ] Search triggers on explicit apply action (consistent with existing filter behavior).
- [ ] Empty search returns all items (no filter applied).

### REQ-2: Multi-field text matching

Search matches keywords across all text content fields on ground truth items.

**Acceptance Criteria:**

- [ ] Matches `synthQuestion` and `editedQuestion` fields (question text).
- [ ] Matches `answer` field.
- [ ] Matches `history[*].msg` content for all turns (both user and agent roles).
- [ ] Match is case-insensitive.
- [ ] Partial word matching is supported (substring match).

### REQ-3: Results display in Explorer

Search results display using the standard Explorer row format.

**Acceptance Criteria:**

- [ ] Filtered results appear in the existing ground truth list (no separate result UI).
- [ ] Pagination works correctly with search filter applied.
- [ ] Keyword search composes with other filters (status, dataset, tags).
- [ ] Result count reflects the filtered total.

### REQ-4: Clear search state

Users can clear the keyword search to return to unfiltered view.

**Acceptance Criteria:**

- [ ] Clear action removes keyword filter.
- [ ] Other active filters remain when search is cleared.

## Technical Considerations

### Data fields to search

| Field | Location | Description |
|-------|----------|-------------|
| `synthQuestion` | Top-level | Original synthetic question |
| `editedQuestion` | Top-level | User-edited question (overrides synthQuestion) |
| `answer` | Top-level | Answer text |
| `history[*].msg` | Array | Multi-turn conversation content |

### Implementation options

**Option A: In-memory filtering**

- Fetch items matching other filters, apply keyword filter client-side or in API layer.
- Simple to implement, no infrastructure changes.
- Acceptable for initial implementation with moderate dataset sizes.

**Option B: Cosmos DB full-text search**

- Configure `fullTextIndexes` in indexing policy.
- Use `FullTextContains()` in queries for server-side filtering.
- Better performance at scale, but requires index configuration.
- May have emulator compatibility limitations.

**Option C: Azure AI Search integration**

- Index ground truth items in Azure AI Search.
- Leverage existing `SearchService` pattern.
- Best for advanced search features and large scale.
- Adds infrastructure complexity and sync requirements.

### Recommended approach

Start with Option A (in-memory filtering) to prioritize correctness and usability. This aligns with the requirement that no performance optimizations are required initially. Evaluate migration to Option B or C based on actual usage patterns and scale.

### API contract

Add `keyword` query parameter to `GET /v1/ground-truths`:

```text
GET /v1/ground-truths?keyword=<search_text>&status=draft&dataset=test
```

## Out of Scope

The following are explicitly excluded from the initial implementation:

- Fuzzy matching or typo tolerance
- Search ranking or relevance scoring
- Highlighting of matched terms in results
- Search history or saved searches
- Advanced query syntax (AND, OR, phrases)
