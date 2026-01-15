# CI Code Quality Research

**Date:** 2026-01-22
**Topic:** ci-code-quality
**Jira:** SA-745 - Enforce formatting and linters in CI, reconcile drift

---

## Summary

The repository has established linting and formatting tooling for both backend (Python) and frontend (TypeScript), with backend pre-commit hooks configured but **no frontend pre-push hooks**. There is **active drift in the frontend** that needs reconciliation before CI enforcement.

---

## 1. Backend (Python) Configuration

### Package Manager

- **uv** - Modern Python package manager from Astral
- Lock file: [backend/uv.lock](backend/uv.lock)

### Linting/Formatting Tools

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Ruff** | Linting + formatting | [backend/pyproject.toml](backend/pyproject.toml) `[tool.ruff]` |
| **Black** | Formatting (legacy, likely superseded by ruff) | `[tool.black]` section |
| **ty** | Type checking | `[tool.ty]` section |
| **Vulture** | Dead code detection | `[tool.vulture]` section |

### Ruff Configuration

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = [
    "F",       # Pyflakes (F401, F841, F811, etc.)
    "ERA",     # Commented code (ERA001)
    "RUF059",  # Unused unpacked variables
]
```

### Pre-commit Hooks (Backend Only)

File: [backend/.pre-commit-config.yaml](backend/.pre-commit-config.yaml)

| Hook | Stage | Scope |
|------|-------|-------|
| `ruff-format` | pre-commit | `^backend/.*\.py$` |
| `ruff` (lint + fix) | pre-commit | `^backend/.*\.py$` |
| `ty` | pre-commit | `^backend/app/.*\.py$` |
| `pytest` | **pre-push** | Backend tests |

### Current Drift Status

```
✅ Backend lint: All checks passed!
✅ Backend format: 67 files already formatted
```

**No drift in backend.**

---

## 2. Frontend (TypeScript) Configuration

### Package Manager

- **npm** - Standard Node.js package manager
- Lock file: [frontend/package-lock.json](frontend/package-lock.json)

### Linting/Formatting Tools

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Biome** | Linting + formatting | [frontend/biome.json](frontend/biome.json) |
| **TypeScript** | Type checking | `tsc -b` via npm script |
| **Knip** | Dead code detection | [frontend/knip.json](frontend/knip.json) |

### Biome Configuration

```json
{
    "formatter": { "enabled": true },
    "linter": {
        "enabled": true,
        "rules": {
            "correctness": {
                "noUnusedImports": "error",
                "noUnusedVariables": "warn",
                "noUnusedFunctionParameters": "warn",
                "noUnusedPrivateClassMembers": "warn"
            }
        }
    }
}
```

### NPM Scripts

```json
{
    "lint": "biome check --write",
    "typecheck": "tsc -b --pretty false"
}
```

### Pre-commit/Pre-push Hooks

**None configured.** No husky, lefthook, or lint-staged packages present.

### Current Drift Status

```
❌ Frontend: Found 31 errors (formatting + organize imports)
```

**Active drift detected:**

- 2 config files need formatting (`biome.json`, `knip.json`)
- Multiple source files have import organization issues
- Formatting issues in `vitest.config.ts` and source files

---

## 3. CI Workflow Analysis

File: [.github/workflows/gtc-ci.yml](.github/workflows/gtc-ci.yml)

### Current CI Checks

| Check | Type | Status |
|-------|------|--------|
| Backend unit tests | pytest | ✅ Runs |
| Backend integration tests | pytest | ✅ Runs |
| `ty check app` | Type checking | ✅ Runs |
| OpenAPI spec freshness | git diff | ✅ Runs |
| Frontend types check | `api:types:check` | ✅ Runs |
| Frontend tests | vitest | ✅ Runs |
| **Backend lint/format** | ruff | ❌ **Not in CI** |
| **Frontend lint/format** | biome | ❌ **Not in CI** |

### Missing CI Jobs

1. **Backend linting:** `uv run ruff check app`
2. **Backend formatting:** `uv run ruff format app --check`
3. **Frontend linting:** `npx biome check`

---

## 4. Recommendations for SA-745

### Phase 1: Reconcile Drift

1. Run `npm run lint` in frontend to auto-fix 31 errors
2. Commit formatting fixes separately for clean history

### Phase 2: Add CI Enforcement

Add to `.github/workflows/gtc-ci.yml`:

```yaml
- name: Backend lint
  working-directory: backend
  run: uv run ruff check app

- name: Backend format check
  working-directory: backend
  run: uv run ruff format app --check

- name: Frontend lint
  working-directory: frontend
  run: npx biome check
```

### Phase 3: Add Frontend Pre-push Hooks

Options:

1. **Husky** - Most popular, npm-based
2. **Lefthook** - Fast, language-agnostic
3. **Extend pre-commit** - Add frontend hooks to existing backend config

Recommended: Extend existing `pre-commit` framework (already in dev dependencies) with frontend hooks.

### Phase 4: Environment Alignment

- Document required tool versions in README
- Consider adding `engines` field to `package.json`
- Ensure `pre-commit install` is documented in setup instructions

---

## 5. File References

| File | Purpose |
|------|---------|
| [backend/pyproject.toml](backend/pyproject.toml) | Python tools config |
| [backend/.pre-commit-config.yaml](backend/.pre-commit-config.yaml) | Pre-commit hooks |
| [frontend/biome.json](frontend/biome.json) | Biome linter/formatter config |
| [frontend/package.json](frontend/package.json) | NPM scripts and dependencies |
| [.github/workflows/gtc-ci.yml](.github/workflows/gtc-ci.yml) | CI workflow |

---

## 6. Quick Fix Commands

```bash
# Fix frontend drift
cd frontend && npm run lint

# Verify backend is clean
cd backend && uv run ruff check app && uv run ruff format app --check

# Install pre-commit hooks (backend)
cd backend && uv run pre-commit install
```
