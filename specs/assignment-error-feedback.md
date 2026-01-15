---
title: Assignment Error Feedback
description: The assignment error feedback system displays specific, actionable messages when assignment operations fail due to conflicts.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-825
---

## Overview

When an assignment operation fails due to an existing assignment, the UI needs enough structured information to explain what happened and what the user can do next.

Parent JTBD: Help SMEs curate ground truth items effectively

## Problem Statement

Today, when a user attempts to assign an item that is already assigned to someone else, the frontend often displays a generic error message. This hides the actionable root cause and prevents the user from quickly identifying the current assignee.

## Requirements

### Functional Requirements

| ID     | Requirement                                                        | Priority | Acceptance Criteria                                                            |
| ------ | ------------------------------------------------------------------ | -------- | ----------------------------------------------------------------------------- |
| FR-001 | Return an explicit conflict response for already-assigned failures | Must     | Backend responds with HTTP 409 for already-assigned conflicts                  |
| FR-002 | Return a structured error payload for already-assigned failures    | Must     | Response body contains `code` and `assignedTo` fields                          |
| FR-003 | Preserve assignee identity for this error case                     | Must     | `assignedTo` is the real assignee identifier (no anonymization for this case) |
| FR-004 | Render a specific toast message for already-assigned failures      | Must     | UI toast includes the assignee in the message and avoids generic wording      |
| FR-005 | Provide an action to view the current assignee                     | Must     | Toast includes an action button that surfaces assignee details in the UI      |
| FR-006 | Fall back gracefully for unknown error formats                     | Should   | UI shows a generic message only when no structured payload is available       |

### Non-Functional Requirements

| ID      | Category    | Requirement                                           | Target |
| ------- | ----------- | ----------------------------------------------------- | ------ |
| NFR-001 | Usability   | Error message is understandable without developer context | 1 read |
| NFR-002 | Consistency | Backend and frontend use the same error code           | 100%   |

## User Stories

### US-001: SME sees who owns the assignment

As a user, I want to see who an item is assigned to when I cannot assign it, so that I can coordinate with the right person.

Acceptance criteria:

1. Given an item is assigned to another user
2. When I click Assign
3. Then I see a toast that states the item is already assigned to that user

### US-002: SME can view assignee details

As a user, I want a one-click way to view the current assignee, so that I can quickly confirm ownership.

Acceptance criteria:

1. Given the already-assigned toast is shown
2. When I click View assignee
3. Then the UI displays the assignee identity in a stable place (modal, side panel, or item details)

## Technical Considerations

### Error Payload

Return a structured payload for this conflict:

```json
{
  "code": "ALREADY_ASSIGNED",
  "message": "Item is already assigned to another user",
  "assignedTo": "alice@example.com"
}
```

### Status Codes

* Use HTTP 409 for assignment conflicts
* Avoid HTTP 500 for expected business conflicts

### Frontend Mapping

* Parse the backend payload and map `code=ALREADY_ASSIGNED` to a dedicated UX path
* Use the existing toast system action support for the View assignee affordance

## Open Questions

| Q  | Question                                                            | Owner | Status |
| -- | ------------------------------------------------------------------- | ----- | ------ |
| Q1 | What UI surface should the View assignee action open by default      | Team  | Open   |

## References

* SA-825
* [Research file](../.copilot-tracking/subagent/20260122/assignment-error-feedback-research.md)
