---
title: Documentation Infrastructure Research
description: Research findings on current documentation state and MkDocs setup requirements
author: copilot
ms.date: 2026-01-22
status: complete
---

## Summary

The repository has **no existing MkDocs configuration**. Documentation is scattered across multiple locations with no unified build system. Setting up MkDocs requires creating the configuration from scratch.

## Research Findings

### 1. Existing Documentation Files

**Root-level documentation:**

| File | Purpose |
|------|---------|
| [README.md](../../../README.md) | Minimal project title only |
| [AGENTS.md](../../../AGENTS.md) | Jujutsu version control workflow instructions |
| [BUSINESS_VALUE.md](../../../BUSINESS_VALUE.md) | Business value documentation |

**`docs/` folder (5 files + 1 subfolder):**

| File | Description |
|------|-------------|
| computed-tags-design.md | Tag computation design |
| manual-tags-design.md | Manual tagging design |
| frontend-runtime-configuration.md | Frontend config guide |
| ground-truth-curation-reqs.md | Requirements document |
| json-export-migration-plan.md | Export migration plan |
| images/ | Image assets |
| specs/ | Empty subfolder |

**`specs/` folder (26 specification files):**

Organized specifications with an `_index.md` index file covering:

- JTBD-001: Current-state system specs (7 topics)
- JTBD-002: Curation enhancements (7 topics)
- JTBD-003: Search and filtering (3 topics)
- JTBD-004: Data integrity and security (4 topics)
- JTBD-005: Code quality (4 topics)

**`backend/docs/` folder (17 files):**

Technical documentation including:

- API change checklists and consolidation plans
- Cosmos emulator documentation and workarounds
- Feature plans (tagging, history, multi-turn refs)
- Best practices guides

**`frontend/docs/` folder (5 files):**

- CONNECT_TO_BACKEND.md
- MVP_REQUIREMENTS.md
- OBSERVABILITY_IMPLEMENTATION.md
- REFACTORING_PLAN.md
- connecting-e2e-best-practices.md

**Component READMEs:**

- [backend/README.md](../../../backend/README.md) - Comprehensive setup guide (~300 lines)
- [frontend/README.md](../../../frontend/README.md) - Development guide (~100 lines)
- backend/scripts/README.md
- scripts/README.md

### 2. MkDocs Configuration Status

**No `mkdocs.yml` exists.** File search returned no results.

### 3. Existing Build Tooling

**Root level:** No package.json exists at repository root.

**`backend/pyproject.toml`:**

- Uses `uv` for package management
- No documentation-related scripts or dependencies
- Dependencies: FastAPI, pytest, ruff, black (no mkdocs/sphinx)

**`frontend/package.json`:**

- Standard Vite/React scripts (dev, build, lint, test)
- No documentation scripts
- No documentation dependencies

### 4. Documentation Structure Assessment

| Location | File Count | Content Type |
|----------|------------|--------------|
| Root | 3 | Project overview |
| docs/ | 5 | Design docs, requirements |
| specs/ | 26 | Feature specifications |
| backend/docs/ | 17 | Technical guides |
| frontend/docs/ | 5 | Frontend guides |
| .copilot-tracking/ | 50+ | Research artifacts |

**Total unique documentation files:** ~106 markdown files

## What Needs to Be Set Up

### Required for MkDocs

1. **Create `mkdocs.yml`** at repository root with:
   - Site metadata (name, description, repo URL)
   - Theme configuration (recommend Material for MkDocs)
   - Navigation structure organizing scattered docs
   - Plugin configuration (search, etc.)

2. **Add MkDocs dependencies** to `backend/pyproject.toml`:

   ```toml
   [project.optional-dependencies]
   docs = [
       "mkdocs>=1.6",
       "mkdocs-material>=9.5",
   ]
   ```

3. **Create navigation structure** to unify:
   - Root README as landing page
   - `docs/` as design documentation
   - `specs/` as specifications section
   - `backend/docs/` as backend technical docs
   - `frontend/docs/` as frontend technical docs
   - Component READMEs as quickstart guides

4. **Add scripts** for build/serve:
   - `uv run mkdocs serve` for local development
   - `uv run mkdocs build` for static site generation

### Recommended Navigation Structure

```yaml
nav:
  - Home: index.md
  - Getting Started:
    - Backend Setup: backend/README.md
    - Frontend Setup: frontend/README.md
  - Specifications:
    - Overview: specs/_index.md
    - Current State: specs/assignment-workflow.md
    # ... other specs
  - Design Docs:
    - Tags Design: docs/manual-tags-design.md
    # ... other design docs
  - Backend Reference:
    - API Plans: backend/docs/api-write-consolidation-plan.md
    # ... other backend docs
  - Frontend Reference:
    - Connect to Backend: frontend/docs/CONNECT_TO_BACKEND.md
    # ... other frontend docs
```

## Key Findings Summary

| Question | Answer |
|----------|--------|
| MkDocs configuration exists? | **No** |
| Documentation build tooling? | **None** |
| Documentation locations | 5+ scattered locations |
| Total markdown files | ~106 |
| Setup complexity | Medium (organize existing content) |
