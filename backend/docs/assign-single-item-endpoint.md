# Assign Single Item Endpoint

## Overview

This document describes the new `/v1/assignments/{dataset}/{bucket}/{item_id}/assign` endpoint that allows users to manually assign a specific ground truth item to themselves.

## Endpoint Details

### Route

`POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign`

### Parameters

- `dataset` (path): The dataset name
- `bucket` (path): The bucket UUID
- `item_id` (path): The ground truth item ID
- User authentication via `get_current_user` dependency

### Response

- **200 OK**: Successfully assigned item, returns the updated `GroundTruthItem`
- **404 Not Found**: Item doesn't exist
- **409 Conflict**: Item is already assigned to another user in draft state

## Business Logic

### Assignment Rules

The endpoint validates and assigns items according to these rules:

1. **Unassigned draft items**: Can be assigned ✅
2. **Items assigned to another user (draft status)**: Cannot be assigned (409 Conflict) ❌
3. **Skipped items**: Can be reassigned to any user ✅
4. **Approved items**: Can be assigned (will be moved back to draft) ✅
5. **Deleted items**: Can be assigned (will be moved back to draft) ✅

**Important**: When an item is assigned, its status is **always set to draft**, regardless of previous state (approved, deleted, skipped, etc.).

### Assignment Process

1. Fetch the ground truth item
2. Validate the item is assignable:
   - Check it's not already assigned to another user in draft state
3. Call `repo.assign_to()` which unconditionally:
   - Sets `assignedTo` to the current user
   - Sets `assignedAt` to the current timestamp
   - Sets `status` to draft
   - Updates `updatedAt`
4. Create an assignment document in the assignments container via `repo.upsert_assignment_doc()`
5. Fetch and return the updated item

## Implementation Files

### Service Layer

**File**: `backend/app/services/assignment_service.py`

```python
async def assign_single_item(
    self, dataset: str, bucket: UUID, item_id: str, user_id: str
) -> GroundTruthItem:
    """Assign a single ground truth item to a user."""
```

### API Layer

**File**: `backend/app/api/v1/assignments.py`

```python
@router.post("/{dataset}/{bucket}/{item_id}/assign", status_code=200)
async def assign_item(...) -> GroundTruthItem:
    """Assign a specific ground truth item to the current user."""
```

### Repository Layer

**File**: `backend/app/adapters/repos/cosmos_repo.py`

The `assign_to()` method is now **state-agnostic**:
- It no longer checks or validates the item's current status
- It unconditionally assigns the item and sets status to draft
- State validation is the responsibility of the service layer

## Assignment Document

When an item is successfully assigned, an assignment document is created in the assignments container with:

- `id`: `{dataset}|{bucket}|{item_id}` (stable, idempotent)
- `pk`: The user's ID (for fast per-user queries)
- `ground_truth_id`: Reference to the ground truth item
- `datasetName` and `bucket`: For fetching the actual item

This materialized view allows fast retrieval of all items assigned to a user via `/v1/assignments/my`.

## Testing

Integration tests are located in:
**File**: `backend/tests/integration/test_assignments_assign_single_cosmos.py`

Test coverage includes:

- ✅ Successfully assigning an unassigned item
- ✅ 404 error for non-existent items
- ✅ 409 conflict for items already assigned to another user (draft state)
- ✅ Successfully reassigning skipped items
- ✅ Successfully assigning approved items (moves them back to draft)

## Comparison with Self-Serve

This endpoint differs from `/v1/assignments/self-serve` in that:

- **Self-serve**: Automatically picks and assigns N unassigned items (validates state before assignment)
- **Single assign**: User explicitly chooses which specific item to work on (allows reassigning approved/deleted items)

Both create assignment documents and update the `assignedTo` field on the ground truth item.

## State Validation

**Repository Layer (`assign_to`)**: State-agnostic - assigns any item regardless of current state

**Service Layer**:
- `self_assign()`: Validates items are draft (unassigned) or skipped before assignment
- `assign_single_item()`: Only validates that draft items aren't assigned to another user; allows assignment of approved/deleted/skipped items
