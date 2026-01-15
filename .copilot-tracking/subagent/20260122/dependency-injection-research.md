# Dependency Injection Research: SA-238

**Research Date:** 2026-01-22
**Topic:** Refactoring to use FastAPI dependency injection for config and cosmos

---

## 1. Current Architecture Analysis

### 1.1 Container.py Overview

The [container.py](backend/app/container.py) file implements a **Service Locator** pattern (not true DI):

```python
class Container:
    repo: GroundTruthRepo
    assignment_service: AssignmentService
    search_service: SearchService
    snapshot_service: SnapshotService
    curation_service: CurationService
    tag_registry_service: TagRegistryService
    # ... more services

container = Container()  # Global singleton
```

**Key characteristics:**

- Single global `container` instance created at module import time
- Services initialized lazily via explicit `init_*()` methods
- Cosmos repo created via `init_cosmos_repo(db_name)` or `startup_cosmos(db_name)`
- Services store direct references to other services and repos

### 1.2 Service Instantiation Flow

1. **App startup** ([main.py](backend/app/main.py#L60-L78)):
   - `lifespan()` async context manager calls `container.startup_cosmos()`
   - This creates repo instances and wires services

2. **Container initialization methods**:
   - `init_cosmos_repo()` - Creates Cosmos repo and dependent services
   - `init_search()` - Configures Azure AI Search adapter
   - `init_chat()` - Configures agent inference service

### 1.3 Endpoint Access Pattern

Endpoints access services via **direct module import** of the global container:

```python
# In every API router file
from app.container import container

@router.post("")
async def import_bulk(...):
    result = await container.repo.import_bulk_gt(gt_items, buckets=buckets)
```

This pattern repeats across all 16+ files that import `container`.

---

## 2. Existing FastAPI `Depends()` Usage

The codebase **already uses** `Depends()` extensively for authentication:

| File | Usage Pattern |
|------|---------------|
| [ground_truths.py](backend/app/api/v1/ground_truths.py) | `user: UserContext = Depends(get_current_user)` |
| [assignments.py](backend/app/api/v1/assignments.py) | `user: UserContext = Depends(get_current_user)` |
| [search.py](backend/app/api/v1/search.py) | `user: UserContext = Depends(get_current_user)` |
| [chat.py](backend/app/api/v1/chat.py) | `principal: Principal = Depends(require_user)` |
| [main.py](backend/app/main.py#L181) | `dependencies=[Depends(require_user)]` on routes |

**24+ usages** of `Depends()` found, all for authentication.

**No services** are currently injected via `Depends()`.

---

## 3. Configuration Access Pattern

### 3.1 Settings Module ([config.py](backend/app/core/config.py))

Configuration uses **Pydantic Settings** with a global singleton:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GTC_", ...)
    
    COSMOS_ENDPOINT: str | None = None
    COSMOS_KEY: SecretStr | None = None
    # ... 60+ settings

settings = Settings()  # Global singleton
```

### 3.2 Settings Access

Settings are accessed via direct import throughout:

```python
from app.core.config import settings

# Container uses it
if settings.COSMOS_ENDPOINT:
    ...
    
# Services use it
if settings.CHAT_ENABLED:
    ...
```

---

## 4. Pain Points Identified

### 4.1 Testing Complexity

**Integration tests** require extensive fixtures to manage container state:

From [tests/integration/conftest.py](backend/tests/integration/conftest.py#L87-L124):

```python
@pytest.fixture(scope="function")
async def configure_repo_for_test_db(require_cosmos_backend, test_db_name, init_emulator_containers):
    # Close any previous Cosmos async client
    try:
        prev_repo = getattr(container, "repo", None)
        client = getattr(prev_repo, "_client", None)
        if client is not None:
            # Manual cleanup...
    except Exception:
        pass
    container.init_cosmos_repo(db_name=test_db_name)
```

**Unit tests** create fake repos and directly mutate container:

From [tests/unit/conftest.py](backend/tests/unit/conftest.py#L59-L130):

```python
container.repo = _NoopMemoryRepo()
container.assignment_service = AssignmentService(container.repo)
container.snapshot_service = SnapshotService(container.repo, ...)
# ... manual wiring of all services
```

### 4.2 Service Coupling

The [validation_service.py](backend/app/services/validation_service.py) directly imports container:

```python
from app.container import container

async def validate_ground_truth_item(item, valid_tags_cache=None):
    if valid_tags_cache is None:
        valid_tags_cache = set(await container.tag_registry_service.list_tags())
```

This creates a **hidden dependency** that's hard to mock without modifying the global container.

### 4.3 Async Initialization Complexity

Container uses `cast(ServiceType, None)` as placeholder until async init:

```python
self.repo = cast(GroundTruthRepo, None)
self.assignment_service = cast(AssignmentService, None)
```

This leads to potential `None` access if initialization order is wrong.

---

## 5. What FastAPI DI Would Provide

### 5.1 Benefits

| Current Approach | FastAPI DI Alternative |
|------------------|------------------------|
| Global mutable singleton | Request-scoped or cached dependencies |
| Manual container wiring in tests | `app.dependency_overrides[dep] = mock` |
| Import-time coupling | Runtime injection |
| Settings passed around manually | `Annotated[Settings, Depends(get_settings)]` |

### 5.2 Example Transformation

**Current:**
```python
from app.container import container

@router.post("")
async def import_bulk(items: list[GroundTruthItem]):
    result = await container.repo.import_bulk_gt(items)
```

**With FastAPI DI:**
```python
def get_repo() -> GroundTruthRepo:
    return container.repo  # Or create fresh

@router.post("")
async def import_bulk(
    items: list[GroundTruthItem],
    repo: GroundTruthRepo = Depends(get_repo)
):
    result = await repo.import_bulk_gt(items)
```

**Test override:**
```python
async def test_import():
    app.dependency_overrides[get_repo] = lambda: MockRepo()
    # Test now uses MockRepo without touching global container
```

---

## 6. Assessment

### 6.1 Current Approach Works

The current Service Locator pattern is:

- **Consistent** - Used uniformly across all endpoints
- **Simple** - One import gives access to all services
- **Tested** - Extensive test coverage exists
- **Functional** - No reported bugs related to DI

### 6.2 Migration Complexity

A full FastAPI DI migration would require:

1. Creating `Depends()` functions for each service (~8 services)
2. Updating all endpoint signatures (~50+ endpoints)
3. Rewriting test fixtures to use `dependency_overrides`
4. Managing async initialization differently (lifespan vs per-request)

### 6.3 Recommendation

**Status: Consider deferring or partial adoption**

The current approach is working. Potential improvements without full migration:

1. **Partial adoption**: Use `Depends()` for new endpoints
2. **Settings injection**: Create `get_settings()` dependency for easier testing
3. **Service injection for validation_service**: Remove direct container import

---

## 7. Summary

| Question | Finding |
|----------|---------|
| What does container.py do? | Service Locator with lazy initialization, holds all service singletons |
| How are services accessed? | Direct import of global `container` instance |
| What config objects exist? | Single `Settings` Pydantic model, global `settings` instance |
| Pain points? | Test complexity, service coupling, async init management |
| FastAPI DI already used? | Yes, but only for auth (`get_current_user`, `require_user`) |
| Migration worth it? | Partial adoption may be sufficient; full migration is high effort |
