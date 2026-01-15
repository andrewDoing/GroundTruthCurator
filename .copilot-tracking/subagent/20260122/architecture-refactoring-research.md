# Architecture Refactoring Research

**Date:** 2026-01-22
**Stories:** SA-746 (Refactor API logic into services), SA-424 (Refactor cosmos_repo.py)

## Executive Summary

The backend has significant duplicate logic between `assignments.py` and `ground_truths.py` API endpoints. The `cosmos_repo.py` file is 1,500+ lines and contains emulator-specific workarounds and business logic that should be extracted. The existing service layer pattern (`AssignmentService`, `CurationService`, etc.) provides a clear blueprint for refactoring.

---

## 1. Current API Endpoint Structure

### Assignments API (`/v1/assignments/`)

| Endpoint | Method | Purpose | Frontend Usage |
|----------|--------|---------|----------------|
| `/self-serve` | POST | Bulk self-assignment | Yes - requestAssignmentsSelfServe |
| `/my` | GET | List user's assignments | Yes - getMyAssignments |
| `/{dataset}/{bucket}/{item_id}` | PUT | Update assigned item | Yes - updateAssignedGroundTruth |
| `/{dataset}/{bucket}/{item_id}/assign` | POST | Assign single item | Yes - assignItem |
| `/{dataset}/{bucket}/{item_id}/duplicate` | POST | Duplicate as rephrase | Yes - duplicateItem |

### Ground Truths API (`/v1/ground-truths/`)

| Endpoint | Method | Purpose | Frontend Usage |
|----------|--------|---------|----------------|
| `` | POST | Bulk import | No (admin) |
| `` | GET | List all (paginated) | Yes - listAllGroundTruths (Explorer) |
| `/snapshot` | POST/GET | Export snapshot | Yes - downloadSnapshot |
| `/{datasetName}` | GET | List by dataset | Unknown |
| `/{datasetName}/{bucket}/{item_id}` | GET | Get single item | Yes - getGroundTruth |
| `/{datasetName}/{bucket}/{item_id}` | PUT | Update item | Yes - restoreGroundTruth |
| `/{datasetName}/{bucket}/{item_id}` | DELETE | Soft delete | Yes - deleteGroundTruth |
| `/recompute-tags` | POST | Bulk tag recomputation | No (admin) |

---

## 2. Duplicate Logic Analysis

### 2.1 Item Update Logic (HIGH PRIORITY)

Both `assignments.py:update_item()` and `ground_truths.py:update_ground_truth()` contain nearly identical logic:

**Shared patterns (~80% overlap):**

```python
# Both endpoints do:
1. Fetch item via container.repo.get_gt()
2. Apply field updates (edited_question, answer, comment, status, refs, manual_tags)
3. Handle history field parsing (identical HistoryItem conversion)
4. Handle ETag validation (If-Match header or body.etag)
5. Apply computed tags via apply_computed_tags()
6. Persist via container.repo.upsert_gt()
7. Re-fetch and return updated item
```

**Differences:**

| Aspect | Assignments | Ground Truths |
|--------|------------|---------------|
| Authorization | `assignedTo == user` check | No assignment check |
| Status handling | Clears assignment on approve/delete | No assignment clearing |
| Payload model | `AssignmentUpdateRequest` (Pydantic) | `dict[str, Any]` (raw) |
| Assignment doc cleanup | Yes (deletes assignment doc) | No |
| `approve` flag | Convenience boolean | Not supported |

### 2.2 History Parsing (MEDIUM PRIORITY)

Identical history parsing code in both endpoints (~30 lines each):

```python
# Duplicated in assignments.py:140-160 and ground_truths.py:280-305
history_items = []
for h in payload.history:
    refs_data = h.get("refs")
    refs_list = None
    if refs_data is not None:
        refs_list = [r if isinstance(r, Reference) else Reference(**r) for r in refs_data]
    expected_behavior_data = h.get("expected_behavior") or h.get("expectedBehavior")
    history_items.append(HistoryItem(
        role=h["role"],
        msg=h.get("msg") or h.get("content", ""),
        refs=refs_list,
        expected_behavior=expected_behavior_data if isinstance(expected_behavior_data, list) else None,
    ))
it.history = history_items
```

### 2.3 Tag Handling (LOW PRIORITY)

Both endpoints validate and set `manual_tags` with identical patterns:

```python
if "manual_tags" in provided_fields:  # or "manualTags" in payload
    try:
        it.manual_tags = payload.manual_tags or []
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## 3. cosmos_repo.py Analysis

### 3.1 File Statistics

- **Total lines:** 1,536
- **Functions/methods:** 35+
- **Contains:** Cosmos emulator workarounds, Unicode sanitization, business logic

### 3.2 Logical Components (Candidates for Extraction)

| Component | Lines | Description | Extract To |
|-----------|-------|-------------|------------|
| Unicode sanitization | 50-150 | `_sanitize_string_for_cosmos`, `_normalize_unicode_for_cosmos`, `_restore_unicode_from_cosmos` | `cosmos_emulator.py` or `unicode_utils.py` |
| Base64 encoding for refs | 151-200 | `_base64_encode_refs_content`, `_base64_decode_refs_content` | `cosmos_emulator.py` |
| Sort security validation | 600-650 | `SortSecurityError`, `_build_secure_sort_clause` | Keep in repo (security) |
| Quota computation | 1100-1150 | `_compute_quotas` (largest remainder method) | `AssignmentService` |
| Query building | 500-600 | `_build_query_filter` | Keep in repo (query concern) |
| Document conversion | 350-450 | `_to_doc`, `_from_doc`, `_to_curation_doc`, `_from_curation_doc` | Keep in repo |

### 3.3 Business Logic in Repository (Should Move to Service)

1. **`sample_unassigned()`** (lines 1000-1150)
   - Contains allocation/weighting logic
   - Calls `_compute_quotas()` (policy decision)
   - Should be: Service orchestrates, repo just queries

2. **`assign_to()`** (lines 1200-1350)
   - Contains conditional assignment logic
   - User validation regex check (security concern - keep in service)
   - Different code paths for emulator vs production

3. **Total reference calculation** (lines 380-390)
   - `_compute_total_references()` is business logic
   - Currently in `_to_doc()` - should move to domain model or service

### 3.4 Emulator-Specific Code

The following are emulator workarounds that could be isolated:

```python
# Pattern: is_cosmos_emulator_in_use() checks
def is_cosmos_emulator_in_use(self) -> bool:
    return "localhost" in self._endpoint or "127.0.0.1" in self._endpoint

# Used in:
- list_gt_paginated() - routes to _list_gt_paginated_with_emulator()
- _get_filtered_count() - different counting strategy
- assign_to() - read-modify-replace vs patch
- upsert_gt() - retry logic for jsonb errors
- delete_dataset() - retry logic
```

---

## 4. Current Service Layer Structure

### 4.1 Existing Services

| Service | Location | Responsibility |
|---------|----------|----------------|
| `AssignmentService` | services/assignment_service.py | Self-assign, assign single, duplicate |
| `CurationService` | services/curation_service.py | Dataset curation instructions |
| `SnapshotService` | services/snapshot_service.py | Export snapshots |
| `TaggingService` | services/tagging_service.py | Tag validation, computed tags |
| `ValidationService` | services/validation_service.py | Bulk import validation |
| `SearchService` | services/search_service.py | Azure AI Search adapter |
| `TagRegistryService` | services/tag_registry_service.py | Tag registry management |
| `ChatService` | services/chat_service.py | AI chat functionality |

### 4.2 Service Pattern Used

```python
class AssignmentService:
    def __init__(self, repo: GroundTruthRepo):
        self.repo = repo
    
    async def self_assign(self, user_id: str, limit: int) -> list[GroundTruthItem]:
        # Orchestrates repo calls
        # Contains business logic (retry, shuffle, validation)
        pass
```

### 4.3 Container Wiring

```python
# container.py
self.assignment_service = AssignmentService(self.repo)
self.curation_service = CurationService(self.repo)
self.snapshot_service = SnapshotService(self.repo, ...)
```

---

## 5. Refactoring Recommendations

### 5.1 Phase 1: Extract Update Logic to Service (SA-746)

Create `GroundTruthService` with shared update logic:

```python
# services/ground_truth_service.py
class GroundTruthService:
    def __init__(self, repo: GroundTruthRepo):
        self.repo = repo
    
    async def update_item(
        self,
        dataset: str,
        bucket: UUID,
        item_id: str,
        updates: ItemUpdateDTO,
        user_id: str | None,
        etag: str | None,
        *,
        enforce_assignment: bool = False,
        clear_assignment_on_complete: bool = False,
    ) -> GroundTruthItem:
        """Unified item update logic."""
        pass
    
    def parse_history(self, raw_history: list[dict]) -> list[HistoryItem]:
        """Parse history from API payload."""
        pass
```

### 5.2 Phase 2: Split cosmos_repo.py (SA-424)

**File structure:**

```
backend/app/adapters/repos/
├── base.py                    # Protocol (unchanged)
├── cosmos_repo.py             # Core repo (~800 lines)
├── cosmos_emulator.py         # Emulator workarounds (~200 lines)
├── cosmos_unicode.py          # Unicode sanitization (~100 lines)
└── tags_repo.py               # Tags (unchanged)
```

**Extract to cosmos_emulator.py:**

- `_base64_encode_refs_content()`
- `_base64_decode_refs_content()`
- `_sanitize_string_for_cosmos()`
- `_normalize_unicode_for_cosmos()`
- `_restore_unicode_from_cosmos()`
- `_list_gt_paginated_with_emulator()` (as standalone function)
- `_assign_to_with_read_modify_replace()` (as standalone function)

**Move to service layer:**

- `_compute_quotas()` → `AssignmentService`
- `_compute_total_references()` → Domain model (`GroundTruthItem.total_references` property)

### 5.3 Phase 3: Consolidate API Endpoints (Optional)

Consider making `assignments` endpoint a thin wrapper that:

1. Validates assignment ownership
2. Calls `GroundTruthService.update_item()` with `enforce_assignment=True`
3. Handles assignment document cleanup

---

## 6. Frontend Impact Assessment

### Assignments Endpoints (All Used by Frontend)

- `POST /self-serve` - Used for initial assignment
- `GET /my` - Used for loading assigned items
- `PUT /{...}` - Used for all SME edits
- `POST /{...}/assign` - Used for explicit item assignment
- `POST /{...}/duplicate` - Used for rephrase creation

### Ground Truths Endpoints

- `GET /` (paginated) - Used by Explorer view
- `GET /{...}` - Used for item detail fetch
- `PUT /{...}` - Used for restore from deleted
- `DELETE /{...}` - Used for soft delete
- `GET /snapshot` - Used for export download

**Conclusion:** Both endpoint groups are actively used. Refactoring must preserve API contracts.

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking API contract | Low | High | Keep endpoint signatures identical |
| ETag behavior changes | Medium | High | Comprehensive integration tests |
| Emulator-specific regressions | Medium | Medium | Run test suite with emulator flag |
| Service layer adds latency | Low | Low | Profile before/after |

---

## 8. Next Steps

1. **Create spec** for `GroundTruthService` with unified update logic
2. **Define interface** for emulator compatibility layer
3. **Estimate effort** for each phase
4. **Prioritize** based on Jira story scope

---

## Appendix: File Line Counts

```
backend/app/api/v1/assignments.py     - 242 lines
backend/app/api/v1/ground_truths.py   - 405 lines
backend/app/adapters/repos/cosmos_repo.py - 1,536 lines
backend/app/adapters/repos/base.py    - 57 lines
backend/app/services/assignment_service.py - 210 lines
backend/app/services/curation_service.py - 35 lines
backend/app/services/tagging_service.py - 130 lines
backend/app/services/validation_service.py - 70 lines
backend/app/services/snapshot_service.py - 90 lines
```
