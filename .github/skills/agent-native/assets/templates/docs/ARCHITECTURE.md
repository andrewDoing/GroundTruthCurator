# Architecture

<!-- ⚠️  CUSTOMIZE THIS FILE — replace every section below with your project's real details.
     See the example at the bottom for what a filled-in version looks like.
     A grader/auditor will FAIL this file if it still contains placeholder text. -->

## Purpose

_Replace: What does this service/app do? One sentence._

## Boundaries

| Boundary | Input | Output | Owner |
|---|---|---|---|
| _Replace_ | _HTTP request / CLI args / event_ | _DTO / response / side effect_ | _module/package_ |

## Data Shape Contracts

- Parse and validate external data at boundaries.
- Convert to internal typed models before crossing module boundaries.
- Keep boundary transformation logic centralized and testable.

## Module Ownership Rules

- One primary responsibility per module.
- No cross-layer shortcuts without explicit architecture update.
- New modules require ownership and boundary documentation.

## Execution Flow

_Replace each step with your actual request lifecycle:_

1. Entry: _e.g., HTTP request hits router_
2. Boundary parse/validate: _e.g., middleware validates auth + body schema_
3. Core execution: _e.g., service layer applies business logic_
4. Persistence/output: _e.g., write to DB / return response_
5. Event/log emission: _e.g., hlog() writes to .harness/logs.jsonl_

## Enforcing Boundaries With Lint Rules

Architecture docs rot. Lint rules don't. Encode your boundaries as static analysis rules so agents (and humans) get instant feedback when they violate them.

### Import/Dependency Restrictions

Prevent modules from importing across boundaries they shouldn't cross.

**TypeScript (ESLint `no-restricted-imports` / `import/no-restricted-paths`):**
```jsonc
// eslint.config.js — block store from importing route-layer code
{
  "rules": {
    "no-restricted-imports": ["error", {
      "patterns": [{
        "group": ["../routes/*", "../middleware/*"],
        "message": "Store layer must not import from routes or middleware."
      }]
    }]
  }
}
```

**Python (Ruff / `import-linter`):**
```toml
# pyproject.toml — using import-linter
[tool.importlinter]
root_packages = ["app"]

[[tool.importlinter.contracts]]
name = "Domain must not import from API layer"
type = "forbidden"
source_modules = ["app.domain"]
forbidden_modules = ["app.routes", "app.middleware"]
```

**Go (depguard via golangci-lint):**
```yaml
# .golangci.yml
linters:
  enable:
    - depguard
linters-settings:
  depguard:
    rules:
      store-boundary:
        deny:
          - pkg: "harness-test-go/handlers"
            desc: "Store package must not import handlers"
        files:
          - "**/store/**"
```

**C# (Roslyn analyzers / NDepend / ArchUnitNET):**
```csharp
// Using ArchUnitNET in a test:
[Fact]
public void Domain_Should_Not_Reference_Controllers()
{
    Types().That().ResideInNamespace("App.Domain")
        .Should().NotDependOnAny(
            Types().That().ResideInNamespace("App.Controllers"))
        .Check(Architecture);
}
```

### Custom Rules for Your Project

_Replace: Add project-specific lint rules here. Common patterns:_

- **No direct DB access outside the store layer** — restrict ORM/SQL imports to `store/` or `repository/`
- **No HTTP calls in domain logic** — restrict `fetch`/`requests`/`HttpClient` to service layer
- **Config must flow through injection** — ban `process.env` / `os.environ` reads outside config module
- **No cross-feature imports** — in monorepos, features can't import from sibling features directly

### Wiring Into the Harness

Add boundary lint rules to `scripts/harness/lint.sh` so they run in `make check` and `make ci`:

```bash
# In scripts/harness/lint.sh — add after standard linting
echo "Checking architectural boundaries..."
# TypeScript: eslint already covers it if rules are in config
# Python: import-linter
import-linter --config pyproject.toml
# Go: golangci-lint already covers it if depguard is enabled
# C#: dotnet test --filter "Category=Architecture"
```

## Refactor Checklist

- [ ] Boundary contracts unchanged or versioned.
- [ ] Ownership map still accurate.
- [ ] Integration tests cover boundary paths.
- [ ] Documentation updated in same change.

---

## Example (delete this section after customizing)

Below is what a filled-in architecture doc looks like for a task tracker API:

```markdown
## Purpose
REST API for managing tasks (CRUD) with in-memory storage and JSONL observability.

## Boundaries
| Boundary | Input | Output | Owner |
|---|---|---|---|
| HTTP Router | HTTP request | route match + params | routes.py / router.ts |
| Validation | raw JSON body | typed Task model | models.py / types.ts |
| Store | Task model | persisted Task (dict/Map) | store.py / store.ts |
| Observability | request context | JSONL log/trace lines | middleware (hlog) |

## Execution Flow
1. Entry: HTTP request → framework router
2. Boundary: request body parsed into typed model, 422 on invalid
3. Core: store CRUD operation (create/read/update/delete)
4. Response: JSON serialization of result, appropriate status code
5. Observability: middleware logs request completion + duration to .harness/
```
