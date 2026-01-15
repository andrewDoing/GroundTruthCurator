---
title: Validation Error Clarity
description: The validation error clarity system enforces consistent backend and frontend validation and renders user-friendly remediation messages.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-334
---

## Overview

Validation rules should be enforced in the backend and reflected in the UI. When validation fails, the user should see a clear, specific message that explains what to change.

Parent JTBD: Help SMEs curate ground truth items effectively

## Problem Statement

The key paragraph field is communicated as having a 2000 character limit, but the backend does not consistently enforce this limit. When failures occur, the UI often displays a generic error message, which makes it hard for users to correct the issue.

## Requirements

### Functional Requirements

| ID     | Requirement                                                           | Priority | Acceptance Criteria                                                               |
| ------ | --------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------- |
| FR-001 | Enforce a 2000 character limit for the key paragraph in the backend    | Must     | Backend rejects values over 2000 characters with a 4xx status                     |
| FR-002 | Enforce a 2000 character limit in the UI input control                 | Must     | UI prevents typing beyond 2000 characters or blocks save with an inline error    |
| FR-003 | Return a structured validation error for key paragraph length violations | Must     | Error payload includes a code and a field name so UI can map it                   |
| FR-004 | Render a specific, user-friendly message for key paragraph length violations | Must     | UI message includes the 2000 character limit and how to fix it                   |
| FR-005 | Keep backend and frontend validation rules consistent                  | Should   | UI guidance reflects backend constraints and stays in sync as constraints evolve |

### Non-Functional Requirements

| ID      | Category    | Requirement                         | Target |
| ------- | ----------- | ----------------------------------- | ------ |
| NFR-001 | Usability   | Validation messages are actionable  | 1 read |
| NFR-002 | Consistency | UI and backend limits match         | 100%   |

## User Stories

### US-001: User understands key paragraph errors

As a user, I want to see a specific message when my key paragraph is too long, so that I can shorten it quickly.

Acceptance criteria:

1. Given I paste or type a key paragraph longer than 2000 characters
2. When I attempt to save
3. Then I see an error that states the key paragraph must be 2000 characters or less
4. And I can correct the field without losing other edits

## Technical Considerations

### Backend Validation

Prefer Pydantic model validation using `max_length=2000` for the relevant field, with a stable error code.

### Frontend Validation

* Use `maxLength={2000}` for the input
* Display a counter that matches backend constraints
* Map backend error codes to a targeted message rather than a generic toast

## Open Questions

| Q  | Question                                                                                                      | Owner | Status |
| -- | ------------------------------------------------------------------------------------------------------------- | ----- | ------ |
| Q1 | Which field name is canonical for the key paragraph in the API: `keyExcerpt`, `keyParagraph`, or another name | Team  | Open   |

## References

* SA-334
* [Research file](../.copilot-tracking/subagent/20260122/validation-error-clarity-research.md)
