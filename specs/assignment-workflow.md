---
title: Assignment Workflow
description: The assignment workflow manages how curators receive, claim, and complete work items.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Assignment Workflow

## Overview

The assignment workflow manages how curators receive, claim, and complete work items.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

Curators need a predictable way to obtain work items for review, track ownership of in-progress items, and complete items through state transitions, all while preventing conflicts when multiple users are active.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The system shall provide a self-serve assignment endpoint that returns items for a user to work on | Must | Calling self-serve returns assigned items and updates assignment metadata |
| FR-002 | The system shall provide a "my assignments" endpoint returning items currently assigned to the requesting user in draft state | Must | Only draft items assigned to the current user are returned |
| FR-003 | The system shall support single-item self-assign where a user explicitly claims a specific item | Should | Assigning sets status to draft and rejects if another user holds a draft assignment |
| FR-004 | Assignment mutations shall enforce ownership; only the assigned user may modify | Must | Attempts by other users return a stable ownership error |
| FR-005 | Status transitions (approve/skip/delete) shall clear assignment fields atomically | Must | After transition, assignment metadata is removed from the item |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Concurrency | Assignment writes shall use optimistic concurrency via ETag | 412 on missing/mismatch |
| NFR-002 | Consistency | Assignment timestamps shall be timezone-aware UTC | ISO 8601 format with Z suffix |

## User Stories

### US-001: Request Work Items

**As a** curator
**I want to** request new items to work on
**So that** I have a queue of items to review

**Acceptance Criteria:**
- [ ] Given no current assignments, when I call self-serve, then I receive items assigned to me
- [ ] Given existing assignments, when I call self-serve, then I may receive additional items up to limit

### US-002: Claim Specific Item

**As a** curator
**I want to** claim a specific item I found in the explorer
**So that** I can work on it without another user taking it

**Acceptance Criteria:**
- [ ] Given the item is unassigned or assigned to me, when I claim it, then it becomes assigned to me in draft state
- [ ] Given the item is draft-assigned to another user, when I claim it, then I receive a conflict error

### US-003: Complete Work Item

**As a** curator
**I want to** approve, skip, or delete an item
**So that** it is removed from my queue and reflects my decision

**Acceptance Criteria:**
- [ ] Given I own the assignment, when I transition the status, then assignment fields are cleared
- [ ] Given I do not own the assignment, when I attempt a transition, then I receive an ownership error

## Technical Considerations

### Data Model

- Ground-truth items include assignment fields: `assignedTo`, `assignedAt`, `updatedBy`, `updatedAt`, `_etag`.
- A secondary assignment document (materialized view) may exist for fast per-user queries.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Cosmos DB | Persistence | Read/write ground-truth items and assignment documents |

### Constraints

- ETag is required on all write paths; missing or mismatched ETag returns HTTP 412.
- Assignment list responses include `etag` in the JSON body.

## Open Questions

(None)

## References

- [backend/docs/api-change-checklist-assignments.md](../backend/docs/api-change-checklist-assignments.md)
- [backend/docs/assign-single-item-endpoint.md](../backend/docs/assign-single-item-endpoint.md)
- [backend/CODEBASE.md](../backend/CODEBASE.md)
