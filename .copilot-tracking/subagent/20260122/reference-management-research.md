---
topic: reference-management
jtbd: JTBD-001
date: 2026-01-22
status: complete
---

# Research: Reference Management

## Context

The reference management system supports adding, visiting, annotating, and removing supporting references that back ground-truth items.

## Sources Consulted

### URLs
- (None)

### Codebase
- [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts): Maps top-level and per-history references into a unified reference list with `id`, `title`, `url`, `snippet`, `keyParagraph`, `visitedAt`, `bonus`, and `messageIndex`.
- [frontend/CODEBASE.md](frontend/CODEBASE.md): Documents reference workflow behaviors including search, URL de-duplication, visited tracking, and key-paragraph editing.

### Documentation
- [.copilot-tracking/research/20260121-high-level-requirements-research.md](.copilot-tracking/research/20260121-high-level-requirements-research.md): Consolidates reference-related requirements and notes documentation gaps.
- [frontend/src/components/app/defaultCurateInstructions.md](frontend/src/components/app/defaultCurateInstructions.md): Contains user-facing curation instructions including key paragraph constraints.

## Key Findings

1. References include a `keyParagraph` field with a minimum length constraint (≥40 characters) for approval eligibility.
2. The UI tracks whether a reference has been visited (opened in a new tab) and uses this for approval gating.
3. URL de-duplication is performed in the UI to prevent duplicate references.
4. The frontend model unifies top-level `refs` and per-history `refs` into one reference list.
5. References can be marked as "bonus" and can be associated with specific conversation turns via `messageIndex`.

## Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| Reference mapping and normalization | [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts) | Defines current shape of reference objects in UI |
| Approval gating on reference completeness | [frontend/CODEBASE.md](frontend/CODEBASE.md) | Defines behavioral constraints for saving/approving |

## Open Questions

- (None)

## Recommendations for Spec

- Specify the reference data shape (id, title, url, snippet, keyParagraph, visitedAt, bonus, messageIndex).
- Specify the approval gating rules: at least one selected reference, all visited, keyParagraph ≥40 chars.
- Specify URL de-duplication as a UI behavior.
