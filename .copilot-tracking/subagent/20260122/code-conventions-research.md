# Code Conventions Research

**Research Date:** 2025-01-22  
**Related Jira Stories:** SA-249, SA-250, SA-245

---

## Executive Summary

This research identifies patterns requiring standardization across three areas:
1. **Pydantic models vs JSON dump** - Limited issues; most API endpoints correctly return Pydantic models
2. **Exception handling** - Significant use of generic `Exception` catches that could use specific Cosmos error types
3. **Logging patterns** - Two `print()` statements in app code; mature logging infrastructure using `extra={}` pattern

---

## 1. JSON Dumps vs Pydantic Models (SA-249)

### Findings

The codebase generally handles Pydantic models correctly. FastAPI endpoints return Pydantic models directly, letting FastAPI handle JSON serialization.

#### Locations Using `json.dumps()` or `model_dump()`

| File | Line | Context | Assessment |
|------|------|---------|------------|
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L409) | 409 | `model_dump(mode="json", by_alias=True)` | **Appropriate** - Preparing data for Cosmos DB storage |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1068) | 1068 | `model_dump(mode="json", by_alias=True)` | **Appropriate** - Document upsert |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1917) | 1917 | `model_dump(mode="json", by_alias=True)` | **Appropriate** - Assignment document upsert |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L380) | 380 | `json.loads(json.dumps(sanitized, ensure_ascii=True))` | **Appropriate** - Unicode sanitization workaround |
| [snapshot_service.py](backend/app/services/snapshot_service.py#L81) | 81 | `model_dump(mode="json", ...)` for export items | **Appropriate** - Export formatting |
| [inference.py](backend/app/adapters/inference/inference.py#L772) | 772 | `json.dumps({"error": str(e)})` | **Review** - Error response in retrieval tool |

#### Bucket UUID to String Coercion

| File | Line | Context |
|------|------|---------|
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L411) | 411 | `d["bucket"] = str(d["bucket"])` - Converting for Cosmos storage |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1058) | 1058 | `str(bucket)` - Partition key construction |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1272) | 1272 | `str(it.bucket)` - Partition key for delete |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1762) | 1762 | `str(bucket)` - Partition key construction |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1837) | 1837 | `str(bucket)` - Partition key construction |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1907) | 1907 | `str(gt.bucket)` - Document ID construction |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1975) | 1975 | `str(bucket)` - Item ID construction |

**Assessment:** Bucket-to-string conversion happens at the repository layer for Cosmos DB compatibility. This is appropriate since Cosmos DB partition keys must be strings. The Pydantic models properly type `bucket` as `UUID`, and conversion only happens at persistence boundaries.

### Recommendation

- **No changes required** for JSON serialization patterns in API layer
- Repository-level `model_dump()` and `str(bucket)` conversions are appropriate for persistence
- Consider documenting the pattern: "Models remain typed; string conversion only at persistence boundary"

---

## 2. Generic Exception Catches (SA-250)

### Locations in App Code

The codebase has extensive use of generic `Exception` catches. Most are intentional defensive patterns with pragmatic comments, but some could benefit from more specific error types.

#### High-Priority (Cosmos-related operations)

| File | Line | Context | Recommendation |
|------|------|---------|----------------|
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L113) | 113 | Generic exception in repo | Use `CosmosHttpResponseError` |
| [container.py](backend/app/container.py#L83) | 83 | Credential building | Keep generic (import failures) |
| [container.py](backend/app/container.py#L127) | 127 | Search init | Keep generic (optional feature) |
| [container.py](backend/app/container.py#L260) | 260 | Inference init | Keep generic (optional feature) |

#### API Layer Exception Catches

| File | Line | Context | Recommendation |
|------|------|---------|----------------|
| [search.py](backend/app/api/v1/search.py#L22) | 22 | Search endpoint | Add specific error handling |
| [ground_truths.py](backend/app/api/v1/ground_truths.py#L308) | 308 | Status parsing | Keep generic (data validation) |
| [ground_truths.py](backend/app/api/v1/ground_truths.py#L483) | 483 | Tag recompute | Add specific error types |
| [assignments.py](backend/app/api/v1/assignments.py#L149) | 149 | Assignment update | Use `CosmosHttpResponseError` |
| [assignments.py](backend/app/api/v1/assignments.py#L238) | 238 | Assignment update | Use `CosmosHttpResponseError` |
| [chat.py](backend/app/api/v1/chat.py#L133) | 133 | Chat endpoint | Commented as safeguard |
| [chat.py](backend/app/api/v1/chat.py#L151) | 151 | Chat endpoint | Keep generic (multi-service) |
| [tags.py](backend/app/api/v1/tags.py#L83) | 83 | Tags endpoint | Add specific error types |

#### Startup/Lifecycle (main.py)

The [main.py](backend/app/main.py) file has numerous generic `Exception` catches (lines 77, 80, 114, 130, 155, 162, 170, 175, 197, 229). These are intentional "never block startup" patterns and should remain generic.

#### Codebase Already Using CosmosHttpResponseError

The codebase demonstrates proper usage in several places:

```python
# cosmos_repo.py
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
```

Used correctly in:
- [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L488) - Line 488
- [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1060) - Line 1060
- [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1091) - Line 1091

### Recommendation

1. **Keep generic** exceptions in:
   - Startup/lifecycle code (main.py)
   - Optional feature initialization (container.py)
   - Third-party library error handling

2. **Replace with specific** exceptions in:
   - Repository operations interacting with Cosmos
   - API endpoints that call Cosmos operations
   - Use `CosmosHttpResponseError` and `CosmosResourceNotFoundError`

---

## 3. Print Statements (SA-245)

### Locations in App Code

Only **2 print statements** exist in the main app code:

| File | Line | Code | Recommendation |
|------|------|------|----------------|
| [main.py](backend/app/main.py#L122) | 122 | `print(APP_VERSION)` | Replace with `logger.info("app.version", extra={"version": APP_VERSION})` |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L401) | 401 | `print(item.__repr__())` | Replace with `logger.error("repo.invalid_item", extra={"item": item.__repr__()})` |

### Scripts with Print Statements (Lower Priority)

Scripts in `backend/scripts/` use `print()` extensively for CLI output:
- `cosmos_container_manager.py` - CLI progress output
- `cosmos_export_import.py` - Migration logging
- `delete_cosmos_emulator_dbs.py` - Cleanup status
- `init_seed_data.py` - Seed data feedback

**Assessment:** Script print statements are appropriate for CLI tools and don't need conversion.

---

## 4. Logging Patterns Analysis

### Current Architecture

The codebase has a mature logging infrastructure in [app/core/logging.py](backend/app/core/logging.py):

#### Key Components

1. **Setup Function** (`setup_logging`):
   - Configures root logger with structured format
   - Suppresses noisy Azure SDK logs
   - Format: `%(asctime)s %(levelname)s %(name)s user=%(user_id)s %(message)s`

2. **Trace Context Filter** (`_TraceContextFilter`):
   - Injects `trace_id`, `span_id`, `user_id` into every log record
   - Integrates with OpenTelemetry when available

3. **User Identity Context**:
   - `ContextVar` for current user ID
   - `set_current_user()` / `clear_current_user()` functions
   - Middleware automatically populates from Easy Auth or headers

4. **Log Record Factory** (`_install_log_record_factory`):
   - Custom factory ensures `user_id` attribute always exists
   - Prevents `KeyError` when using `extra={"user_id": ...}`

### The "Extra Field" Pattern (SA-245)

The `extra={}` parameter is used throughout for structured logging:

```python
# Example from assignment_service.py
logger.info(
    "self_assign.assigned",
    extra=self._log_context(it.id, it.datasetName),
)

# Helper method creates consistent context
def _log_context(self, item_id: str | None = None, dataset: str | None = None) -> dict[str, str]:
    context: dict[str, str] = {}
    if item_id:
        context["item_id"] = item_id
    if dataset:
        context["dataset"] = dataset
    return context
```

#### Locations Using `extra={}` Pattern

| File | Count | Notes |
|------|-------|-------|
| [assignment_service.py](backend/app/services/assignment_service.py) | 14 | Consistent `_log_context()` helper |
| [cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py) | 8+ | Various repo operations |
| [search_service.py](backend/app/services/search_service.py) | 1 | Search results |
| [tagging_service.py](backend/app/services/tagging_service.py) | 1 | Tag collision warning |
| [validation_service.py](backend/app/services/validation_service.py) | 2 | Validation logging |

### Current Issues with Extra Pattern

1. **Reserved field collision**: The `user_id` field is reserved by the log record factory. Using `extra={"user_id": ...}` would cause issues (documented in [assignment_service.py](backend/app/services/assignment_service.py#L27-L34)).

2. **Inconsistent key naming**: Some use `item_id`, others use `itemId`; some use `count`, others use `candidate_count`.

3. **Missing context helpers**: Only `AssignmentService` has a `_log_context()` helper; other services construct extra dicts inline.

### Recommendations

1. **Standardize key names** across all services (snake_case recommended)
2. **Create shared logging context helper** in `app/core/logging.py`
3. **Document reserved keys** (`user_id`, `trace_id`, `span_id`)
4. **Consider structured logging library** (e.g., `structlog`) for better JSON output in production

---

## 5. Summary of Required Changes

### Immediate (Low Effort)

| Priority | File | Change |
|----------|------|--------|
| High | [main.py#L122](backend/app/main.py#L122) | Replace `print(APP_VERSION)` with logger |
| High | [cosmos_repo.py#L401](backend/app/adapters/repos/cosmos_repo.py#L401) | Replace `print(item.__repr__())` with logger |

### Medium-Term (Moderate Effort)

| Priority | Scope | Change |
|----------|-------|--------|
| Medium | API endpoints | Replace generic `Exception` with `CosmosHttpResponseError` where appropriate |
| Medium | Logging | Standardize extra field key naming convention |
| Low | Logging | Create shared `_log_context()` helper |

### No Changes Required

- Pydantic model return patterns (already correct)
- Bucket UUID-to-string conversion (appropriate at persistence layer)
- Generic exceptions in startup/lifecycle code
- Print statements in CLI scripts

---

## Appendix: Files Referenced

- [backend/app/main.py](backend/app/main.py)
- [backend/app/core/logging.py](backend/app/core/logging.py)
- [backend/app/container.py](backend/app/container.py)
- [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py)
- [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py)
- [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py)
- [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py)
- [backend/app/api/v1/search.py](backend/app/api/v1/search.py)
- [backend/app/api/v1/chat.py](backend/app/api/v1/chat.py)
- [backend/app/api/v1/tags.py](backend/app/api/v1/tags.py)
