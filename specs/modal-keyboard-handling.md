---
title: Modal Keyboard Handling
description: The modal keyboard handling system prevents key presses in modal inputs from triggering unintended global shortcuts or modal closure.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-507
---

## Overview

When a modal is open, keyboard input inside the modal should be handled by the modal and its focused controls. Global key handlers should not cause the modal to close or the app to navigate unexpectedly.

Parent JTBD: Help SMEs curate ground truth items effectively

## Problem Statement

In the References modal, typing a space in the search field can close the modal. This prevents users from searching effectively and creates a confusing experience.

## Requirements

### Functional Requirements

| ID     | Requirement                                              | Priority | Acceptance Criteria                                                                |
| ------ | -------------------------------------------------------- | -------- | --------------------------------------------------------------------------------- |
| FR-001 | Prevent space key from closing the References modal       | Must     | Pressing space in the modal search input does not close the modal                 |
| FR-002 | Restrict modal closure to explicit close actions          | Must     | Modal closes only via Escape, close button, or clicking outside (as designed)     |
| FR-003 | Disable app-level keyboard shortcuts while a modal is open | Must     | Global keydown handlers do not switch tabs or trigger actions while modal is open |
| FR-004 | Maintain expected focus behavior                          | Should   | Initial focus is set to the search input and remains stable while typing          |

### Non-Functional Requirements

| ID      | Category  | Requirement                                        | Target |
| ------- | --------- | -------------------------------------------------- | ------ |
| NFR-001 | Usability | Keyboard behavior matches common modal conventions | Yes    |

## User Stories

### US-001: User can type spaces in the modal search

As a user, I want to type a multi-word query in the References modal search field, so that I can find references by phrase.

Acceptance criteria:

1. Given the References modal is open and the search field is focused
2. When I type a space character
3. Then the modal remains open
4. And the search field value includes the space

## Technical Considerations

### Event Handling

Use a consistent pattern across modals:

* Capture keydown events inside the modal
* Stop propagation for keys that should not reach global listeners
* Ensure Escape is handled intentionally and consistently

### Global Listeners

The codebase has multiple `window.addEventListener("keydown")` listeners. Consolidate or gate them behind an "is modal open" condition.

## Open Questions

| Q  | Question                                                              | Owner | Status |
| -- | --------------------------------------------------------------------- | ----- | ------ |
| Q1 | Which non-Escape keys should be stopped from propagating for all modals | Team  | Open   |

## References

* SA-507
* [Research file](../.copilot-tracking/subagent/20260122/modal-keyboard-handling-research.md)
