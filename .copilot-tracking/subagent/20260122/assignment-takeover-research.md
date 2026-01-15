# Assignment Takeover Research

**Date:** 2026-01-22  
**Topic:** Assignment takeover system - allowing SMEs to reassign items currently assigned to others  
**Issue Reference:** SA-721

---

## Executive Summary

The current system **blocks** assignment of draft items that belong to another user (409 Conflict). There is **no existing force/takeover logic** in the codebase. The backend has a clear validation checkpoint that could be modified to accept a `force` parameter. The frontend uses `window.confirm()` for confirmation dialogs throughout the codebase.

---

## 1. Current Assignment Flow and Data Model

### Assignment Data Model

**GroundTruthItem** (in [backend/app/domain/models.py](backend/app/domain/models.py)):
```python
assignedTo: Optional[str] = Field(default=None, alias="assignedTo")
assigned_at: Optional[datetime] = Field(default=None, alias="assignedAt")
```

**AssignmentDocument** (materialized view for fast per-user queries):
```python
class AssignmentDocument(BaseModel):
    id: str  # stable id: "<dataset>|<bucket>|<groundTruthId>"
    pk: str  # SME user id (partition key)
    ground_truth_id: str
    datasetName: str
    bucket: UUID
    docType: str = "sme-assignment"
    schemaVersion: str = "v1"
```

### Assignment Flow

1. **Self-serve assignment** (`POST /v1/assignments/self-serve`):
   - Samples unassigned items from the pool
   - Assigns batch to requesting user
   - Creates `AssignmentDocument` for each item

2. **Single-item assignment** (`POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign`):
   - User explicitly selects an item to work on
   - Validates assignability (see conflict handling below)
   - Sets `assignedTo`, `assignedAt`, `status=draft`
   - Creates/updates `AssignmentDocument`

---

## 2. Backend Conflict Handling

### Current Validation Logic

Location: [backend/app/services/assignment_service.py#L199-L210](backend/app/services/assignment_service.py#L199-L210)

```python
# Validate item can be assigned
# Don't allow assignment of items already assigned to another user in draft state
if (
    item.assignedTo
    and item.assignedTo != user_id
    and item.status == GroundTruthStatus.draft
):
    logger.warning(
        f"assignment_service.assign_single_item.already_assigned - ..."
    )
    raise ValueError("Item is already assigned to another user")
```

### Assignment Rules (from [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md)):

| Scenario | Current Behavior |
|----------|------------------|
| Unassigned draft items | Can be assigned ✅ |
| Items assigned to another user (draft) | **Cannot be assigned (409 Conflict)** ❌ |
| Skipped items | Can be reassigned ✅ |
| Approved items | Can be assigned (moves to draft) ✅ |
| Deleted items | Can be assigned (moves to draft) ✅ |

### Repository Layer

Location: [backend/app/adapters/repos/cosmos_repo.py#L1719](backend/app/adapters/repos/cosmos_repo.py#L1719)

The `assign_to()` method is **state-agnostic** - it performs the assignment unconditionally. The state validation happens in the **service layer**, not the repository.

Filter predicate in Cosmos patch operation:
```python
filter_predicate = (
    f"FROM c WHERE (c.assignedTo = null OR c.assignedTo = '' "
    f"OR c.assignedTo = '{user_id}' OR c.status != 'draft')"
)
```

This prevents reassigning draft items at the database level too, but could be modified for force-assign scenarios.

---

## 3. Existing Force/Override Logic

**Finding: No existing force/override parameter exists.**

The current system has no mechanism to bypass the 409 Conflict for draft items assigned to others. The workaround mentioned in the PRD is:
> "delete the relevant assignment doc from cosmos and update the assignedTo field on the groundTruth doc"

---

## 4. Frontend Confirmation Dialog Patterns

The frontend uses **native `window.confirm()`** dialogs throughout. There are no custom modal confirmation components.

### Examples Found

1. **Unsaved changes warning** ([frontend/src/hooks/useGroundTruth.ts#L390](frontend/src/hooks/useGroundTruth.ts#L390)):
   ```typescript
   const confirmed = window.confirm(
       "You have unsaved changes. Switching items will discard them. Continue?",
   );
   ```

2. **Tag removal** ([frontend/src/components/app/editor/TagsEditor.tsx#L65](frontend/src/components/app/editor/TagsEditor.tsx#L65)):
   ```typescript
   const ok = window.confirm(`Remove tag "${tag}"?`);
   ```

3. **Turn deletion** ([frontend/src/components/app/editor/MultiTurnEditor.tsx#L161](frontend/src/components/app/editor/MultiTurnEditor.tsx#L161)):
   ```typescript
   if (window.confirm("Are you sure you want to delete this turn?")) {
   ```

4. **Reference removal** ([frontend/src/components/app/pages/ReferencesSection.tsx#L95](frontend/src/components/app/pages/ReferencesSection.tsx#L95)):
   ```typescript
   window.confirm(`Remove reference "${name}"? You can Undo for 8s.`)
   ```

5. **External link confirmation** ([frontend/src/components/modals/InspectItemModal.tsx](frontend/src/components/modals/InspectItemModal.tsx)):
   ```typescript
   const confirmed = confirm(
       `You are about to visit an external website:\n\n${parsedUrl.hostname}\n\nDo you want to continue?`,
   );
   ```

### Modal Infrastructure

- [frontend/src/hooks/useModalKeys.ts](frontend/src/hooks/useModalKeys.ts) - Keyboard handling for modals (Escape to close, Enter to confirm)
- [frontend/src/components/modals/ModalPortal.tsx](frontend/src/components/modals/ModalPortal.tsx) - Portal for rendering modals
- [frontend/src/components/modals/InspectItemModal.tsx](frontend/src/components/modals/InspectItemModal.tsx) - Example full modal implementation

---

## 5. Assignment Document Structure in Cosmos

### Container: `assignments`
- **Partition Key:** `/pk` (user ID with prefix `sme:{userId}`)

### Document Structure
```json
{
  "id": "{datasetName}|{bucket}|{itemId}",
  "pk": "sme:{userId}",
  "ground_truth_id": "{itemId}",
  "datasetName": "{datasetName}",
  "bucket": "{uuid}",
  "docType": "sme-assignment",
  "schemaVersion": "v1"
}
```

### Related Operations

- **Create/Update:** `repo.upsert_assignment_doc(user_id, item)`
- **Delete:** `repo.delete_assignment_doc(user_id, dataset, bucket, ground_truth_id)`
- **List by user:** `repo.list_assignments_by_user(user_id)`

---

## 6. Implementation Recommendations

### Backend Changes

1. **Add `force` parameter to `assign_single_item`:**
   ```python
   async def assign_single_item(
       self, dataset: str, bucket: UUID, item_id: str, user_id: str,
       force: bool = False  # NEW
   ) -> GroundTruthItem:
   ```

2. **Modify validation logic:**
   ```python
   if (
       item.assignedTo
       and item.assignedTo != user_id
       and item.status == GroundTruthStatus.draft
       and not force  # NEW: skip check if force=True
   ):
       raise ValueError("Item is already assigned to another user")
   ```

3. **Clean up old assignment document:**
   When force-assigning, delete the previous user's `AssignmentDocument` before creating the new one.

4. **Update API endpoint:**
   Accept `force` parameter in request body:
   ```python
   @router.post("/{dataset}/{bucket}/{item_id}/assign", status_code=200)
   async def assign_item(
       dataset: str,
       bucket: UUID,
       item_id: str,
       body: dict[str, Any] = {},  # NEW: accept { force: true }
       user: UserContext = Depends(get_current_user),
   ) -> GroundTruthItem:
   ```

### Frontend Changes

1. **Catch 409 Conflict** in the assign service call
2. **Show confirmation dialog** with current assignee info:
   ```typescript
   const confirmed = window.confirm(
       `This item is currently assigned to ${currentAssignee}. ` +
       `Do you want to take over this assignment?`
   );
   ```
3. **Retry with `force: true`** if user confirms

### API Contract

**Request:**
```http
POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign
Content-Type: application/json

{ "force": true }
```

**Response:** Same as current (updated `GroundTruthItem`)

---

## 7. Related Issues

- **SA-721:** "GTC: Re-think assignment limitations (unassign, vacation, etc.)"
  - Desired behavior from PRD:
    1. When a ground truth is already assigned to someone else, a different SME can choose "Assign to me anyway"
    2. UI prompts for confirmation before taking over the assignment
    3. After confirmation, assignment is transferred to the current user and the UI reflects the new assignee

---

## Key Files Reference

| Component | File |
|-----------|------|
| Assignment Service | [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py) |
| Assignment API Routes | [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py) |
| Cosmos Repository | [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py) |
| Domain Models | [backend/app/domain/models.py](backend/app/domain/models.py) |
| Frontend Assignment Service | [frontend/src/services/assignments.ts](frontend/src/services/assignments.ts) |
| Design Doc | [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md) |
