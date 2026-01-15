---
title: CI Code Quality
description: The CI code quality enforcement adds linting, formatting, and pre-push hooks with drift reconciliation.
jtbd: JTBD-003
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# CI Code Quality

## Overview

The CI code quality enforcement adds linting, formatting, and pre-push hooks with drift reconciliation.

**Parent JTBD:** Help developers maintain GTC code quality

**Stories:** SA-745

## Problem Statement

The GTC repository has linting and formatting tools configured but:

1. **CI does not enforce them**: Tests run, but lint/format checks are absent from CI workflows
2. **Frontend has drift**: 31 formatting and import organization errors exist
3. **No frontend hooks**: Backend has pre-commit hooks; frontend has none
4. **Environment alignment unclear**: No documented tool version requirements

## Current State

### Backend (Python)

| Aspect | Status |
|--------|--------|
| Tools | Ruff (lint + format), ty (types), Vulture (dead code) |
| Hooks | pre-commit + pre-push configured |
| CI | Tests only; no lint/format checks |
| Drift | ✅ None |

### Frontend (TypeScript)

| Aspect | Status |
|--------|--------|
| Tools | Biome (lint + format), TypeScript, Knip (dead code) |
| Hooks | ❌ None configured |
| CI | Type check only; no lint/format checks |
| Drift | ❌ 31 errors |

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Reconcile frontend drift | Must | `npm run lint` exits cleanly |
| FR-002 | Add backend lint/format to CI | Must | CI fails on lint violations |
| FR-003 | Add frontend lint/format to CI | Must | CI fails on Biome violations |
| FR-004 | Configure frontend pre-push hooks | Must | Biome runs before push |
| FR-005 | Document environment setup | Should | README includes tool version requirements |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | CI Performance | Lint jobs complete quickly | <2 minutes added |
| NFR-002 | Developer Experience | Hooks run fast locally | <10 seconds |
| NFR-003 | Consistency | All developers use same tool versions | Documented in README |

## User Stories

### US-001: Developer pushes clean code

**As a** frontend developer
**I want to** have pre-push hooks catch formatting issues
**So that** CI doesn't fail due to trivial style violations

**Acceptance Criteria:**

- [ ] Given uncommitted formatting violations, when I run `git push`, then hooks block the push and show violations
- [ ] Given clean code, when I run `git push`, then hooks pass silently

### US-002: Reviewer trusts CI status

**As a** code reviewer
**I want to** trust that CI catches style issues
**So that** I can focus on logic during review

**Acceptance Criteria:**

- [ ] Given a PR with lint violations, when CI runs, then the PR is blocked with clear error messages
- [ ] Given a PR with formatting issues, when CI runs, then the job fails with actionable output

## Technical Considerations

### CI Workflow Changes

Add to `.github/workflows/gtc-ci.yml`:

```yaml
jobs:
  backend-lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - name: Ruff lint
        run: uv run ruff check app
      - name: Ruff format check
        run: uv run ruff format app --check

  frontend-lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - name: Biome check
        run: npx biome check
```

### Frontend Pre-push Hooks

**Option A: Extend pre-commit (Recommended)**

Add to root `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/biomejs/pre-commit
    rev: v0.6.1
    hooks:
      - id: biome-check
        additional_dependencies: ["@biomejs/biome@1.9.4"]
        files: ^frontend/.*\.(ts|tsx|js|json)$
        stages: [pre-push]
```

**Option B: Husky (Alternative)**

```bash
cd frontend
npm install --save-dev husky
npx husky init
echo "cd frontend && npm run lint" > .husky/pre-push
```

### Drift Reconciliation Commands

```bash
# Fix frontend drift (31 errors)
cd frontend && npm run lint

# Verify backend is clean
cd backend && uv run ruff check app && uv run ruff format app --check
```

### Tool Versions to Document

| Tool | Version | Location |
|------|---------|----------|
| Node.js | 20.x | `frontend/package.json` engines |
| Python | 3.12+ | `backend/pyproject.toml` |
| uv | Latest | `backend/README.md` |
| Biome | 1.9.4 | `frontend/package.json` devDependencies |
| Ruff | 0.11.x | `backend/pyproject.toml` |

### Constraints

- Pre-commit framework already in use for backend
- Biome is the only frontend linter (no ESLint/Prettier)
- CI uses GitHub Actions
- Must not significantly increase CI time

## Implementation Phases

### Phase 1: Reconcile Drift

1. Run `npm run lint` in frontend
2. Commit formatting fixes
3. Verify `npx biome check` passes

### Phase 2: Add CI Enforcement

1. Add `backend-lint` job to CI workflow
2. Add `frontend-lint` job to CI workflow
3. Verify PR status checks work

### Phase 3: Configure Frontend Hooks

1. Choose hook approach (pre-commit extension or husky)
2. Configure hooks
3. Document hook installation in README

### Phase 4: Document Environment

1. Add `engines` field to `frontend/package.json`
2. Update `frontend/README.md` with setup steps
3. Update `backend/README.md` with pre-commit install instructions

## Open Questions

| Q | Question | Owner | Status |
|---|----------|-------|--------|
| Q1 | Use pre-commit extension or husky for frontend hooks? | Frontend team | Open |
| Q2 | Should CI jobs be blocking or advisory initially? | DevOps | Open |

## References

- Research: [.copilot-tracking/subagent/20260122/ci-code-quality-research.md](../.copilot-tracking/subagent/20260122/ci-code-quality-research.md)
- [.github/workflows/gtc-ci.yml](../.github/workflows/gtc-ci.yml)
- [backend/.pre-commit-config.yaml](../backend/.pre-commit-config.yaml)
- [frontend/biome.json](../frontend/biome.json)
