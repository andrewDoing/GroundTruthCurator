---
topic: curation-editor
jtbd: JTBD-001
date: 2026-01-22
status: complete
---

# Research: Curation Editor

## Context

The curation editor provides the main workflow to edit ground-truth content (single-turn or multi-turn), apply tags, and transition items through draft/approved/skipped/deleted states.

## Sources Consulted

### URLs
- (None)

### Codebase
- [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts): Maps single-turn items into a multi-turn history format and maps references across top-level and per-turn refs.
- [frontend/src/services/tags.ts](frontend/src/services/tags.ts): Defines tag schema fetch and exclusive-group validation in the UI.

### Documentation
- [.copilot-tracking/research/20260121-high-level-requirements-research.md](.copilot-tracking/research/20260121-high-level-requirements-research.md): Consolidates editor and multi-turn behavior requirements.
- [frontend/CODEBASE.md](frontend/CODEBASE.md): Documents the curation workspace layout and approval gating constraints.
- [backend/CODEBASE.md](backend/CODEBASE.md): Documents API behaviors, including camelCase output and ETag concurrency.
- [backend/docs/multi-turn-refs.md](backend/docs/multi-turn-refs.md): Documents backward-compatible storage and editing semantics for multi-turn refs.
- [backend/docs/tagging_plan.md](backend/docs/tagging_plan.md): Documents tag normalization expectations.

## Key Findings

1. The UI treats all items as multi-turn in its internal model, converting legacy single-turn records into an initial two-message history.
2. The editor supports both top-level references and per-history-turn references, and maps them into a unified reference list for user workflows.
3. Approval is gated by reference completeness rules (at least one selected reference, all references visited, key paragraph constraints).
4. Tagging includes manual and computed tags, and the UI enforces “exclusive group” constraints based on backend-provided schema.
5. Documentation includes some conflicts (for example, tag write paths); when code does not reflect a doc claim, it is treated as doc-only.

## Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| Single-turn to multi-turn normalization | [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts) | Defines current UI behavior and backward compatibility |
| Exclusive tag group validation | [frontend/src/services/tags.ts](frontend/src/services/tags.ts) | Defines validation expectations for tag selection |

## Open Questions

- (None)

## Recommendations for Spec

- Specify the multi-turn normalization rule as a frontend behavior and compatibility expectation.
- Specify tag behaviors in terms of observable constraints (exclusive groups, manual vs computed sets).
- Specify approval gating rules as UX invariants.
