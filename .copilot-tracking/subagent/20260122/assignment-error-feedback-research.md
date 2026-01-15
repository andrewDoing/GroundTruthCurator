# Assignment Error Feedback Research

**Date:** 2025-01-22
**Topic:** assignment-error-feedback
**Status:** Complete

## Executive Summary

The assignment error feedback system has partial implementation. The backend returns appropriate status codes (409 for conflicts) with generic messages, but the frontend displays generic "Failed to assign item" errors instead of the backend's specific messages. The toast notification system is in place and supports actionable buttons, but is not leveraged for assignment conflict scenarios.

---

## Research Findings

### 1. Backend Response Structure for "Already Assigned" Failure

**Location:** [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L258-L300)

The `assign_item` endpoint handles assignment errors:

```python
@router.post("/{dataset}/{bucket}/{item_id}/assign", status_code=200)
async def assign_item(...) -> GroundTruthItem:
    try:
        assigned = await container.assignment_service.assign_single_item(...)
        return assigned
    except ValueError as e:
        error_msg = str(e)
        if "already assigned" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail="This item is already assigned to another user.",
            )
```

**Service Layer:** [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L196-L207)

```python
if (
    item.assignedTo
    and item.assignedTo != user_id
    and item.status == GroundTruthStatus.draft
):
    raise ValueError("Item is already assigned to another user")
```

### 2. Status Codes and Error Payload

| Scenario | Status Code | Detail Message |
|----------|-------------|----------------|
| Item already assigned to another user (draft) | **409 Conflict** | `"This item is already assigned to another user."` |
| Item not found | **404 Not Found** | `"The requested item could not be found or has been deleted."` |
| Other validation failures | **400 Bad Request** | `"Unable to assign this item. Please check the item status and try again."` |

**Current Payload Structure:**
```json
{
  "detail": "This item is already assigned to another user."
}
```

**Gap Identified:** The payload does NOT include:
- Error code (e.g., `ASSIGNMENT_CONFLICT`)
- Current assignee identity (`assignedTo`)
- Structured error object

The PRD (SA-825) explicitly requires:
> "Backend returns a specific status code (e.g., 409 Conflict) and a structured error payload (e.g., code + assignedTo) so the frontend can render the correct UX."

### 3. Frontend Error Handling for Assignments

**Location:** [frontend/src/demo.tsx](frontend/src/demo.tsx#L184-L213)

```tsx
onAssign={async (item) => {
  try {
    await assignItem(item.datasetName, item.bucket, item.id);
    toast("success", `Assigned ${item.id} for curation`);
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Failed to assign item";
    toast("error", message);
  }
}}
```

**Service Layer:** [frontend/src/services/assignments.ts](frontend/src/services/assignments.ts#L64-L76)

```typescript
export async function assignItem(
  dataset: string,
  bucket: string,
  itemId: string,
): Promise<GroundTruthItemOut> {
  const { data, error } = await client.POST(
    "/v1/assignments/{dataset}/{bucket}/{item_id}/assign",
    { params: { path: { dataset, bucket, item_id: itemId } } },
  );
  if (error) throw error;
  return data as unknown as GroundTruthItemOut;
}
```

**Gap Identified:** The frontend:
1. Throws the raw error object from `openapi-fetch`
2. Only extracts `error.message` which may not contain the backend's `detail`
3. Does NOT check status codes or parse structured error responses
4. Falls back to generic "Failed to assign item" message

### 4. Toast/Notification System

**Location:** [frontend/src/hooks/useToasts.ts](frontend/src/hooks/useToasts.ts)

The toast system supports:
- **Types:** `success`, `error`, `info`
- **Actionable buttons:** `actionLabel` and `onAction` callback
- **Auto-dismiss:** Configurable duration (default 3500ms)

```typescript
export type Toast = {
  id: string;
  kind: "success" | "error" | "info";
  msg: string;
  actionLabel?: string;  // ← Supports action buttons
  onAction?: () => void; // ← Callback for action
};

const showToast = useCallback(
  (kind: Toast["kind"], msg: string, opts?: ShowOptions) => { ... },
  [dismiss],
);
```

**Toast Component:** [frontend/src/components/common/Toasts.tsx](frontend/src/components/common/Toasts.tsx)

The UI renders action buttons when provided:
```tsx
{t.actionLabel && t.onAction && (
  <button onClick={() => onActionClick?.(t.id, t.onAction)}>
    {t.actionLabel}
  </button>
)}
```

### 5. Assignment Logic Locations

#### Backend

| Component | File | Purpose |
|-----------|------|---------|
| API Route | [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L258) | `POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign` |
| Service | [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L175) | `assign_single_item()` - validation & orchestration |
| Repository | [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1859) | `assign_to()` - database operations |
| Error Classes | [backend/app/core/errors.py](backend/app/core/errors.py) | `ConflictError(HTTPException)` - not currently used for assignments |

#### Frontend

| Component | File | Purpose |
|-----------|------|---------|
| Service | [frontend/src/services/assignments.ts](frontend/src/services/assignments.ts#L64) | `assignItem()` - API call |
| Main App | [frontend/src/demo.tsx](frontend/src/demo.tsx#L184) | `onAssign` handler with error display |
| Toast Hook | [frontend/src/hooks/useToasts.ts](frontend/src/hooks/useToasts.ts) | Toast state management |
| Toast UI | [frontend/src/components/common/Toasts.tsx](frontend/src/components/common/Toasts.tsx) | Toast rendering |

---

## Gap Analysis

| Requirement (SA-825) | Current State | Gap |
|---------------------|---------------|-----|
| Clear, specific error message in UI | Generic "Failed to assign item" | ❌ Backend message not surfaced |
| Toast includes action to view assignee | No action button shown | ❌ Not implemented |
| Assignee identity surfaced | Not included in error response | ❌ Backend doesn't return `assignedTo` |
| Structured error payload with code | Plain `detail` string only | ❌ No error code or assignee field |

---

## Recommendations

### Backend Changes

1. **Enhance error response structure** in [assignments.py](backend/app/api/v1/assignments.py#L290-L295):
   ```python
   raise HTTPException(
       status_code=409,
       detail={
           "code": "ASSIGNMENT_CONFLICT",
           "message": "This item is already assigned to another user.",
           "assignedTo": item.assignedTo  # Include current assignee
       }
   )
   ```

2. **Update OpenAPI spec** to document 409 response schema with error structure.

### Frontend Changes

1. **Parse error responses** in [assignments.ts](frontend/src/services/assignments.ts#L64-L76) to extract status code and detail:
   ```typescript
   if (error?.status === 409) {
     throw new AssignmentConflictError(error.body.detail);
   }
   ```

2. **Show specific toast with action** in [demo.tsx](frontend/src/demo.tsx#L206-L211):
   ```typescript
   toast("error", `Assigned to ${assignee}`, {
     actionLabel: "View",
     onAction: () => showAssigneeProfile(assignee)
   });
   ```

---

## Related Documentation

- [backend/docs/assign-single-item-endpoint.md](backend/docs/assign-single-item-endpoint.md) - Endpoint specification
- [backend/docs/api-change-checklist-assignments.md](backend/docs/api-change-checklist-assignments.md) - API change guidelines
- [prd-refined-2.json](prd-refined-2.json) - SA-825 requirements

## Test Coverage

Existing integration test: [backend/tests/integration/test_assignments_assign_single_cosmos.py](backend/tests/integration/test_assignments_assign_single_cosmos.py#L77-L93)

```python
async def test_assign_single_item_already_assigned(...):
    """Test assigning an item already assigned to another user returns 409."""
    # Verifies 409 status code for conflict scenario
    r = await async_client.post(f"/v1/assignments/{ds}/{bucket}/{item_id}/assign", ...)
    assert r.status_code == 409
```
