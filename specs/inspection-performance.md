---
title: Inspection Performance
description: The inspection performance system reduces redundant computation and network requests when inspecting ground truth items.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-566
  - SA-567
---

## Overview

Inspecting items and viewing turn references should feel responsive. Repeated inspections of the same item should avoid unnecessary refetching and expensive recomputation.

Parent JTBD: Help SMEs curate ground truth items effectively

## Problem Statement

The Inspect and Turn References modals perform work on each open and render:

* Inspect fetches item data each time the modal opens
* Turn References recomputes derived reference sets on each render

This increases latency and can make the UI feel sluggish when reviewing items.

## Requirements

### Functional Requirements

| ID     | Requirement                                              | Priority | Acceptance Criteria                                                                      |
| ------ | -------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------- |
| FR-001 | Cache inspected item fetches in-memory per session        | Must     | Opening Inspect for the same item avoids a redundant network call within a session      |
| FR-002 | Invalidate or refresh cache when the item changes         | Must     | After an edit or save, the next inspection shows updated data                           |
| FR-003 | Memoize expensive derived computations in Turn References modal | Must     | Derived reference lists are computed via memoization and not recomputed on every render |
| FR-004 | Keep caching intentionally simple for v1                  | Must     | No new library is required; use existing hooks and patterns                              |

### Non-Functional Requirements

| ID      | Category    | Requirement                                         | Target        |
| ------- | ----------- | --------------------------------------------------- | ------------- |
| NFR-001 | Performance | Inspect modal open latency improves for repeat opens | Noticeable    |
| NFR-002 | Correctness | Cached data does not show stale values after edits  | 0 known issues |

## User Stories

### US-001: Repeat inspect is fast

As a user, I want repeated inspections of the same item to be fast, so that reviewing items does not feel like a series of full reloads.

Acceptance criteria:

1. Given I open Inspect for an item
2. When I close and reopen Inspect for the same item
3. Then the modal loads without waiting on a new fetch (unless invalidated)

### US-002: Turn references render efficiently

As a user, I want the References modal to stay responsive while I search and filter, so that I can review references quickly.

Acceptance criteria:

1. Given the References modal is open
2. When I type into the search box
3. Then reference computations do not rerun unnecessarily on every keystroke

## Technical Considerations

### Caching Strategy

Use a small in-memory cache keyed by item id:

* Scope: per browser session
* Invalidation: clear entry on successful update, or use a short TTL

### Memoization

Use `useMemo` for:

* Filtering references for a selected turn
* Building derived URL sets

## Open Questions

| Q  | Question                                                                                     | Owner | Status |
| -- | -------------------------------------------------------------------------------------------- | ----- | ------ |
| Q1 | What TTL is appropriate for the inspect cache if we cannot reliably invalidate on all edits | Team  | Open   |

## References

* SA-566
* SA-567
* [Research file](../.copilot-tracking/subagent/20260122/inspection-performance-research.md)
