# Init AGENTS.md

> **Purpose:** Generate a high-quality AGENTS.md for this repository.
> **Usage:** Feed this prompt to any AI coding agent while in the repo root.
> **Why this matters:** Vercel's evals showed a small, always-present AGENTS.md "docs index" hit 100% on Next.js API tasks — beating both no-docs (53%) and on-demand skills (53-79%). Passive context beats active retrieval because agents don't have to decide to look things up.

---

## Prompt

You are initializing an AGENTS.md file for this repository. AGENTS.md is **persistent context** — it's loaded every time an agent works in this repo. Think of it as a **routing table for agent attention**: what to run, where truth lives, how to find things fast, and what not to do.

### Step 1: Check for existing AGENTS.md

```bash
cat AGENTS.md 2>/dev/null
```

If an AGENTS.md already exists, you are **updating**, not creating from scratch:
- Preserve any manually-added sections, rules, or gotchas
- Update commands, project map, and docs index to reflect the current repo state
- Remove references to files/directories that no longer exist
- Add new docs, directories, or commands that have appeared since the last update
- Keep the file under 8KB

If no AGENTS.md exists, you are creating one fresh.

### Step 2: Explore the repo

Before writing anything, explore the project:

```bash
# What's here?
find . -maxdepth 3 -type f | head -80
cat README.md 2>/dev/null
cat package.json 2>/dev/null || cat pyproject.toml 2>/dev/null || cat go.mod 2>/dev/null || cat *.csproj 2>/dev/null || cat Cargo.toml 2>/dev/null

# How do you build/test/lint?
cat Makefile 2>/dev/null || cat Makefile.harness 2>/dev/null
cat .github/workflows/*.yml 2>/dev/null | head -100

# Existing agent config?
cat AGENTS.md 2>/dev/null
cat .github/copilot-instructions.md 2>/dev/null
cat .cursorrules 2>/dev/null
cat .claude/settings.json 2>/dev/null

# Docs?
ls docs/ 2>/dev/null
ls .next-docs/ 2>/dev/null
ls ADR/ 2>/dev/null || ls docs/adr/ 2>/dev/null
```

### Step 3: Write or update AGENTS.md

Write (or update) AGENTS.md in the repo root with these sections. **Keep it under 8KB.** Every line must earn its place — agents read this on every turn.

#### Required Sections

**1. Setup & Commands** (copy-pasteable, no prose)

```markdown
## Commands

| Goal | Command |
|---|---|
| Install deps | `<command>` |
| Dev server | `<command>` |
| Lint | `<command>` |
| Type check | `<command>` |
| Test (all) | `<command>` |
| Test (single) | `<command> <path>` |
| Build | `<command>` |
| CI-equivalent | `<command>` |
```

**2. Project Map** (what matters, where — max 15 lines)

```markdown
## Project Map

- `src/` — application source
  - `src/api/` — route handlers
  - `src/lib/` — shared utilities
  - `src/db/` — database layer (DO NOT import from api/)
- `tests/` — test suite (mirrors src/ structure)
- `docs/` — architecture decisions and API docs
- `scripts/` — build and deployment scripts
```

Only list directories an agent would actually need to navigate. Skip obvious ones (node_modules, dist, .git).

**3. Decision Rules** (when unsure, what to do)

```markdown
## Rules

- Prefer retrieval-led reasoning over pre-training knowledge. When unsure about an API or pattern, check the docs index below before guessing.
- Run `<lint command>` before committing. Treat lint failures as blocking.
- Run `<test command>` after any logic change.
- Do not modify files in `<protected paths>` without asking.
- Keep modules within their boundaries (see Architecture below).
```

**4. Docs Index** (pointers, not walls of text)

This is the key insight from Vercel's research: a compressed index mapping topics → files beats pasting docs inline. If the repo has local docs, ADRs, or a docs folder, build an index:

```markdown
## Docs Index

When you need information on a topic, open the referenced file:

| Topic | File |
|---|---|
| API route conventions | `docs/api-routes.md` |
| Database migrations | `docs/migrations.md` |
| Auth flow | `docs/auth.md` |
| Error handling | `docs/OBSERVABILITY.md` |
| Module boundaries | `docs/ARCHITECTURE.md` |
| Deployment | `docs/deploy.md` |
| ADR: chose Postgres over Mongo | `docs/adr/001-database.md` |
```

If the repo has framework docs locally (e.g., `.next-docs/`, `vendor/docs/`), index those too. Point to specific files, not directories.

**5. Quality Bar** (what "done" means)

```markdown
## Quality Bar

- All tests pass
- No lint errors
- No type errors
- New endpoints include tests
- Structured logging follows `docs/OBSERVABILITY.md` convention
- PR description explains the "why"
```

#### Optional Sections (include if relevant)

- **Architecture Boundaries** — if the project has layer rules (e.g., "store must not import from handlers"), state them explicitly
- **Conventions** — naming patterns, file organization rules, import ordering
- **Known Gotchas** — things that break in non-obvious ways

### Step 4: Verify

After writing AGENTS.md:

1. Confirm it's under 8KB: `wc -c AGENTS.md`
2. Every command listed actually works (run them)
3. Every file referenced in the docs index actually exists
4. No placeholder text remains

### Design Principles (why these rules)

- **Passive > Active**: Agents read AGENTS.md every turn. They have to *decide* to invoke skills/tools. Decision failure killed 56% of skill invocations in Vercel's evals.
- **Pointers > Content**: An 8KB index that says "open this file for auth docs" beats pasting 40KB of auth docs inline. The agent fetches what it needs, when it needs it.
- **Commands > Descriptions**: `npm run test -- --watch` is better than "you can run the tests in watch mode using the npm test script with the watch flag."
- **Guardrails > Guidance**: "DO NOT import from api/ in the db layer" is better than "try to keep layers separate."
