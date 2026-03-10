# Static Analysis & Linting

## Purpose

Fast feedback before expensive test runs. Linting catches typos, unused imports, type errors, and style violations in seconds — before the agent spends minutes running tests against broken code.

For harness engineering, linting is the **first gate**: `make check` (lint + typecheck) runs before `make test`. If lint fails, don't bother testing.

## Principles

1. **Fast** — lint should finish in under 10 seconds for most projects
2. **Deterministic** — same code, same result, every time. Pin versions.
3. **Fixable** — prefer linters with `--fix` / autofix so agents can self-repair
4. **Parseable** — use JSON/SARIF output when available so agents can read results programmatically
5. **Opinionated defaults** — start strict, relax only with justification

## Recommended Tools by Language

### JavaScript / TypeScript
- **ESLint** — the standard. Use flat config (`eslint.config.js`).
  - Recommended: `@eslint/js` recommended + `typescript-eslint` strict
  - `eslint --format json` for agent-parseable output
  - `eslint --fix` for auto-repair
- **Biome** — faster alternative (Rust-based). Lint + format in one tool.
  - `biome check --reporter json` for parseable output
  - Good for new projects; ESLint has broader plugin ecosystem

### Python
- **Ruff** — extremely fast (Rust-based), replaces flake8 + isort + pyupgrade + dozens more
  - `ruff check --output-format json` for agent-parseable output
  - `ruff check --fix` for auto-repair
  - Config in `pyproject.toml` under `[tool.ruff]`
- **mypy** or **pyright** for type checking (separate from lint, runs via `make typecheck`)

### Go
- **golangci-lint** — meta-linter wrapping 50+ Go linters
  - `golangci-lint run --out-format json` for parseable output
  - Config in `.golangci.yml`

### Rust
- **clippy** — built-in, no setup needed
  - `cargo clippy --all-targets -- -D warnings`
  - JSON output: `cargo clippy --message-format json`

### C# / .NET
- **dotnet format** — built-in formatter + analyzer
  - `dotnet format --verify-no-changes` for CI
  - Roslyn analyzers for deeper checks (configure in `.editorconfig`)

### Multi-Language / Monorepo
- **MegaLinter** — runs 50+ linters across languages in Docker
  - Best for: monorepos with many services in different languages
  - `mega-linter-runner` for local use, GitHub Action for CI
  - Config in `.mega-linter.yml` — enable only what you need
  - Heavy (~minutes), so use per-language linters for tight agent loops and MegaLinter for CI gate
- **Trunk Check** (`trunk.io`) — single CLI, auto-detects language, runs appropriate linters
  - Lighter than MegaLinter, good local experience
  - Proprietary dependency (free tier available)

## The lint.sh Script

The harness template ships `scripts/harness/lint.sh` with auto-detection:

1. If `HARNESS_LINT_CMD` env var is set → run that (explicit override)
2. Detect language from project files (package.json, pyproject.toml, Cargo.toml, go.mod)
3. Run the appropriate linter with sane defaults
4. Exit 0 on clean, non-zero on violations

**Customize it.** The auto-detection is a starting point. For most projects, replace the body of `lint.sh` with your specific linter invocation.

## Agent-Friendly Output

When configuring linters, prefer JSON output for agent consumption:

```bash
# Instead of:
eslint src/

# Use:
eslint src/ --format json > .harness/lint-results.json

# Agent can then:
jq '.[] | .messages[] | select(.severity == 2)' .harness/lint-results.json
```

The verify loop can check lint results alongside runtime telemetry:

```bash
make lint                              # fast static check
make test                              # integration tests  
jq 'select(.level == "ERROR")' .harness/logs.jsonl  # runtime errors
```

## Typecheck vs Lint

These are separate concerns:
- **Lint** = style, patterns, common mistakes → `make lint`
- **Typecheck** = type correctness → `make typecheck`

Both run under `make check` (before tests). Keep them separate so agents know which kind of error they're dealing with.

## Pinning Versions

Lock linter versions in your package manager (package.json, pyproject.toml, go.mod). Never rely on globally installed linters in CI — the version will drift. Agent harness runs must be reproducible.
