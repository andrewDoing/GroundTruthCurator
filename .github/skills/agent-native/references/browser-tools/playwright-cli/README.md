# Playwright CLI — Agent Skill Reference

**Source:** [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)
**Install:** `npm install -g @playwright/cli`
**Compatibility:** GitHub Copilot (VS Code, CLI, coding agent), Claude Code, any skills-compatible agent

---

## Overview

CLI for browser automation — navigate, interact, snapshot, screenshot. Designed specifically for coding agents. Uses accessibility snapshots (not screenshots) as the primary way to "see" pages, with element refs for precise interaction.

## Install

```bash
npm install -g @playwright/cli
# or per-project
npx playwright-cli open https://example.com
```

Skills are auto-discovered by compatible agents when installed globally.

## Quick Start

```bash
playwright-cli open http://localhost:3000   # launch browser
playwright-cli snapshot                      # get accessibility tree with element refs
playwright-cli click e15                     # click element by ref
playwright-cli fill e7 "user@example.com"    # type into input
playwright-cli screenshot                    # capture visual
playwright-cli close                         # done
```

## Core Commands

### Navigation
```bash
playwright-cli open https://example.com
playwright-cli goto https://example.com/page
playwright-cli go-back
playwright-cli go-forward
playwright-cli reload
```

### Interaction (use refs from snapshot)
```bash
playwright-cli click e3
playwright-cli dblclick e7
playwright-cli fill e5 "value"
playwright-cli type "search query"       # types into focused element
playwright-cli press Enter
playwright-cli hover e4
playwright-cli select e9 "option-value"
playwright-cli check e12
playwright-cli uncheck e12
playwright-cli drag e2 e8
playwright-cli upload ./file.pdf
```

### Inspection
```bash
playwright-cli snapshot                          # accessibility tree (primary)
playwright-cli snapshot --filename=state.yml     # save to file
playwright-cli screenshot                        # visual capture
playwright-cli screenshot --filename=page.png
playwright-cli eval "document.title"             # run JS
playwright-cli eval "el => el.textContent" e5    # run JS on element
playwright-cli console                           # JS console messages
playwright-cli console warning                   # filter by level
playwright-cli network                           # network requests
```

### Tabs
```bash
playwright-cli tab-list
playwright-cli tab-new https://example.com
playwright-cli tab-select 0
playwright-cli tab-close
```

### DevTools / Tracing
```bash
playwright-cli tracing-start
playwright-cli tracing-stop          # saves trace file
playwright-cli video-start
playwright-cli video-stop video.webm
```

### Network Mocking
```bash
playwright-cli route "**/*.jpg" --status=404
playwright-cli route "https://api.example.com/**" --body='{"mock": true}'
playwright-cli route-list
playwright-cli unroute "**/*.jpg"
```

### State Management
```bash
playwright-cli state-save auth.json      # save cookies + localStorage
playwright-cli state-load auth.json      # restore state
playwright-cli cookie-list
playwright-cli cookie-set session abc123
playwright-cli localstorage-get theme
playwright-cli localstorage-set theme dark
```

### Sessions
```bash
playwright-cli -s=mysession open --persistent   # named session with persistent profile
playwright-cli -s=mysession click e6
playwright-cli -s=mysession close
playwright-cli list                              # list all sessions
playwright-cli close-all
```

## Key Pattern: Snapshot-First

**Always use `snapshot` before interacting.** The snapshot provides element `refs` (e.g., `e15`) that interaction commands need.

```bash
playwright-cli open http://localhost:3000
playwright-cli snapshot           # → find e7 is the email input
playwright-cli fill e7 "test@example.com"
playwright-cli click e12          # submit button
playwright-cli snapshot           # verify result
```

**Take a new snapshot after navigation or major DOM changes** — refs may change.

## Harness Engineering Patterns

### Pattern: Verify After Fix
```bash
# Agent makes a code change, then:
playwright-cli snapshot --filename=.harness/after-fix.yml
playwright-cli console              # check for new JS errors
playwright-cli screenshot --filename=.harness/after-fix.png
```

### Pattern: Form Submission Test
```bash
playwright-cli open http://localhost:3000/form
playwright-cli snapshot
playwright-cli fill e1 "user@example.com"
playwright-cli fill e2 "password123"
playwright-cli click e3
playwright-cli snapshot   # verify success state
playwright-cli close
```

### Pattern: Debugging
```bash
playwright-cli open http://localhost:3000
playwright-cli console              # check JS errors
playwright-cli network              # check failed requests
playwright-cli eval "document.querySelectorAll('.error').length"
```
