---
title: Assignment Takeover
description: The assignment takeover system allows admins and team leads to reassign items currently assigned to others with appropriate confirmation.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
stories: [SA-721]
---

## Overview

Admins and team leads can reassign ground truth items that are currently assigned to another SME in draft status, with a confirmation dialog to prevent accidental takeovers.

**Parent JTBD:** Help SMEs curate ground truth items effectively

## Problem Statement

When a ground truth item is assigned to an SME who is unavailable (vacation, left the team, or overloaded), there is no supported way to reassign the item. The current system returns a 409 Conflict error when attempting to assign an item already assigned to another user in draft status. The only workaround is direct Cosmos DB manipulation—deleting the assignment document and updating the `assignedTo` field manually—which is error-prone and requires database access.

## Requirements

### Functional Requirements

| ID   | Requirement                                                                      | Priority |
| ---- | -------------------------------------------------------------------------------- | -------- |
| FR-1 | The system must accept a `force` parameter on the assign endpoint                | Must     |
| FR-2 | Only users with `admin` or `team-lead` role can use the force parameter          | Must     |
| FR-3 | When force-assigning, the system must clean up the previous user's assignment document | Must     |
| FR-4 | The API must return 403 Forbidden if a non-privileged user attempts force assignment | Must     |
| FR-5 | The 409 Conflict response must include the current assignee's identifier         | Should   |
| FR-6 | The frontend must show a confirmation dialog before force-assigning              | Must     |
| FR-7 | The confirmation dialog must display who currently owns the assignment           | Should   |
| FR-8 | The force-assign UI control must only be visible to admin/team-lead users        | Must     |

### Non-Functional Requirements

| ID    | Requirement                                                     | Target        |
| ----- | --------------------------------------------------------------- | ------------- |
| NFR-1 | Force-assign latency                                            | < 500ms p95   |
| NFR-2 | Assignment document cleanup must be atomic with reassignment     | Consistency   |
| NFR-3 | Audit trail must record force-assign events with previous owner  | Compliance    |

## User Stories

### US-1: Team Lead Reassigns Abandoned Item

**As a** team lead  
**I want to** take over an item assigned to an unavailable SME  
**So that** the curation work can continue without delays

**Acceptance Criteria:**

1. Given I am logged in with a team-lead role
2. When I attempt to assign an item currently assigned to another user
3. Then I see a confirmation dialog showing who currently owns the item
4. When I confirm the takeover
5. Then the item is reassigned to me
6. And the previous assignment document is deleted
7. And I can immediately begin editing the item

### US-2: Admin Reassigns During Offboarding

**As an** admin  
**I want to** reassign all items from a departing team member  
**So that** their work queue is redistributed

**Acceptance Criteria:**

1. Given I am logged in with an admin role
2. When I navigate to an item assigned to the departing user
3. And I click "Assign to me"
4. Then I see a confirmation: "This item is assigned to {user}. Take over assignment?"
5. When I confirm, the assignment transfers to me

### US-3: Regular SME Cannot Force-Assign

**As a** regular SME  
**I want to** understand why I cannot take over someone else's item  
**So that** I know to escalate to my team lead

**Acceptance Criteria:**

1. Given I am logged in without admin or team-lead role
2. When I attempt to assign an item owned by another user
3. Then I see a 409 Conflict error message
4. And I do not see a "force assign" or "take over" option
5. And the message indicates the item is assigned to another user

## Technical Considerations

### Backend Changes

#### API Endpoint Modification

Update `POST /v1/assignments/{dataset}/{bucket}/{item_id}/assign` to accept an optional request body:

```json
{
  "force": true
}
```

#### Service Layer Changes

Location: `backend/app/services/assignment_service.py`

1. Add `force: bool = False` parameter to `assign_single_item()`
2. Modify validation logic to check role before allowing force:

```python
if (
    item.assignedTo
    and item.assignedTo != user_id
    and item.status == GroundTruthStatus.draft
):
    if not force:
        raise ValueError("Item is already assigned to another user")
    if not self._has_takeover_permission(user_roles):
        raise PermissionError("Force assignment requires admin or team-lead role")
    # Clean up previous assignment document
    await self._repo.delete_assignment_doc(
        item.assignedTo, dataset, bucket, item_id
    )
```

3. Add role validation helper:

```python
def _has_takeover_permission(self, roles: list[str]) -> bool:
    return "admin" in roles or "team-lead" in roles
```

#### Enhanced 409 Response

Include current assignee in conflict response for frontend display:

```json
{
  "detail": "Item is already assigned to another user",
  "assignedTo": "alice@example.com"
}
```

### Frontend Changes

#### Conditional UI Based on Role

1. Add role check utility in auth context
2. Only show "Take over" option to users with admin/team-lead role
3. Regular SMEs see only the conflict error message

#### Confirmation Dialog

Use existing `window.confirm()` pattern consistent with codebase:

```typescript
const confirmed = window.confirm(
  `This item is currently assigned to ${currentAssignee}. ` +
  `Do you want to take over this assignment?`
);
if (confirmed) {
  await assignItem(dataset, bucket, itemId, { force: true });
}
```

#### Error Handling Flow

1. Catch 409 Conflict from initial assign attempt
2. Parse `assignedTo` from error response
3. If user has takeover permission, show confirmation dialog
4. If user lacks permission, display error: "This item is assigned to {user}. Contact your team lead."

### Authorization

#### Role Determination

Roles are populated from Azure AD claims via Easy Auth:

- `Principal.roles` is extracted from the `roles` claim in `X-MS-CLIENT-PRINCIPAL`
- `UserContext.roles` passes this through to API handlers

#### Required Roles

| Role        | Source            | Permissions                  |
| ----------- | ----------------- | ---------------------------- |
| `admin`     | Azure AD app role  | Full force-assign capability |
| `team-lead` | Azure AD app role  | Force-assign within their scope |

#### Configuration

Azure AD app registration must define these roles in the manifest:

```json
{
  "appRoles": [
    {
      "displayName": "Admin",
      "value": "admin",
      "allowedMemberTypes": ["User"]
    },
    {
      "displayName": "Team Lead",
      "value": "team-lead",
      "allowedMemberTypes": ["User"]
    }
  ]
}
```

## Open Questions

None.

## References

- [SA-721](https://jira.example.com/browse/SA-721) - GTC: Re-think assignment limitations (unassign, vacation, etc.)
- [Research file](../.copilot-tracking/subagent/20260122/assignment-takeover-research.md)
- [Assign single item endpoint](../backend/docs/assign-single-item-endpoint.md)
- [Auth module](../backend/app/core/auth.py)
