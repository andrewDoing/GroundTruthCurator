---
title: Code Conventions
description: The code conventions standardize Pydantic model usage, exception handling, and logging patterns.
jtbd: JTBD-003
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Code Conventions

## Overview

The code conventions standardize Pydantic model usage, exception handling, and logging patterns.

**Parent JTBD:** Help developers maintain GTC code quality

**Stories:** SA-249, SA-250, SA-245

## Problem Statement

The GTC backend has inconsistencies in three areas:

1. **Exception handling (SA-250)**: Generic `Exception` catches obscure Cosmos-specific errors, making debugging harder
2. **Logging patterns (SA-245)**: Two `print()` statements remain in app code; logging extra field keys are inconsistent
3. **Pydantic models (SA-249)**: Research found this is already correct—API endpoints return models and FastAPI serializes them

## Current State Assessment

### Pydantic Models (SA-249) - ✅ No Changes Required

Research confirms:

- API endpoints return Pydantic models directly
- `model_dump()` used only at persistence boundary (appropriate)
- Bucket UUID→string conversion happens in repository (appropriate for Cosmos partition keys)

### Exception Handling (SA-250) - ⚠️ Needs Attention

| Location | Current | Recommendation |
|----------|---------|----------------|
| Startup/lifecycle (main.py) | Generic `Exception` | Keep generic (never block startup) |
| Optional features (container.py) | Generic `Exception` | Keep generic (import failures) |
| Cosmos operations (cosmos_repo.py) | Mixed | Use `CosmosHttpResponseError` |
| API endpoints | Generic `Exception` | Use specific error types |

### Logging (SA-245) - ⚠️ Needs Attention

| Issue | Count | Impact |
|-------|-------|--------|
| `print()` statements in app | 2 | Debug output not captured |
| Inconsistent extra keys | Multiple | Log aggregation harder |
| No shared context helper | N/A | Duplicate context construction |

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Replace print statements with logger | Must | Zero `print()` calls in `backend/app/` |
| FR-002 | Use specific Cosmos exceptions in repo operations | Must | `CosmosHttpResponseError` caught where appropriate |
| FR-003 | Standardize logging extra field keys | Should | All extra keys use snake_case |
| FR-004 | Create shared logging context helper | Should | `_log_context()` helper in `core/logging.py` |
| FR-005 | Document reserved logging keys | Should | README lists `user_id`, `trace_id`, `span_id` |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Observability | Structured log output | JSON-compatible extra fields |
| NFR-002 | Debuggability | Cosmos errors include status codes | Error logs show HTTP status |
| NFR-003 | Consistency | Logging patterns uniform | All services use same helper |

## User Stories

### US-001: Developer debugs Cosmos errors

**As a** backend developer
**I want to** see specific Cosmos error types in logs
**So that** I can quickly identify 404 vs 409 vs 429 errors

**Acceptance Criteria:**

- [ ] Given a Cosmos 409 Conflict, when the error is caught, then logs show `CosmosHttpResponseError` with status code
- [ ] Given a generic exception path, when reviewing code, then it handles truly unexpected errors only

### US-002: Operations team queries logs

**As an** operations engineer
**I want to** filter logs by item_id consistently
**So that** I can trace all operations for a specific ground truth

**Acceptance Criteria:**

- [ ] Given logs from different services, when filtering by `item_id`, then all relevant logs appear
- [ ] Given a log entry, when reading extra fields, then keys use consistent snake_case naming

## Technical Considerations

### Print Statement Replacements

| File | Line | Current | Replacement |
|------|------|---------|-------------|
| [main.py](../backend/app/main.py#L122) | 122 | `print(APP_VERSION)` | `logger.info("app.version", extra={"version": APP_VERSION})` |
| [cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py#L401) | 401 | `print(item.__repr__())` | `logger.error("repo.invalid_item", extra={"item_repr": item.__repr__()})` |

### Exception Handling Pattern

**Before:**

```python
try:
    result = await self._container.upsert_item(doc)
except Exception as e:
    logger.error(f"Upsert failed: {e}")
    raise
```

**After:**

```python
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

try:
    result = await self._container.upsert_item(doc)
except CosmosResourceNotFoundError:
    logger.warning("repo.item_not_found", extra={"item_id": item_id})
    raise HTTPException(404, "Item not found")
except CosmosHttpResponseError as e:
    logger.error("repo.cosmos_error", extra={"status": e.status_code, "message": str(e)})
    raise
except Exception as e:
    # Truly unexpected errors
    logger.exception("repo.unexpected_error")
    raise
```

### Shared Logging Context Helper

Add to `core/logging.py`:

```python
def log_context(
    *,
    item_id: str | None = None,
    dataset: str | None = None,
    bucket: str | None = None,
    operation: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build consistent extra dict for structured logging.

    Reserved keys (automatically injected): user_id, trace_id, span_id
    """
    context: dict[str, Any] = {}
    if item_id:
        context["item_id"] = item_id
    if dataset:
        context["dataset"] = dataset
    if bucket:
        context["bucket"] = bucket
    if operation:
        context["operation"] = operation
    context.update(kwargs)
    return context

# Usage
logger.info("assignment.created", extra=log_context(item_id=item.id, dataset=item.datasetName))
```

### Standard Extra Field Keys

| Key | Type | Description |
|-----|------|-------------|
| `item_id` | str | Ground truth item ID |
| `dataset` | str | Dataset name |
| `bucket` | str | Bucket UUID as string |
| `operation` | str | Operation name (e.g., "upsert", "delete") |
| `status_code` | int | HTTP or Cosmos status code |
| `count` | int | Number of items affected |
| `duration_ms` | float | Operation duration |

**Reserved keys (injected automatically):**

- `user_id` - Current user from auth context
- `trace_id` - OpenTelemetry trace ID
- `span_id` - OpenTelemetry span ID

### Locations Needing Exception Updates

| File | Lines | Current Pattern | Update To |
|------|-------|-----------------|-----------|
| cosmos_repo.py | 113 | Generic Exception | CosmosHttpResponseError |
| assignments.py | 149, 238 | Generic Exception | CosmosHttpResponseError |
| ground_truths.py | 483 | Generic Exception | CosmosHttpResponseError |
| search.py | 22 | Generic Exception | Specific search errors |

### Constraints

- Keep generic exceptions in startup code (main.py)
- Keep generic exceptions for optional features (container.py)
- Don't change external script print statements
- Preserve existing log format string

## Implementation Phases

### Phase 1: Remove Print Statements (SA-245)

1. Replace `print()` in main.py with logger
2. Replace `print()` in cosmos_repo.py with logger
3. Verify no other prints in app code

### Phase 2: Standardize Logging (SA-245)

1. Create `log_context()` helper in core/logging.py
2. Document standard keys in README
3. Update AssignmentService to use shared helper
4. Update other services incrementally

### Phase 3: Specific Exceptions (SA-250)

1. Add CosmosHttpResponseError imports
2. Update cosmos_repo.py error handling
3. Update API endpoint error handling
4. Add tests for error scenarios

## Open Questions

| Q | Question | Owner | Status |
|---|----------|-------|--------|
| Q1 | Should we adopt structlog for better JSON output? | Backend team | Deferred |
| Q2 | Should exception changes be breaking (different HTTP status)? | Backend team | Open |

## References

- Research: [.copilot-tracking/subagent/20260122/code-conventions-research.md](../.copilot-tracking/subagent/20260122/code-conventions-research.md)
- [backend/app/core/logging.py](../backend/app/core/logging.py)
- [backend/app/adapters/repos/cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py)
- [Azure Cosmos DB Python SDK Exceptions](https://learn.microsoft.com/en-us/python/api/azure-cosmos/azure.cosmos.exceptions)
