---
title: Explorer State Preservation
description: The explorer state preservation system keeps Explorer filters and sorting stable across navigation and actions.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-364
---

## Overview

The Explorer view should preserve user-selected filters and sorting when users take actions such as assigning an item or switching views.

Parent JTBD: Help SMEs curate ground truth items effectively

## Problem Statement

Assigning a ground truth item from the Explorer currently switches the application to the curation view. This unmounts the Explorer component and drops all filters, which disrupts the user workflow.

## Requirements

### Functional Requirements

| ID     | Requirement                                                         | Priority | Acceptance Criteria                                                               |
| ------ | ------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------- |
| FR-001 | Preserve Explorer filter state in the URL                           | Must     | Changing filters updates `location.search` using a stable query parameter schema |
| FR-002 | Restore Explorer filter state from the URL on load                  | Must     | Reloading the page retains the same filters and sorting                          |
| FR-003 | Avoid switching away from Explorer during assignment actions        | Must     | Assigning from Explorer does not force the app into curation view                |
| FR-004 | Allow user-initiated navigation between Explorer and curation views | Must     | A user can switch views without losing Explorer state                            |
| FR-005 | Maintain back and forward browser behavior for filter changes       | Should   | Using back and forward navigates between recent filter states                    |

### Non-Functional Requirements

| ID      | Category  | Requirement                                    | Target |
| ------- | --------- | ---------------------------------------------- | ------ |
| NFR-001 | Usability | URLs are shareable and human-inspectable       | Yes    |
| NFR-002 | Stability | Query parameter schema is backward compatible | Yes    |

## User Stories

### US-001: Explorer filters stay in place

As a user, I want my Explorer filters to remain unchanged after assigning an item, so that I can continue triaging without resetting my view.

Acceptance criteria:

1. Given I have set Explorer filters
2. When I assign an item from the Explorer
3. Then I remain in the Explorer and my filters are unchanged

### US-002: Explorer filters survive reload

As a user, I want my Explorer filters to be encoded in the URL, so that reloading the page does not lose my work.

Acceptance criteria:

1. Given I have set Explorer filters
2. When I reload the page
3. Then the Explorer loads with the same filters and sorting

## Technical Considerations

### Query Parameter Schema

Define a stable set of parameters for Explorer state, for example:

* `q`: keyword search
* `status`: status filter
* `assignedTo`: assignment filter
* `sort`: sort column
* `dir`: sort direction

### No Router Constraint

The app currently does not use a routing library. Implement URL state using `window.history.pushState` and `URLSearchParams` without introducing a router dependency.

## Open Questions

| Q  | Question                                                                  | Owner | Status |
| -- | ------------------------------------------------------------------------- | ----- | ------ |
| Q1 | Which Explorer filters and UI controls should be included in URL state for v1 | Team  | Open   |

## References

* SA-364
* [Research file](../.copilot-tracking/subagent/20260122/explorer-state-preservation-research.md)
