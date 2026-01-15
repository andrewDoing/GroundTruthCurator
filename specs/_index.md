---
title: Specifications Index
description: Index of Jobs to Be Done and their topic specifications.
author: spec-builder
ms.date: 2026-01-22
status: draft
---

## Current-State Specs

### JTBD-001: Help curators review and approve ground-truth data items through an assignment-based workflow

These specs capture the current system behavior across frontend and backend.

| Topic | Spec | Status | Last Updated |
|-------|------|--------|--------------|
| assignment-workflow | [assignment-workflow.md](assignment-workflow.md) | Draft | 2026-01-22 |
| explorer-view | [explorer-view.md](explorer-view.md) | Draft | 2026-01-22 |
| curation-editor | [curation-editor.md](curation-editor.md) | Draft | 2026-01-22 |
| reference-management | [reference-management.md](reference-management.md) | Draft | 2026-01-22 |
| export-snapshots | [export-snapshots.md](export-snapshots.md) | Draft | 2026-01-22 |
| data-persistence | [data-persistence.md](data-persistence.md) | Draft | 2026-01-22 |
| observability-operations | [observability-operations.md](observability-operations.md) | Draft | 2026-01-22 |

## Future Enhancement Specs

### JTBD-002: Help SMEs curate ground truth items effectively (enhancements)

| Topic                      | Spec                                                               | Status |
| -------------------------- | ------------------------------------------------------------------ | ------ |
| assignment-error-feedback  | [assignment-error-feedback.md](assignment-error-feedback.md)        | Draft  |
| assignment-takeover        | [assignment-takeover.md](assignment-takeover.md)                    | Draft  |
| explorer-state-preservation | [explorer-state-preservation.md](explorer-state-preservation.md)    | Draft  |
| draft-duplicate-detection  | [draft-duplicate-detection.md](draft-duplicate-detection.md)        | Draft  |
| modal-keyboard-handling    | [modal-keyboard-handling.md](modal-keyboard-handling.md)            | Draft  |
| validation-error-clarity   | [validation-error-clarity.md](validation-error-clarity.md)          | Draft  |
| inspection-performance     | [inspection-performance.md](inspection-performance.md)              | Draft  |

### JTBD-003: Help users find and filter ground truth items (enhancements)

| Topic            | Spec                                           | Status |
| ---------------- | ---------------------------------------------- | ------ |
| keyword-search   | [keyword-search.md](keyword-search.md)         | Draft  |
| tag-filtering    | [tag-filtering.md](tag-filtering.md)           | Draft  |
| explorer-sorting | [explorer-sorting.md](explorer-sorting.md)     | Draft  |

### JTBD-004: Help administrators ensure data integrity and security

| Topic            | Spec                                           | Status |
| ---------------- | ---------------------------------------------- | ------ |
| pii-detection    | [pii-detection.md](pii-detection.md)           | Draft  |
| dos-prevention   | [dos-prevention.md](dos-prevention.md)         | Draft  |
| xss-sanitization | [xss-sanitization.md](xss-sanitization.md)     | Draft  |
| batch-validation | [batch-validation.md](batch-validation.md)     | Draft  |

### JTBD-005: Help developers maintain GTC code quality

| Topic                    | Spec                                                         | Status |
| ------------------------ | ------------------------------------------------------------ | ------ |
| architecture-refactoring | [architecture-refactoring.md](architecture-refactoring.md)   | Draft  |
| dependency-injection     | [dependency-injection.md](dependency-injection.md)           | Draft  |
| ci-code-quality          | [ci-code-quality.md](ci-code-quality.md)                     | Draft  |
| code-conventions         | [code-conventions.md](code-conventions.md)                   | Draft  |

### JTBD-006: Help teams understand GTC through documentation

| Topic                 | Spec                                                     | Status |
| --------------------- | -------------------------------------------------------- | ------ |
| docs-infrastructure   | [docs-infrastructure.md](docs-infrastructure.md)         | Draft  |
| docs-content-strategy | [docs-content-strategy.md](docs-content-strategy.md)     | Draft  |
| tag-glossary          | [tag-glossary.md](tag-glossary.md)                       | Draft  |

### JTBD-007: Help GTC handle chunked document references correctly

| Topic              | Spec                                           | Status |
| ------------------ | ---------------------------------------------- | ------ |
| reference-identity | [reference-identity.md](reference-identity.md) | Draft  |

### JTBD-008: Help optimize GTC performance and Cosmos usage

| Topic               | Spec                                             | Status |
| ------------------- | ------------------------------------------------ | ------ |
| cosmos-indexing     | [cosmos-indexing.md](cosmos-indexing.md)         | Draft  |
| partial-updates     | [partial-updates.md](partial-updates.md)         | Draft  |
| query-optimization  | [query-optimization.md](query-optimization.md)   | Draft  |
| concurrency-control | [concurrency-control.md](concurrency-control.md) | Draft  |

## Completed Jobs

(None yet)

## Topic Relationship Map

```text
JTBD-001: Current-state system specification
├── assignment-workflow      # How curators receive and complete work
├── explorer-view            # Browsing and filtering outside the queue
├── curation-editor          # Editing content, tags, and status
├── reference-management     # Attaching and annotating sources
├── export-snapshots         # Generating downloadable outputs
├── data-persistence         # Storage abstraction and Cosmos backend
└── observability-operations # Health, telemetry, and error handling

JTBD-002: Help SMEs curate ground truth items effectively (enhancements)
├── assignment-error-feedback
├── assignment-takeover
├── explorer-state-preservation
├── draft-duplicate-detection
├── modal-keyboard-handling
├── validation-error-clarity
└── inspection-performance

JTBD-003: Help users find and filter ground truth items (enhancements)
├── keyword-search
├── tag-filtering
└── explorer-sorting

JTBD-004: Help administrators ensure data integrity and security
├── pii-detection
├── dos-prevention
├── xss-sanitization
└── batch-validation

JTBD-005: Help developers maintain GTC code quality
├── architecture-refactoring
├── dependency-injection
├── ci-code-quality
└── code-conventions

JTBD-006: Help teams understand GTC through documentation
├── docs-infrastructure   # MkDocs setup, build/serve commands
├── docs-content-strategy # Audience organization, migration, drift
└── tag-glossary          # In-app tag definitions and management

JTBD-007: Help GTC handle chunked document references correctly
└── reference-identity    # Chunk ID as primary key instead of URL

JTBD-008: Help optimize GTC performance and Cosmos usage
├── cosmos-indexing       # Limit indexed fields to reduce write RU costs
├── partial-updates       # Patch only changed fields instead of full replacement
├── query-optimization    # Replace expensive cross-partition queries
└── concurrency-control   # Race condition prevention (already implemented)
```

## Research Artifacts

Topic research notes for JTBD-001 are in `.copilot-tracking/subagent/20260122/`:

- [assignment-workflow-research.md](../.copilot-tracking/subagent/20260122/assignment-workflow-research.md)
- [explorer-view-research.md](../.copilot-tracking/subagent/20260122/explorer-view-research.md)
- [curation-editor-research.md](../.copilot-tracking/subagent/20260122/curation-editor-research.md)
- [reference-management-research.md](../.copilot-tracking/subagent/20260122/reference-management-research.md)
- [export-snapshots-research.md](../.copilot-tracking/subagent/20260122/export-snapshots-research.md)
- [data-persistence-research.md](../.copilot-tracking/subagent/20260122/data-persistence-research.md)
- [observability-operations-research.md](../.copilot-tracking/subagent/20260122/observability-operations-research.md)

Topic research notes for JTBD-006 are in `.copilot-tracking/subagent/20260122/`:

- [docs-infrastructure-research.md](../.copilot-tracking/subagent/20260122/docs-infrastructure-research.md)
- [docs-content-strategy-research.md](../.copilot-tracking/subagent/20260122/docs-content-strategy-research.md)
- [tag-glossary-research.md](../.copilot-tracking/subagent/20260122/tag-glossary-research.md)
