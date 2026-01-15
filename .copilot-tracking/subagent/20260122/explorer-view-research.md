---
topic: explorer-view
jtbd: JTBD-001
date: 2026-01-22
status: complete
---

# Research: Explorer View

## Context

The explorer view enables browsing and filtering ground-truth items outside the assigned queue, and initiating actions such as inspection, assignment, and deletion.

## Sources Consulted

### URLs
- (None)

### Codebase
- [frontend/src/components/app/QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx): Implements an explorer UI with filtering (status/dataset/tags/itemId/refUrl), sorting, pagination, and item actions.
- [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts): Implements `listAllGroundTruths()` and maps API payloads into the frontend model.
- [frontend/src/services/tags.ts](frontend/src/services/tags.ts): Fetches manual/computed tags and validates exclusive tag groups.

### Documentation
- [.copilot-tracking/research/20260121-high-level-requirements-research.md](.copilot-tracking/research/20260121-high-level-requirements-research.md): Provides repo-wide behavioral requirements context.

## Key Findings

1. The explorer supports server-backed listing (`GET /v1/ground-truths`) with query parameters for status, dataset, tags, itemId, refUrl, sorting, and pagination.
2. The explorer fetches and displays available datasets and tags to drive filtering.
3. The explorer UI includes a concept of “inspect” and “assign” actions per item, plus a delete action.
4. The explorer assumes the backend provides pagination metadata when listing items.
5. Doc-only gaps exist in documentation about searching/browsing, but the explorer implementation is the current source of truth.

## Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| Filter state vs applied filter state | [frontend/src/components/app/QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx) | Implements explicit Apply behavior and avoids unnecessary calls |
| Server-side sorting and pagination | [frontend/src/components/app/QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx) | Assumes backend performs sorting and returns pagination |
| List API wrapper mapping wire schema to UI model | [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts) | Defines frontend expectations for list payload shape |

## Open Questions

- (None)

## Recommendations for Spec

- Specify supported explorer filters and sorting fields as observable UI capabilities.
- Specify that the list view uses server-backed pagination when available.
- Specify that explorer actions (inspect/assign/delete) are initiated from the UI but depend on backend support.
