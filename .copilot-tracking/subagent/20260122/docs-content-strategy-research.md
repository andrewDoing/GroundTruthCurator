# Documentation Content Strategy Research

## Overview

This research assesses the current documentation landscape for Ground Truth Curator, identifying audience fit, staleness, and organization recommendations.

---

## 1. Documentation Inventory

### Root Level

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| [README.md](README.md) | Developers | **Stub** | Single-line placeholder only |
| [AGENTS.md](AGENTS.md) | AI Agents | Current | Jujutsu workflow instructions |
| [BUSINESS_VALUE.md](BUSINESS_VALUE.md) | Stakeholders/SMEs | Current | Value proposition and KPIs |

### Backend (`backend/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| [README.md](backend/README.md) | Developers | **Current** | Comprehensive local setup guide |
| [CODEBASE.md](backend/CODEBASE.md) | Developers | **Current** | Architecture map, contracts, extension points |

#### Backend Docs (`backend/docs/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| export-pipeline.md | Developers | **Current** | Export API and storage backends |
| OBSERVABILITY_IMPLEMENTATION.md | Developers/Ops | Current | Telemetry setup |
| api-write-consolidation-plan.md | Developers | **Stale/Plan** | AI-generated implementation plan |
| api-write-consolidation-plan.v2.md | Developers | **Stale/Plan** | Superseded plan version |
| fastapi-implementation-plan.md | Developers | **Stale/Plan** | Original MVP implementation plan |
| drift_cleanup.md | Developers | **Stale/Plan** | API drift analysis (completed work) |
| tagging_plan.md | Developers | Partially current | Tag behavior reference |
| cosmos-emulator-limitations.md | Developers | Current | Emulator workarounds |
| cosmos-emulator-unicode-workaround.md | Developers | Current | Unicode escape fix |
| todos.md | Developers | **Stale** | Old MVP checklist |
| multi-turn-refs.md | Developers | Current | Multi-turn data model |
| history-tags-feature.md | Developers | Current | History item tags |
| user-self-serve-plan.md | Developers | **Stale/Plan** | Implemented feature |
| assign-single-item-endpoint.md | Developers | **Stale/Plan** | Endpoint design doc |
| pytest-fastapi-cosmos-emulator-best-practices.md | Developers | Current | Testing guidance |

### Frontend (`frontend/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| [README.md](frontend/README.md) | Developers | **Current** | Local dev guide |
| [CODEBASE.md](frontend/CODEBASE.md) | Developers | **Current** | Architecture map and contracts |

#### Frontend Docs (`frontend/docs/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| CONNECT_TO_BACKEND.md | Developers | Current | API types generation guide |
| MVP_REQUIREMENTS.md | Developers/SMEs | **Partially stale** | Original MVP checklist (some items done) |
| REFACTORING_PLAN.md | Developers | **Stale/Plan** | Completed refactor |
| OBSERVABILITY_IMPLEMENTATION.md | Developers | Current | Frontend telemetry |
| connecting-e2e-best-practices.md | Developers | Current | E2E testing patterns |

#### Frontend Plans (`frontend/plans/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| multi-turn-curation-plan.md | Developers | **Stale/Plan** | Implementation plan (in progress) |
| e2e-backend-integration-plan.md | Developers | **Stale/Plan** | Completed integration |
| playwright-e2e-test-plan.md | Developers | **Stale/Plan** | Test setup plan |
| keyboard-shortcuts-plan.md | Developers | **Stale/Plan** | Implemented feature |
| agent-integration-plan.md | Developers | **Stale/Plan** | LLM integration plan |
| telemetry-observability-plan.md | Developers | **Stale/Plan** | Implemented feature |
| *-plan.md (remaining) | Developers | **Stale/Plan** | Various implementation plans |

### Docs Folder (`docs/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| ground-truth-curation-reqs.md | Developers/SMEs | **Canonical** | MVP requirements and data model |
| computed-tags-design.md | Developers | **Current** | Tag architecture and export pipeline |
| manual-tags-design.md | Developers | Current | Manual tag system |
| frontend-runtime-configuration.md | Developers | Current | Runtime config |
| json-export-migration-plan.md | Developers | **Stale/Plan** | Completed migration |

### Specs Folder (`specs/`)

| File | Audience | Status | Notes |
|------|----------|--------|-------|
| _index.md | All | **Current** | Spec index by JTBD |
| assignment-workflow.md | Developers/SMEs | Draft | Current-state spec |
| explorer-view.md | Developers/SMEs | Draft | Current-state spec |
| curation-editor.md | Developers/SMEs | Draft | Current-state spec |
| reference-management.md | Developers/SMEs | Draft | Current-state spec |
| export-snapshots.md | Developers/SMEs | Draft | Current-state spec |
| data-persistence.md | Developers | Draft | Cosmos backend spec |
| observability-operations.md | Developers/Ops | Draft | Health and telemetry spec |
| *-enhancement specs | Developers | Draft | Future feature specs |

---

## 2. Staleness Assessment

### Categories

**Current (Authoritative)**
- Backend README.md and CODEBASE.md
- Frontend README.md and CODEBASE.md
- Export pipeline docs
- Emulator workarounds
- Testing best practices
- Specs index and current-state specs

**Stale/Plan Documents (AI-generated or completed work)**
- `backend/docs/fastapi-implementation-plan.md` - original MVP plan, now implemented
- `backend/docs/api-write-consolidation-plan*.md` - API redesign, mostly complete
- `backend/docs/drift_cleanup.md` - analysis of completed cleanup
- `backend/docs/user-self-serve-plan.md` - implemented
- `backend/docs/todos.md` - outdated checklist
- `frontend/docs/REFACTORING_PLAN.md` - completed refactor
- `frontend/plans/*.md` - most are completed implementation plans
- `docs/json-export-migration-plan.md` - completed migration

**Partially Stale**
- `frontend/docs/MVP_REQUIREMENTS.md` - contains done items mixed with remaining work
- `docs/ground-truth-curation-reqs.md` - canonical but has outdated "todo" items

### Drift Patterns

1. **AI-generated plans remain after implementation** - Plans in `frontend/plans/` and `backend/docs/` were created to guide implementation but weren't archived after completion.

2. **Checklists not updated** - MVP_REQUIREMENTS.md and todos.md have checkboxes that don't reflect current state.

3. **Multiple versions** - api-write-consolidation-plan.md has v1 and v2 without clear indication which is canonical.

---

## 3. Audience Analysis

### Developer Audience

**Well served by:**
- Backend/frontend README.md - local setup
- Backend/frontend CODEBASE.md - architecture understanding
- Export pipeline and emulator docs - specific technical guidance
- Specs folder - system behavior documentation

**Gaps:**
- No consolidated "Getting Started" guide across the full stack
- No API reference (relies on OpenAPI spec)
- No contribution guide
- Architecture diagrams scattered or missing

### SME/Curator Audience

**Well served by:**
- BUSINESS_VALUE.md - value proposition
- ground-truth-curation-reqs.md - requirements context
- Current-state specs - system behavior documentation

**Gaps:**
- **No user guide** - SMEs have no documentation for using the curation UI
- **No workflow guide** - No step-by-step curation workflow documentation
- **No onboarding material** - New SMEs must learn by exploration

### Ops/Admin Audience

**Partially served by:**
- Observability implementation docs
- Backend README deployment section

**Gaps:**
- No runbook for production operations
- No incident response documentation
- Limited deployment documentation

---

## 4. Content Organization Recommendations

### Recommended Structure

```
docs/
├── README.md                    # Documentation hub (NEW)
├── getting-started/
│   ├── quickstart.md           # Full-stack setup (NEW)
│   ├── developer-setup.md      # Detailed dev environment
│   └── sme-onboarding.md       # SME getting started (NEW)
├── user-guides/
│   ├── curation-workflow.md    # SME curation guide (NEW)
│   ├── tagging-guide.md        # How to use tags (NEW)
│   └── export-guide.md         # Export procedures (NEW)
├── architecture/
│   ├── overview.md             # System architecture (NEW)
│   ├── data-model.md           # Consolidated from reqs
│   ├── api-reference.md        # Link to OpenAPI
│   └── backend-internals.md    # From CODEBASE.md
├── operations/
│   ├── deployment.md           # Deploy to Azure (NEW)
│   ├── monitoring.md           # Observability guide
│   └── troubleshooting.md      # Common issues (NEW)
├── contributing/
│   ├── CONTRIBUTING.md         # Contribution guide (NEW)
│   └── code-conventions.md     # From specs
└── archive/
    └── plans/                  # Move completed plans here
```

### Migration Actions

1. **Create docs hub** - New README.md in docs/ with navigation

2. **Create SME documentation** - Priority: curation-workflow.md and sme-onboarding.md

3. **Archive stale plans** - Move completed implementation plans to `docs/archive/plans/`

4. **Consolidate duplicates** - Merge api-write-consolidation-plan versions

5. **Update checklists** - Either update or archive MVP_REQUIREMENTS.md and todos.md

6. **Promote specs** - Current-state specs are good; link from docs hub

---

## 5. Summary

### Current State

| Category | Count | Status |
|----------|-------|--------|
| Current/authoritative docs | 15 | Good coverage for developers |
| Stale plan documents | 12+ | Need archival |
| SME-focused docs | 0 | **Critical gap** |
| Ops documentation | 2 | Partial coverage |

### Priorities

1. **High: Create SME user guide** - No documentation for the primary user persona
2. **High: Archive stale plans** - Reduce confusion about authoritative sources
3. **Medium: Create docs hub** - Improve discoverability
4. **Medium: Getting started guide** - Reduce onboarding friction
5. **Low: Ops runbook** - Needed for production but can follow launch

### Key Findings

- **Developer docs are strong** - README and CODEBASE files provide good guidance
- **SME docs are absent** - Critical gap for the primary user audience
- **Plan documents create noise** - 12+ stale plans remain in active locations
- **Specs are well-organized** - JTBD-based spec structure is effective
- **No contribution guide** - Missing standard OSS documentation
