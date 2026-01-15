---
title: Explorer View
description: The explorer view allows curators to browse and filter ground-truth items outside the assigned queue.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Explorer View

## Overview

The explorer view allows curators to browse and filter ground-truth items outside the assigned queue.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

Curators need a way to discover items beyond their assigned queue, filter by various criteria, and initiate actions like inspection, assignment, or deletion from a browseable list.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The explorer shall display a list of ground-truth items with server-backed pagination | Must | Items are fetched from backend with pagination metadata |
| FR-002 | The explorer shall support filtering by status (all/draft/approved/skipped/deleted) | Must | Selecting a status filter refreshes the list |
| FR-003 | The explorer shall support filtering by dataset | Must | Selecting a dataset filter refreshes the list |
| FR-004 | The explorer shall support filtering by tags (manual and computed) | Should | Selecting tags filters the list to matching items |
| FR-005 | The explorer shall support filtering by item ID (exact or prefix match) | Should | Entering an item ID filters the list |
| FR-006 | The explorer shall support filtering by reference URL | Should | Entering a URL filters to items containing that reference |
| FR-007 | The explorer shall support sorting by reference count, reviewed date, and answer presence | Should | Clicking a column header toggles sort direction |
| FR-008 | The explorer shall provide actions to inspect, assign, and delete items | Must | Each item row includes action affordances |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | Filtering shall use an explicit Apply action to avoid excessive API calls | Filters are not applied until user confirms |
| NFR-002 | Usability | Available datasets and tags shall be fetched and displayed for selection | Dropdowns populated from backend |

## User Stories

### US-001: Browse All Items

**As a** curator
**I want to** browse all ground-truth items
**So that** I can find items outside my assigned queue

**Acceptance Criteria:**
- [ ] Given I open the explorer, when items load, then I see a paginated list
- [ ] Given I navigate pages, when I click next/previous, then the list updates

### US-002: Filter by Status

**As a** curator
**I want to** filter items by status
**So that** I can focus on draft, approved, or other categories

**Acceptance Criteria:**
- [ ] Given I select a status filter and click Apply, when the list refreshes, then only matching items appear

### US-003: Assign from Explorer

**As a** curator
**I want to** assign an item to myself from the explorer
**So that** I can claim it for curation

**Acceptance Criteria:**
- [ ] Given I click Assign on an item, when the action completes, then the item is assigned to me

## Technical Considerations

### Data Model

- Explorer fetches items via `GET /v1/ground-truths` with query parameters for filters, sorting, and pagination.
- Pagination metadata includes `total`, `page`, `limit`, `totalPages`.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Backend API | List ground-truths | GET with query params |
| Tags API | Fetch available tags | GET /v1/tags |
| Datasets API | Fetch available datasets | GET /v1/datasets |

### Constraints

- Server performs sorting; client does not re-sort fetched items.
- Filters are applied explicitly via an Apply button.

## Open Questions

(None)

## References

- [frontend/src/components/app/QuestionsExplorer.tsx](../frontend/src/components/app/QuestionsExplorer.tsx)
- [frontend/src/services/groundTruths.ts](../frontend/src/services/groundTruths.ts)
