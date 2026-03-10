# Update Agent-Native Docs

> **Purpose:** Sync agent-native documentation with the current state of the codebase.
> **Usage:** Run `/update-agent-native-docs` in Copilot Chat periodically, after major refactors, or when docs feel stale.

---

## Prompt

You are auditing and updating the agent-native documentation in this repository. These docs drift as code evolves — new modules get added, boundaries shift, commands change, and files get renamed. Your job is to make the docs match reality.

### Step 1: Read current docs

```bash
cat AGENTS.md 2>/dev/null
cat docs/ARCHITECTURE.md 2>/dev/null
cat docs/OBSERVABILITY.md 2>/dev/null
cat PLANS.md 2>/dev/null
```

### Step 2: Scan the actual codebase

```bash
# Current structure
find . -maxdepth 3 -type f -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' -not -path '*/obj/*' -not -path '*/bin/*' | sort

# Current commands
cat Makefile 2>/dev/null || cat Makefile.harness 2>/dev/null
cat package.json 2>/dev/null | jq '.scripts' 2>/dev/null
cat pyproject.toml 2>/dev/null | grep -A20 '\[tool\.' 2>/dev/null

# Current imports / module dependencies (spot-check boundaries)
# TypeScript:
grep -r "from ['\"]" src/ --include="*.ts" 2>/dev/null | head -30
# Python:
grep -r "^from \|^import " src/ app/ --include="*.py" 2>/dev/null | head -30
# Go:
grep -r '"' --include="*.go" 2>/dev/null | grep -v test | grep import | head -20
# C#:
grep -r "^using " --include="*.cs" 2>/dev/null | grep -v obj | head -20

# Existing docs referenced in AGENTS.md
grep -oE '`[^`]+\.(md|txt|yml|yaml)`' AGENTS.md 2>/dev/null | sort -u | while read f; do
  f=$(echo "$f" | tr -d '`')
  [ -f "$f" ] && echo "✅ $f" || echo "❌ MISSING: $f"
done
```

### Step 3: Update each doc

For each file, diff what the doc says against what the code actually does. Fix discrepancies.

#### AGENTS.md
- **Commands table:** Do all commands still work? Run each one. Remove broken ones, add new ones.
- **Project map:** Do all listed directories exist? Are there new important directories not listed?
- **Docs index:** Do all referenced files exist? Are there new docs not indexed?
- **Decision rules:** Still accurate? Any new rules needed from recent refactors?
- **Quality bar:** Still matches CI/linting reality?

#### docs/ARCHITECTURE.md
- **Module list:** Does it match the actual directory structure?
- **Execution flow:** Still accurate? Test by tracing a request through the code.
- **Boundaries:** Are the stated rules actually followed? Spot-check with import grep above.
- **Lint rules:** Do the configured lint rules still match the documented boundaries? Run them.
- **Refactoring red flags:** Updated with any new patterns to watch for?

#### docs/OBSERVABILITY.md
- **hlog()/htrace() calls:** Still present in the codebase? Check with: `grep -r "hlog\|htrace\|HLog\|HTrace\|Harness" --include="*.ts" --include="*.py" --include="*.go" --include="*.cs" .`
- **Level policy:** Still followed? Start the app, hit a 404, check `.harness/logs.jsonl`
- **Field conventions:** Do actual log entries match the documented fields?
- **Endpoints listed:** Do example endpoints in the doc still exist?

#### PLANS.md
- **Completed items:** Mark done items as done, remove if no longer relevant.
- **Stale items:** Flag anything that hasn't been touched in the last iteration.

### Step 4: Verify

After updating:

```bash
# All commands in AGENTS.md still work
make -f Makefile.harness ci 2>/dev/null || make ci 2>/dev/null

# All referenced files exist
grep -oE '`[^`]+\.(md|txt|yml|yaml)`' AGENTS.md 2>/dev/null | sort -u | while read f; do
  f=$(echo "$f" | tr -d '`')
  [ -f "$f" ] || echo "❌ MISSING: $f"
done

# Verify customization still passes
scripts/verify_customized.sh . 2>/dev/null

# AGENTS.md still under 8KB
wc -c AGENTS.md
```

### Step 5: Summarize changes

After updating, add a brief summary of what changed and why. This helps the next update cycle understand what drifted.

### When to run this

- After any major refactor (new modules, renamed directories, changed boundaries)
- After adding new dependencies or removing old ones
- After changing CI/build commands
- Periodically (weekly or biweekly) as docs hygiene
- When an agent reports confusion about project structure
