---
title: Dependency Injection
description: The dependency injection refactoring adopts FastAPI's DI patterns for configuration and services.
jtbd: JTBD-003
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Dependency Injection

## Overview

The dependency injection refactoring adopts FastAPI's DI patterns for configuration and services.

**Parent JTBD:** Help developers maintain GTC code quality

**Stories:** SA-238

## Problem Statement

The GTC backend uses a Service Locator pattern via a global `container` singleton. While functional, this creates:

1. **Test complexity**: Fixtures manually mutate the global container and require careful lifecycle management
2. **Hidden dependencies**: Services like `validation_service.py` import `container` directly, making dependencies implicit
3. **Async initialization quirks**: Services use `cast(ServiceType, None)` placeholders until async startup completes

## Current State Assessment

### What Works

- Consistent pattern used across 50+ endpoints
- Extensive test coverage exists
- No reported production bugs related to DI

### What Could Improve

- Test fixtures require 50+ lines to set up container state
- `dependency_overrides` not usable for cleaner test mocking
- Settings accessed via global import rather than injection

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Create `Depends()` functions for settings | Should | `get_settings()` returns Settings instance |
| FR-002 | Create `Depends()` functions for core services | Could | Optional migration path for new endpoints |
| FR-003 | Document recommended DI patterns | Must | README includes guidance on when to use DI |
| FR-004 | Remove direct container imports from services | Should | `validation_service.py` receives dependencies via constructor |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Testability | Support `dependency_overrides` for mocking | New endpoints use injectable dependencies |
| NFR-002 | Migration Risk | Existing tests continue passing | Zero test regressions |
| NFR-003 | Code Churn | Minimize changes to stable code | <10 files modified |

## Recommendation: Partial Adoption

A full migration from Service Locator to FastAPI DI would require:

- Creating `Depends()` functions for 8+ services
- Updating 50+ endpoint signatures
- Rewriting all test fixtures

**Recommendation:** Adopt DI incrementally for:

1. Settings injection (improves testability)
2. New endpoints (establishes pattern)
3. Services with hidden dependencies (reduces coupling)

Defer full migration unless testing pain becomes critical.

## User Stories

### US-001: Developer tests settings-dependent code

**As a** backend developer
**I want to** override settings in tests without modifying globals
**So that** I can test different configuration scenarios safely

**Acceptance Criteria:**

- [ ] Given a test using `dependency_overrides[get_settings]`, when settings are overridden, then the endpoint uses the mock settings
- [ ] Given the production app, when settings are not overridden, then the global Settings instance is used

### US-002: Developer understands service dependencies

**As a** backend developer
**I want to** see service dependencies in function signatures
**So that** I can understand what a service needs without reading implementation

**Acceptance Criteria:**

- [ ] Given `validation_service`, when reviewing the module, then dependencies are constructor parameters not global imports

## Technical Considerations

### Settings Injection Pattern

```python
# core/dependencies.py
from functools import lru_cache
from app.core.config import Settings

@lru_cache
def get_settings() -> Settings:
    return Settings()

# In endpoint
from fastapi import Depends
from typing import Annotated

@router.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)]
) -> dict:
    return {"cosmos_configured": bool(settings.COSMOS_ENDPOINT)}

# In test
app.dependency_overrides[get_settings] = lambda: MockSettings(
    COSMOS_ENDPOINT=None
)
```

### Service Injection Pattern (Optional)

```python
# core/dependencies.py
def get_repo() -> GroundTruthRepo:
    return container.repo

def get_assignment_service() -> AssignmentService:
    return container.assignment_service

# In new endpoint
@router.post("/example")
async def example(
    repo: Annotated[GroundTruthRepo, Depends(get_repo)]
):
    return await repo.some_method()
```

### Removing Hidden Dependencies

**Before (validation_service.py):**

```python
from app.container import container

async def validate_ground_truth_item(item, valid_tags_cache=None):
    if valid_tags_cache is None:
        valid_tags_cache = set(await container.tag_registry_service.list_tags())
```

**After:**

```python
class ValidationService:
    def __init__(self, tag_registry: TagRegistryService):
        self.tag_registry = tag_registry

    async def validate_ground_truth_item(self, item, valid_tags_cache=None):
        if valid_tags_cache is None:
            valid_tags_cache = set(await self.tag_registry.list_tags())
```

### Constraints

- Existing container pattern remains for current endpoints
- No async `Depends()` for services (lifespan manages initialization)
- `@lru_cache` used for singleton behavior in dependencies

## Implementation Phases

### Phase 1: Settings Injection

1. Create `core/dependencies.py` with `get_settings()`
2. Document pattern in README
3. Use in one endpoint as example
4. Add test demonstrating `dependency_overrides`

### Phase 2: Service Constructor Injection

1. Refactor `validation_service.py` to receive `TagRegistryService` via constructor
2. Update container wiring
3. Update tests

### Phase 3: Documentation

1. Add "Dependency Injection" section to backend README
2. Document when to use DI vs direct container access
3. Provide test example with `dependency_overrides`

## Open Questions

| Q | Question | Owner | Status |
|---|----------|-------|--------|
| Q1 | Should new endpoints mandate DI pattern? | Backend team | Open |
| Q2 | Is full migration worth the effort long-term? | Backend team | Deferred |

## References

- Research: [.copilot-tracking/subagent/20260122/dependency-injection-research.md](../.copilot-tracking/subagent/20260122/dependency-injection-research.md)
- [backend/app/container.py](../backend/app/container.py)
- [backend/app/services/validation_service.py](../backend/app/services/validation_service.py)
- [FastAPI Dependencies Documentation](https://fastapi.tiangolo.com/tutorial/dependencies/)
