---
title: Curation Editor
description: The curation editor enables viewing and editing ground-truth content, including tags.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Curation Editor

## Overview

The curation editor enables viewing and editing ground-truth content, including tags.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

Curators need a workspace to view and edit question/answer content, manage conversation history for multi-turn items, apply tags, and transition items through workflow states while meeting approval gating requirements.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The editor shall display and edit single-turn items (question + answer) | Must | Single-turn items render with editable question and answer fields |
| FR-002 | The editor shall display and edit multi-turn items (conversation history) | Must | Multi-turn items render as a timeline with editable turns |
| FR-003 | The editor shall normalize legacy single-turn items into multi-turn format in the UI | Must | A single-turn item appears as a two-message history (user, agent) |
| FR-004 | The editor shall support adding, editing, and removing conversation turns | Should | Turn management controls are available for multi-turn items |
| FR-005 | The editor shall display manual and computed tags and allow editing manual tags | Must | Tags are shown; manual tags can be added/removed |
| FR-006 | The editor shall enforce exclusive tag group constraints | Must | Selecting a second value in an exclusive group replaces the first |
| FR-007 | The editor shall gate approval on reference completeness rules | Must | Approval is disabled until rules are met |
| FR-008 | The editor shall support status transitions: approve, skip, delete, restore | Must | Transition buttons update item status |
| FR-009 | The editor shall detect no-op saves and report "No changes" | Should | Saving unchanged content does not issue an update |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Concurrency | Saves shall use optimistic concurrency via ETag | 412 on conflict |
| NFR-002 | Compatibility | Multi-turn storage format is backward-compatible with single-turn readers | Existing consumers unaffected |

## User Stories

### US-001: Edit Answer

**As a** curator
**I want to** edit the answer for an item
**So that** I can correct or improve the ground-truth response

**Acceptance Criteria:**
- [ ] Given an item is displayed, when I edit the answer field and save, then the updated answer is persisted

### US-002: Apply Tags

**As a** curator
**I want to** apply tags to an item
**So that** it can be categorized and filtered

**Acceptance Criteria:**
- [ ] Given tags are displayed, when I select a manual tag and save, then the tag is persisted
- [ ] Given an exclusive group, when I select a second value, then it replaces the first

### US-003: Approve Item

**As a** curator
**I want to** approve an item after review
**So that** it is marked complete and included in exports

**Acceptance Criteria:**
- [ ] Given reference rules are met, when I click Approve, then status changes to approved
- [ ] Given reference rules are not met, when I attempt Approve, then it is disabled with explanation

## Technical Considerations

### Data Model

- Items include `history[]` with `{ role, msg, refs[], expectedBehavior[] }` for multi-turn.
- Items include `tags[]`, `manualTags[]`, `computedTags[]`.
- Items include `status` (draft/approved/skipped/deleted) and `_etag`.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Backend API | Update ground-truth | PUT with ETag |
| Tags API | Fetch schema and validate exclusive groups | GET /v1/tags/schema |

### Constraints

- Approval gating rules: at least one selected reference, all references visited, key paragraph ≥40 chars for selected references.
- Deleted items cannot be approved; they can only be restored.

## Open Questions

(None)

## References

- [frontend/CODEBASE.md](../frontend/CODEBASE.md)
- [frontend/src/services/groundTruths.ts](../frontend/src/services/groundTruths.ts)
- [backend/docs/multi-turn-refs.md](../backend/docs/multi-turn-refs.md)
- [backend/docs/tagging_plan.md](../backend/docs/tagging_plan.md)
