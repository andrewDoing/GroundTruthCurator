---
title: Dead-Code Audit Workflow
description: Detection-only script for rerunning the GroundTruthCurator backend and frontend dead-code checks.
ms.date: 2025-12-25
---

## Dead-Code Audit Workflow

The `dead-code-audit.sh` script reruns the backend and frontend detection steps for an audit. It emits the command output directly to the terminal so contributors can see ruff, vulture, biome, and knip findings side by side without modifying files.

### Prerequisites

* Run the script from the GroundTruthCurator repository root.
* Backend virtual environment dependencies are managed via `uv` (already configured in
  `backend/pyproject.toml`).
* Frontend dependencies must be installed in `frontend` (`npm install`).

### Usage

```bash
./scripts/dead-code-audit.sh
```

The script prints bannered sections for each tool and shows the exact command invoked. All
commands run in detection-only mode, so no files are changed. Fail-fast behavior is enabled
(`set -euo pipefail`), causing the script to stop at the first failing tool so the root
cause is visible immediately.

### Follow-up Commands

After reviewing the detection output, apply fixes manually using the same commands from
the audit plan:

* Backend safe fixes: `(cd backend && uv run ruff check app/ --select F401,F811,RUF059 --fix)`
* Backend variable cleanup (unsafe): `(cd backend && uv run ruff check app/ --select F401,F841,F811,RUF059 --fix --unsafe-fixes)`
* Backend whitelist refresh: `(cd backend && uv run vulture app/ --make-whitelist > vulture_whitelist.py)`
* Frontend unused import fixes: `(cd frontend && npx biome check src/ --fix --unsafe)`
* Frontend unused export cleanup: `(cd frontend && npx knip --fix --allow-remove-files)`

Ruff code quick reference:

* F401 – imported but unused (safe to drop the import).
* F811 – redefined name from outer scope (usually duplicate function or fixture).
* F841 – local variable assigned but never used (often requires manual intent check).
* RUF059 – unused variables unpacked from tuples (covers ``_, value`` style mistakes).

### Configuration

- Backend ruff selections and Vulture settings live in `backend/pyproject.toml`.
- Decorator-driven FastAPI handlers allowed by Vulture are whitelisted in `backend/vulture_whitelist.py`.
- Frontend Biome formatting and unused-import rules reside in `frontend/biome.json`.
- Knip entry points, ignores, and warning levels are defined in `frontend/knip.json`.
