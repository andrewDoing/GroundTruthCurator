---
title: Documentation Content Strategy
description: Dual-audience documentation structure with migration workflow for SME and developer content
jtbd: JTBD-006
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-835
  - SA-422
---

# Documentation Content Strategy

## Overview

Establish a dual-audience documentation structure serving both SME curators and developers, with clear migration paths for existing content and archival strategy for stale plan documents.

**Parent JTBD:** JTBD-006 - Help teams understand GTC through documentation

## Problem Statement

Ground Truth Curator documentation serves two distinct audiences—developers and SME curators—but current content organization fails both:

1. **SME documentation gap**: No user guide exists for the primary user persona. SMEs must learn the curation workflow, tagging system, and export procedures through exploration alone.

2. **Developer docs are scattered**: While README.md and CODEBASE.md files provide strong local guidance, no consolidated getting-started guide spans the full stack.

3. **Plan document drift**: 12+ AI-generated implementation plans remain in active documentation locations after the work they describe has been completed, creating confusion about authoritative sources.

4. **No canonical marking**: Multiple versions of documents (e.g., api-write-consolidation-plan v1 and v2) exist without clear indication of which is current.

## Requirements

| ID | Requirement | Priority | Audience |
|----|-------------|----------|----------|
| REQ-001 | Create SME user guide covering curation workflow, tagging, and exports | High | SME |
| REQ-002 | Create SME onboarding document for new curators | High | SME |
| REQ-003 | Establish docs hub (docs/README.md) with audience-based navigation | High | All |
| REQ-004 | Archive completed implementation plans to docs/archive/plans/ | High | Developers |
| REQ-005 | Create consolidated getting-started guide for full-stack setup | Medium | Developers |
| REQ-006 | Create contribution guide (CONTRIBUTING.md) | Medium | Developers |
| REQ-007 | Mark canonical pages in frontmatter where duplicates exist | Medium | All |
| REQ-008 | Update or archive stale checklists (MVP_REQUIREMENTS.md, todos.md) | Medium | Developers |
| REQ-009 | Add architecture overview diagram linking existing CODEBASE.md files | Low | Developers |
| REQ-010 | Create operations runbook for production deployment | Low | Ops |

## User Stories

### SME Curator Stories

**US-001: Learn curation workflow**
> As an SME curator, I want step-by-step documentation for the curation workflow so I can curate ground truth data without guessing at the interface.

**US-002: Understand tagging system**
> As an SME curator, I want a tagging guide explaining computed vs manual tags so I can apply appropriate metadata to items.

**US-003: Export curated data**
> As an SME curator, I want export documentation so I can generate training datasets in the required format.

### Developer Stories

**US-004: Set up development environment**
> As a developer, I want a single getting-started guide so I can run the full stack locally without navigating multiple README files.

**US-005: Contribute changes**
> As a developer, I want a contribution guide so I understand the workflow for submitting changes.

**US-006: Find authoritative documentation**
> As a developer, I want stale plans archived so I can trust that documentation in active locations reflects current system behavior.

## Technical Considerations

### Content Structure

Recommended documentation hierarchy:

```
docs/
├── README.md                    # Documentation hub with audience navigation
├── getting-started/
│   ├── quickstart.md           # Full-stack setup for developers
│   └── sme-onboarding.md       # SME getting started
├── user-guides/
│   ├── curation-workflow.md    # SME curation guide
│   ├── tagging-guide.md        # Tag usage guide
│   └── export-guide.md         # Export procedures
├── architecture/
│   ├── overview.md             # System architecture
│   └── data-model.md           # Data model reference
├── contributing/
│   └── CONTRIBUTING.md         # Contribution guide
└── archive/
    └── plans/                  # Completed implementation plans
```

### Migration Order

1. **Phase 1 - Foundation**: Create docs/README.md hub, establish archive folder
2. **Phase 2 - SME priority**: Create curation-workflow.md, sme-onboarding.md, tagging-guide.md
3. **Phase 3 - Archive**: Move stale plans to archive, update/remove stale checklists
4. **Phase 4 - Developer consolidation**: Create quickstart.md, CONTRIBUTING.md

### Archive Strategy

Documents to archive immediately:

| Current Location | Reason |
|-----------------|--------|
| backend/docs/fastapi-implementation-plan.md | MVP plan, now implemented |
| backend/docs/api-write-consolidation-plan*.md | API redesign, mostly complete |
| backend/docs/drift_cleanup.md | Completed cleanup analysis |
| backend/docs/user-self-serve-plan.md | Implemented feature |
| backend/docs/todos.md | Outdated checklist |
| frontend/docs/REFACTORING_PLAN.md | Completed refactor |
| frontend/plans/*.md | Completed implementation plans |
| docs/json-export-migration-plan.md | Completed migration |

Archive format: Move to `docs/archive/plans/` with date prefix (e.g., `2025-completed-fastapi-implementation-plan.md`).

### Canonical Page Marking

Add frontmatter to documents where duplicates or versions exist:

```yaml
---
canonical: true
supersedes:
  - api-write-consolidation-plan.md
---
```

## Open Questions

1. **Ops documentation scope**: Should production runbook be in-repo or separate operations documentation?
2. **Archive retention**: How long should archived plans be retained before deletion?
3. **Spec vs user guide boundary**: Should current-state specs serve as user documentation, or maintain separation?

## References

- [Research: Documentation Content Strategy](.copilot-tracking/subagent/20260122/docs-content-strategy-research.md)
- [Specs Index](specs/_index.md)
- [Backend CODEBASE.md](backend/CODEBASE.md)
- [Frontend CODEBASE.md](frontend/CODEBASE.md)
- [Ground Truth Curation Requirements](docs/ground-truth-curation-reqs.md)
