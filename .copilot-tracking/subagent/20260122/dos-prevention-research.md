# DoS Prevention Research: Bulk Import Endpoint

**Date:** 2026-01-22  
**Story:** SA-409  
**Topic:** DoS vulnerability in bulk import endpoint

## Executive Summary

The bulk import endpoint (`POST /v1/ground_truths`) accepts an unbounded list of `GroundTruthItem` objects with **no size validation**. This creates a critical DoS vulnerability where attackers can exhaust server memory/CPU by submitting arbitrarily large payloads. No rate limiting middleware exists in the codebase.

## Research Findings

### 1. Current Bulk Import Endpoint

**Location:** [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L55-L119)

```python
@router.post("", response_model=ImportBulkResponse)
async def import_bulk(
    items: list[GroundTruthItem],  # ← NO SIZE LIMIT
    user: UserContext = Depends(get_current_user),
    buckets: int | None = Query(default=None, ge=1, le=50),
    approve: bool = Query(
        default=False,
        description="If true, mark all imported items as approved and set review metadata.",
    ),
) -> ImportBulkResponse:
```

**Confirmed gaps:**

- No `max_length` constraint on the `items` list parameter
- No validation of list size before processing
- No request body size limit configured
- Iterates over entire list twice (ID assignment + validation) before any persistence

### 2. Rate Limiting Libraries for FastAPI

| Library | Description | Pros | Cons |
|---------|-------------|------|------|
| **slowapi** | FastAPI-friendly, based on limits | Drop-in, Redis support, decorator-based | Adds dependency |
| **fastapi-limiter** | Redis-based rate limiting | Async-native | Requires Redis |
| **starlette-throttle** | Starlette middleware | Simple | Less maintained |
| **Custom middleware** | Roll your own | Full control, no deps | More code to maintain |

**Recommendation:** `slowapi` - mature, FastAPI-native, supports memory and Redis backends.

### 3. Configuration Patterns in GTC

**Settings location:** [backend/app/core/config.py](backend/app/core/config.py)

The codebase uses `pydantic-settings` with:

- Environment variable prefix: `GTC_`
- Type-safe settings via `Settings` class
- Field validation with `Field()` and `model_validator`

**Existing pagination settings pattern to follow:**

```python
# Pagination settings
PAGINATION_MAX_LIMIT: int = Field(
    default=100, description="Maximum items per page for list queries"
)
PAGINATION_MIN_LIMIT: int = Field(default=1, description="Minimum items per page")
PAGINATION_TAG_FETCH_MAX: int = Field(
    default=500,
    description="Maximum items to fetch for tag filtering queries (memory safeguard)",
)
```

**Recommended new settings:**

```python
# DoS prevention settings
BULK_IMPORT_MAX_ITEMS: int = Field(
    default=1000, description="Maximum items per bulk import request"
)
RATE_LIMIT_REQUESTS: int = Field(
    default=100, description="Rate limit: requests per window"
)
RATE_LIMIT_WINDOW_SECONDS: int = Field(
    default=60, description="Rate limit window in seconds"
)
```

### 4. Existing Security Middleware

**Location:** [backend/app/main.py](backend/app/main.py)

Current middleware stack:

1. **Easy Auth middleware** (`install_ezauth_middleware`) - Authentication via Azure Container Apps
2. **User logging middleware** (`user_logging_middleware`) - Request logging with user context

**No existing:**

- Rate limiting middleware
- Request body size validation
- DoS protection middleware

**CORS note:** CORS is handled at platform level (Azure Container Apps), not in code.

### 5. Request Body Size

FastAPI/Starlette default has no body size limit. Uvicorn default is unlimited. This should be addressed at multiple levels:

- Application level: Validate list length in endpoint
- Server level: Configure `--limit-max-body-size` in Uvicorn (bytes)
- Platform level: Azure Container Apps ingress limits

## Gap Analysis

| Control | Current State | Required |
|---------|--------------|----------|
| Batch size limit | ❌ None | ✅ Configurable max items |
| Rate limiting | ❌ None | ✅ Per-user/IP throttling |
| Request body size | ❌ Unlimited | ✅ Configurable max bytes |
| Validation before processing | ⚠️ Partial | ✅ Early rejection |

## Recommended Implementation

### Phase 1: Immediate (Batch Size Limit)

1. Add `BULK_IMPORT_MAX_ITEMS` to `Settings` class
2. Add validation at start of `import_bulk`:

```python
if len(items) > settings.BULK_IMPORT_MAX_ITEMS:
    raise HTTPException(
        status_code=400,
        detail=f"Batch size {len(items)} exceeds maximum of {settings.BULK_IMPORT_MAX_ITEMS}"
    )
```

### Phase 2: Rate Limiting

1. Add `slowapi` dependency to `pyproject.toml`
2. Configure rate limiter in `main.py`
3. Apply rate limit decorator to bulk endpoints

### Phase 3: Server-Level Protection

1. Configure Uvicorn `--limit-max-body-size`
2. Review Azure Container Apps ingress settings

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/core/config.py` | Add DoS prevention settings |
| `backend/app/api/v1/ground_truths.py` | Add batch size validation |
| `backend/pyproject.toml` | Add slowapi dependency (Phase 2) |
| `backend/app/main.py` | Install rate limiting middleware (Phase 2) |

## References

- [slowapi documentation](https://github.com/laurents/slowapi)
- [FastAPI request body size](https://fastapi.tiangolo.com/advanced/request-body/)
- [OWASP DoS Prevention](https://owasp.org/www-community/attacks/Denial_of_Service)
