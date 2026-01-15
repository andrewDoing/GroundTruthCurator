---
title: Reference Management
description: The reference management system supports adding, visiting, and annotating supporting sources.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Reference Management

## Overview

The reference management system supports adding, visiting, and annotating supporting sources.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

Curators need to attach, annotate, and review supporting references that justify ground-truth answers, with enforcement of completeness rules before approval.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The system shall allow adding references with URL, title, and optional snippet | Must | New references appear in the reference list |
| FR-002 | The system shall de-duplicate references by URL | Must | Adding a duplicate URL does not create a second reference |
| FR-003 | The system shall track whether a reference has been visited (opened in new tab) | Must | Opening a reference marks it as visited |
| FR-004 | The system shall allow editing a key paragraph for each reference | Must | Key paragraph field is editable and persisted |
| FR-005 | The system shall display a character counter for key paragraph length | Should | Counter updates as user types |
| FR-006 | The system shall allow removing a reference with an undo window | Should | Removed reference can be restored within a time window |
| FR-007 | The system shall support marking references as bonus | Should | Bonus flag is editable and persisted |
| FR-008 | The system shall associate references with specific conversation turns for multi-turn items | Should | References include a `messageIndex` linking to a turn |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Validation | Key paragraph shall be ≥40 characters for approval eligibility | Character count enforced |
| NFR-002 | UX | All selected references shall be visited before approval | Visited state tracked per reference |

## User Stories

### US-001: Add Reference

**As a** curator
**I want to** add a reference URL to an item
**So that** the ground-truth answer is backed by a source

**Acceptance Criteria:**
- [ ] Given I enter a URL, when I add it, then a new reference appears
- [ ] Given the URL already exists, when I add it, then no duplicate is created

### US-002: Annotate Reference

**As a** curator
**I want to** add a key paragraph excerpt
**So that** reviewers can see the relevant content without opening the source

**Acceptance Criteria:**
- [ ] Given a reference, when I enter a key paragraph, then it is saved with the reference
- [ ] Given a key paragraph <40 chars, when I attempt approval, then it is blocked

### US-003: Visit Reference

**As a** curator
**I want to** open a reference in a new tab
**So that** I can review the source content

**Acceptance Criteria:**
- [ ] Given I click the reference link, when it opens, then the reference is marked visited

## Technical Considerations

### Data Model

- Reference shape: `{ id, title, url, snippet, keyParagraph, visitedAt, bonus, messageIndex }`.
- References are stored both at top-level `refs[]` and per-history-turn `history[].refs[]`.
- Frontend unifies both into a single list for editing.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Backend API | Persist references with item | PUT ground-truth item |

### Constraints

- Approval gating: at least one selected reference, all visited, key paragraph ≥40 chars.
- URL de-duplication is performed in the UI before save.

## Open Questions

(None)

## References

- [frontend/CODEBASE.md](../frontend/CODEBASE.md)
- [frontend/src/services/groundTruths.ts](../frontend/src/services/groundTruths.ts)
- [frontend/src/components/app/defaultCurateInstructions.md](../frontend/src/components/app/defaultCurateInstructions.md)
