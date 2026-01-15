---
title: Draft Duplicate Detection
description: The draft duplicate detection system warns SMEs about likely duplicates of approved items without blocking work.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-534
---

## Overview

When an SME is working on a draft item, the system should detect likely duplicates against approved items and present a soft warning with access to the likely duplicate.

Parent JTBD: Help SMEs curate ground truth items effectively

## Problem Statement

SMEs can spend time curating draft items that are duplicates of already approved items. The tool currently does not detect duplicates, which increases wasted effort and increases the risk of duplicate content entering exports.

## Requirements

### Functional Requirements

| ID     | Requirement                                         | Priority | Acceptance Criteria                                                                |
| ------ | --------------------------------------------------- | -------- | --------------------------------------------------------------------------------- |
| FR-001 | Detect likely duplicates of approved items for a draft | Must     | System computes likely duplicates based on normalized question and answer content |
| FR-002 | Surface duplicates as a soft warning                 | Must     | UI shows a warning but allows the user to proceed                                 |
| FR-003 | Show the likely duplicate item in the warning        | Must     | Warning includes at least one candidate duplicate with a way to open it           |
| FR-004 | Run detection during import and during editing       | Should   | Bulk import can return warnings; edit flows can surface warnings on save          |
| FR-005 | Limit result size for usability                      | Should   | UI shows a small list (for example, top 3 candidates)                             |

### Non-Functional Requirements

| ID      | Category    | Requirement                                 | Target   |
| ------- | ----------- | ------------------------------------------- | -------- |
| NFR-001 | Safety      | Duplicate detection does not block writes    | 100%     |
| NFR-002 | Performance | Duplicate check is acceptable for SME usage | < 1s p95 |

## User Stories

### US-001: SME receives a duplicate warning

As an SME, I want to be warned when the draft item I am editing looks like an approved item, so that I can avoid duplicating work.

Acceptance criteria:

1. Given I am editing a draft item
2. When I save changes
3. Then I see a warning if a likely duplicate exists
4. And the warning includes a way to inspect the approved item

### US-002: Import warns about duplicates

As a user importing items, I want to see duplicate warnings early, so that I can decide whether to continue curation.

Acceptance criteria:

1. Given I run a bulk import
2. When some imported items are likely duplicates of approved items
3. Then the response includes warnings identifying the duplicates

## Technical Considerations

### Comparison Strategy

Use high-signal matching first:

* Normalize whitespace and casing
* Compare `editedQuestion` or `synthQuestion`
* Compare `answer`
* For multi-turn, consider `history[*].msg` only if needed

### API Shape

Prefer returning warnings rather than hard failures. A warning entry should include:

* Duplicate candidate item id
* Duplicate candidate display fields (question, status)
* Similarity rationale (for example, exact question match)

## Open Questions

| Q  | Question                                                                       | Owner | Status |
| -- | ------------------------------------------------------------------------------ | ----- | ------ |
| Q1 | What is the first matching heuristic for v1: question-only, answer-only, or both | Team  | Open   |

## References

* SA-534
* [Research file](../.copilot-tracking/subagent/20260122/draft-duplicate-detection-research.md)
