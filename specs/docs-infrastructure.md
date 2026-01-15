---
title: Documentation Infrastructure
description: Set up MkDocs to provide unified documentation site for GroundTruthCurator
jtbd: JTBD-006
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-835
  - SA-422
---

## Overview

Set up MkDocs with Material theme to unify ~106 scattered markdown files into a single navigable documentation site.

**Parent JTBD:** JTBD-006 - Help teams understand GTC through documentation

## Problem Statement

Documentation exists across five locations (root, `docs/`, `specs/`, `backend/docs/`, `frontend/docs/`) with no unified build system or navigation. Contributors cannot easily discover or browse documentation, and there is no way to generate a static site for hosting. A documentation infrastructure enables:

- Single entry point to all project documentation
- Searchable, navigable documentation site
- Local preview during documentation authoring
- Static site generation for deployment

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | Install MkDocs via `backend/pyproject.toml` optional dependency group | Must | Use `docs` extra group |
| FR-002 | Create `mkdocs.yml` configuration file | Must | Place at repository root |
| FR-003 | Configure Material for MkDocs theme | Must | Standard documentation theme |
| FR-004 | Define navigation structure covering all doc locations | Must | Root, docs/, specs/, backend/docs/, frontend/docs/ |
| FR-005 | Support `mkdocs serve` for local preview | Must | Hot-reload during authoring |
| FR-006 | Support `mkdocs build` for static site generation | Must | Output to `site/` directory |
| FR-007 | Enable built-in search plugin | Should | Default MkDocs search |
| FR-008 | Add `site/` to `.gitignore` | Must | Exclude build artifacts |

### Non-Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| NFR-001 | Documentation builds in under 30 seconds | Should | For ~106 files |
| NFR-002 | Local serve starts in under 5 seconds | Should | Developer experience |
| NFR-003 | No additional runtime dependencies beyond Python | Must | Leverage existing backend environment |

## User Stories

### SA-835

As a contributor, I want to run a single command to preview documentation locally so that I can verify changes before committing.

**Acceptance Criteria:**

- Running `uv run mkdocs serve` from repository root starts local server
- Documentation is accessible at `http://localhost:8000`
- Changes to markdown files trigger automatic reload

### SA-422

As a new team member, I want navigable documentation covering all project areas so that I can understand the system without searching multiple folders.

**Acceptance Criteria:**

- Navigation includes Getting Started, Specifications, Design Docs, Backend Reference, Frontend Reference sections
- All existing markdown files are accessible through navigation
- Search finds content across all documentation

## Technical Considerations

### Configuration File Location

Place `mkdocs.yml` at repository root to:

- Access all documentation folders without path manipulation
- Follow MkDocs convention
- Enable simple `mkdocs serve` invocation

### pyproject.toml Changes

Add to `backend/pyproject.toml`:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
]
```

Install with: `uv pip install -e ".[docs]"` or `uv sync --extra docs`

### Navigation Structure Approach

Organize navigation by audience and content type:

```yaml
nav:
  - Home: README.md
  - Getting Started:
      - Backend Setup: backend/README.md
      - Frontend Setup: frontend/README.md
  - Specifications:
      - Overview: specs/_index.md
      # Individual spec files
  - Design Docs:
      # docs/ folder content
  - Backend Reference:
      # backend/docs/ folder content
  - Frontend Reference:
      # frontend/docs/ folder content
```

### docs_dir Configuration

Since documentation spans multiple directories, configure `docs_dir` to repository root and use relative paths in navigation:

```yaml
docs_dir: .
```

Alternatively, use `mkdocs-monorepo-plugin` if path complexity increases.

## Open Questions

| Question | Impact | Resolution Path |
|----------|--------|-----------------|
| Should `.copilot-tracking/` research files be included in docs? | Navigation complexity | Discuss with team; likely exclude initially |
| Deploy documentation to GitHub Pages or internal hosting? | CI/CD setup | Out of scope for initial setup; future story |
| Include API reference auto-generation from docstrings? | Additional plugins | Out of scope; future enhancement |

## References

- Stories: SA-835, SA-422
- Research: [.copilot-tracking/subagent/20260122/docs-infrastructure-research.md](../.copilot-tracking/subagent/20260122/docs-infrastructure-research.md)
- MkDocs: https://www.mkdocs.org/
- Material for MkDocs: https://squidfunk.github.io/mkdocs-material/
