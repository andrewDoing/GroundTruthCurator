---
title: DoS Prevention
description: The DoS prevention system enforces batch size limits and rate limiting on bulk import endpoints to protect against resource exhaustion attacks.
jtbd: JTBD-004
author: spec-builder
ms.date: 2026-01-22
status: draft
stories: [SA-409]
---

# DoS Prevention

## Overview

The DoS prevention system protects the Ground Truth Curator API from denial-of-service attacks by enforcing configurable batch size limits and rate limiting on bulk import endpoints.

**Parent JTBD:** Help administrators ensure data integrity and security

## Problem Statement

The bulk import endpoint (`POST /v1/ground_truths`) accepts an unbounded list of `GroundTruthItem` objects with no size validation. This creates a critical DoS vulnerability where attackers can exhaust server memory and CPU by submitting arbitrarily large payloads. The endpoint iterates over the entire list twice (ID assignment + validation) before any persistence, amplifying resource consumption. No rate limiting middleware exists in the codebase, allowing unlimited request volume from any client.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Configurable batch size limit | Must | System rejects bulk import requests exceeding `BULK_IMPORT_MAX_ITEMS` (default: 1000) with HTTP 413 Payload Too Large |
| FR-002 | Per-endpoint rate limiting | Must | Bulk import endpoint enforces configurable requests-per-window limit; returns HTTP 429 Too Many Requests when exceeded |
| FR-003 | Empty batch rejection | Must | System rejects bulk import requests with zero items; returns HTTP 400 Bad Request |
| FR-004 | Early validation failure | Must | Size validation occurs before any processing (ID assignment, field validation, persistence) |
| FR-005 | Configurable rate limit window | Should | Rate limit window (seconds) and request count are configurable via environment variables |
| FR-006 | Role-based rate limits | Could | Different rate limits for admin vs. regular users |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Security | OWASP compliance | Addresses A04:2021 Insecure Design |
| NFR-002 | Security | NIST 800-53 alignment | SC-5 Denial of Service Protection |
| NFR-003 | Performance | Validation overhead | < 1ms additional latency for size check |
| NFR-004 | Reliability | Graceful degradation | Rate-limited requests receive clear retry guidance |
| NFR-005 | Configurability | Environment-based config | All limits configurable via `GTC_` prefixed environment variables |

## User Stories

### SA-409: DoS Prevention for Bulk Import

**As a** system administrator,  
**I want** the bulk import endpoint to enforce size and rate limits,  
**So that** malicious or misconfigured clients cannot exhaust server resources.

**Acceptance Criteria:**

1. Requests with more than `BULK_IMPORT_MAX_ITEMS` items return HTTP 413
2. Requests exceeding rate limits return HTTP 429 with `Retry-After` header
3. Empty batch requests return HTTP 400
4. Error responses include actionable messages with current limits
5. All limits are configurable without code changes

**Security Testing Requirements:**

- Verify 413 response for payload at limit + 1 items
- Verify 429 response after exceeding rate limit
- Verify rate limit resets after window expires
- Load test with concurrent requests to confirm protection
- Verify no memory growth under sustained large-payload attacks

## Technical Considerations

### Configuration

Add settings to `backend/app/core/config.py` following existing patterns:

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

Environment variables: `GTC_BULK_IMPORT_MAX_ITEMS`, `GTC_RATE_LIMIT_REQUESTS`, `GTC_RATE_LIMIT_WINDOW_SECONDS`

### Rate Limiting Implementation

Use `slowapi` library for FastAPI-native rate limiting:

- Supports memory and Redis backends
- Decorator-based application to specific endpoints
- Returns standard 429 responses with `Retry-After` header

### Error Responses

| Condition | Status Code | Response Body |
|-----------|-------------|---------------|
| Batch size exceeded | 413 Payload Too Large | `{"detail": "Batch size 1500 exceeds maximum of 1000"}` |
| Rate limit exceeded | 429 Too Many Requests | `{"detail": "Rate limit exceeded. Retry after 45 seconds"}` |
| Empty batch | 400 Bad Request | `{"detail": "Batch must contain at least one item"}` |

### Implementation Phases

1. **Phase 1 (Immediate):** Add batch size validation with configurable limit
2. **Phase 2:** Add `slowapi` dependency and rate limiting middleware
3. **Phase 3:** Configure server-level protection (Uvicorn `--limit-max-body-size`)

### Files to Modify

| File | Change |
|------|--------|
| `backend/app/core/config.py` | Add DoS prevention settings |
| `backend/app/api/v1/ground_truths.py` | Add batch size validation |
| `backend/pyproject.toml` | Add slowapi dependency (Phase 2) |
| `backend/app/main.py` | Install rate limiting middleware (Phase 2) |

## Open Questions

1. Should rate limiting be per-user (authenticated) or per-IP (for unauthenticated scenarios)?
2. What is the appropriate default for `BULK_IMPORT_MAX_ITEMS`—1000 items balances usability with protection?
3. Should Phase 3 server-level limits be documented separately as infrastructure configuration?
4. Do we need different limits for different bulk endpoints (if more are added)?

## References

- SA-409: DoS Prevention Story
- NIST 800-53: SC-5 Denial of Service Protection
- OWASP A04:2021: Insecure Design
- [slowapi documentation](https://github.com/laurents/slowapi)
- Research file: `.copilot-tracking/subagent/20260122/dos-prevention-research.md`
