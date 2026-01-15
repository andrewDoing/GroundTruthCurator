# Draft Duplicate Detection Research

**Date:** 2026-01-22
**Topic:** Draft duplicate detection system for warning SMEs about potential duplicates

---

## Research Questions and Findings

### 1. Data Model for Ground Truth Items (Draft vs Approved Status)

**Backend Model:** [backend/app/domain/models.py](backend/app/domain/models.py)

The `GroundTruthItem` class defines the core data model:

```python
class GroundTruthItem(BaseModel):
    id: str
    datasetName: str
    bucket: Optional[UUID] = None
    status: GroundTruthStatus = GroundTruthStatus.draft  # Default is draft
    docType: str = "ground-truth-item"
    schemaVersion: str = "v2"
    
    # Question/Answer fields
    synth_question: str = Field(alias="synthQuestion")  # Original synthesized question
    edited_question: Optional[str] = Field(default=None, alias="editedQuestion")  # User-edited version
    answer: Optional[str] = None
    refs: list[Reference] = []
    
    # Multi-turn support
    history: Optional[list[HistoryItem]] = None
    
    # Tags
    manual_tags: list[str] = []
    computed_tags: list[str] = []
```

**Status Enum:** [backend/app/domain/enums.py](backend/app/domain/enums.py)

```python
class GroundTruthStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    deleted = "deleted"
    skipped = "skipped"
```

**Frontend Model:** [frontend/src/models/groundTruth.ts](frontend/src/models/groundTruth.ts)

```typescript
export type GroundTruthItem = {
    id: string;
    question: string;  // Maps to editedQuestion or synthQuestion
    answer: string;
    history?: ConversationTurn[];
    references: Reference[];
    status: "draft" | "approved" | "skipped" | "deleted";
    deleted?: boolean;  // Soft delete flag
    // ...
};
```

---

### 2. Fields for Duplicate Comparison

**Primary Comparison Candidates:**

| Field | Backend Name | Frontend Name | Notes |
|-------|-------------|---------------|-------|
| Original Question | `synthQuestion` | N/A (mapped to `question`) | The AI-generated/imported question text |
| Edited Question | `editedQuestion` | `question` | User-curated question (takes precedence if set) |
| Answer | `answer` | `answer` | The curated answer text |
| Multi-turn History | `history` | `history` | Array of `{role, msg, refs}` for conversation turns |

**Effective Question Logic:**
- Backend: `synthQuestion` is the original; `editedQuestion` is the user's edited version
- Frontend: Uses `editedQuestion || synthQuestion` as `question`
- For duplicate detection: Compare `editedQuestion || synthQuestion` between items

**Fingerprint/Signature Logic:** [frontend/src/hooks/useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts#L113-L135)

The `stateSignature` function shows what fields define item identity:
```typescript
function stateSignature(it: GroundTruthItem): string {
    return JSON.stringify({
        id: it.id,
        question: (it.question || "").trim(),
        answer: (it.answer || "").trim(),
        history: it.history || [],
        references: refs,  // sorted by id
        manualTags: [...(it.manualTags || [])].sort(),
        status: it.status,
        deleted: !!it.deleted,
    });
}
```

**Recommended Comparison Fields for Duplicate Detection:**
1. **Question text** (normalized): `(editedQuestion || synthQuestion).trim().toLowerCase()`
2. **Answer text** (normalized): `answer.trim().toLowerCase()`
3. **Multi-turn content**: Concatenated `history[*].msg` for all turns

---

### 3. Existing Duplicate Detection Logic

**Finding: NO existing duplicate detection logic exists.**

Grep search for `duplicate|similarity|compare` found:
- References to Jira tickets requesting the feature (SA-534, SA-535)
- Tag registry duplicate key prevention (unrelated)
- Reference deduplication within a single item (not cross-item)

**Existing Validation Service:** [backend/app/services/validation_service.py](backend/app/services/validation_service.py)

Current validation only checks:
- Manual tag values against the tag registry
- No duplicate item detection

**Jira Context:**
- **SA-534:** "GTC: Duplicate Detection and Prevention for Drafts" (Spike, MVP label)
- **SA-535:** "GTC: One time pass duplicate removal from drafts/approved"

Both tickets indicate the requirement: *"As an SME I want to avoid working on draft items that are duplicates of approved items."*

---

### 4. Import/Creation Flow for Draft Items

**Bulk Import Endpoint:** [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L54-L114)

```python
@router.post("", response_model=ImportBulkResponse)
async def import_bulk(
    items: list[GroundTruthItem],
    buckets: int | None = Query(default=None),
    approve: bool = Query(default=False),
) -> ImportBulkResponse:
```

**Current Import Flow:**
1. Items received via POST `/v1/ground-truths`
2. Generate IDs for items without one (randomname)
3. Validate items via `validate_bulk_items()` (tags only)
4. Optionally set approval metadata if `approve=true`
5. Apply computed tags
6. Persist via `container.repo.import_bulk_gt()`

**Insertion Point for Duplicate Detection:**
- After step 2 (ID generation), before step 5 (persistence)
- Or as a pre-import validation step

**Single Item Assignment:** [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py#L175-L220)

When an SME assigns an item to themselves:
1. Fetch the item
2. Validate item can be assigned (not assigned to another user in draft)
3. Set `status = draft`, `assignedTo = user`
4. Create assignment document

**Insertion Point:** Before or after step 3, check for duplicates against approved items.

---

### 5. Warning/Notification Patterns in UI

**Toast System:** [frontend/src/hooks/useToasts.ts](frontend/src/hooks/useToasts.ts)

```typescript
export type Toast = {
    id: string;
    kind: "success" | "error" | "info";
    msg: string;
    actionLabel?: string;
    onAction?: () => void;
};

export function useToasts() {
    // showToast(kind, msg, opts)
    // opts: { duration, actionLabel, onAction }
}
```

**Toast Component:** [frontend/src/components/common/Toasts.tsx](frontend/src/components/common/Toasts.tsx)

- Displays in bottom-right corner
- Color-coded by kind (success=emerald, error=rose, info=violet)
- Supports action buttons for interactive toasts

**Usage Pattern for Warnings:**
```typescript
showToast("info", "This draft may duplicate an approved item", {
    duration: 8000,
    actionLabel: "View Similar",
    onAction: () => openSimilarItemsModal()
});
```

**Alert Icon Component:** [frontend/src/components/app/QueueSidebar.tsx](frontend/src/components/app/QueueSidebar.tsx#L181)

Uses `CircleAlert` from lucide-react for inline warnings:
```tsx
<CircleAlert className="h-3.5 w-3.5" /> unsaved
```

---

## Implementation Recommendations

### Backend Duplicate Detection Service

Create `backend/app/services/duplicate_detection_service.py`:

```python
class DuplicateDetectionService:
    async def find_similar_approved(
        self, 
        item: GroundTruthItem,
        threshold: float = 0.9
    ) -> list[GroundTruthItem]:
        """Find approved items similar to the given draft item."""
        pass
    
    async def check_bulk_for_duplicates(
        self, 
        items: list[GroundTruthItem]
    ) -> dict[str, list[str]]:
        """Check a batch of items for duplicates. Returns {item_id: [similar_ids]}."""
        pass
```

### Comparison Strategies

1. **Exact Match:** Normalize and compare question text directly
2. **Fuzzy Match:** Use Levenshtein distance or similar
3. **Semantic Match:** Embed questions and use cosine similarity (future)

### API Response Extension

Extend `ImportBulkResponse` to include warnings:

```python
class ImportBulkResponse(BaseModel):
    imported: int
    errors: list[str]
    uuids: list[str]
    warnings: list[DuplicateWarning] = []  # NEW

class DuplicateWarning(BaseModel):
    draft_id: str
    similar_approved_ids: list[str]
    similarity_score: float
```

### Frontend Integration

1. **On Import:** Show summary of potential duplicates
2. **On Assignment:** Toast warning if assigned item resembles approved
3. **In Editor:** Badge or inline warning in sidebar for flagged items

---

## Summary

| Question | Finding |
|----------|---------|
| Data model for draft/approved? | `GroundTruthStatus` enum with `draft`, `approved`, `deleted`, `skipped` |
| Fields for comparison? | `synthQuestion`, `editedQuestion`, `answer`, `history[*].msg` |
| Existing duplicate detection? | **None** - feature is requested in Jira (SA-534, SA-535) |
| Import/creation flow? | Bulk import via POST `/v1/ground-truths`; single assign via assignment service |
| UI warning patterns? | Toast system with `success/error/info` kinds; `CircleAlert` icon for inline warnings |

---

## Files Referenced

- [backend/app/domain/models.py](backend/app/domain/models.py) - GroundTruthItem model
- [backend/app/domain/enums.py](backend/app/domain/enums.py) - GroundTruthStatus enum
- [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py) - Import endpoint
- [backend/app/services/validation_service.py](backend/app/services/validation_service.py) - Current validation
- [backend/app/services/assignment_service.py](backend/app/services/assignment_service.py) - Assignment flow
- [frontend/src/models/groundTruth.ts](frontend/src/models/groundTruth.ts) - Frontend model
- [frontend/src/hooks/useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts) - State signature logic
- [frontend/src/hooks/useToasts.ts](frontend/src/hooks/useToasts.ts) - Toast system
- [frontend/src/components/common/Toasts.tsx](frontend/src/components/common/Toasts.tsx) - Toast component
