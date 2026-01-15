# Validation Error Clarity Research

**Date:** 2026-01-22  
**Jira Reference:** SA-334 "Key Paragraph too large for generation error is not clear to the user"

---

## Executive Summary

The validation error clarity system has **significant gaps**. The 2000-character limit for key paragraphs is enforced **only in the frontend UI** (character counter display) but **not in the backend validation**. When errors occur, the frontend displays generic messages because `mapApiErrorToMessage()` extracts only the `detail` or `message` field from API errors without semantic mapping to user-friendly guidance.

---

## Research Questions & Findings

### 1. What is the key paragraph validation in the backend (2000 char limit)?

**Finding: The 2000-character limit is NOT enforced in the backend.**

- Backend `Reference` model at [backend/app/domain/models.py](backend/app/domain/models.py#L12-L24):
  ```python
  class Reference(BaseModel):
      url: str = Field(description="Reference URL (required, non-empty)")
      title: str | None = Field(default=None)
      content: str | None = None
      keyExcerpt: str | None = None  # <-- No max_length validation
      type: str | None = None
      bonus: bool = False
      messageIndex: Optional[int] = None
  ```
  
- The `keyExcerpt` field (maps to `keyParagraph` in frontend) has **no length constraints** defined.

- The 2000-character limit exists **only in the frontend UI display** at [frontend/src/components/app/editor/TurnReferencesModal.tsx](frontend/src/components/app/editor/TurnReferencesModal.tsx#L341):
  ```tsx
  <span className={cn("rounded-full px-2 py-0.5", ...)}>
    {len}/40 (2000 max)
  </span>
  ```
  
- This is purely informational - **no validation prevents submission of longer text**.

### 2. How does the backend return validation errors?

**Finding: Generic HTTPException pattern with `detail` field.**

The backend uses FastAPI's `HTTPException` with a `detail` parameter:

- Example from [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L234-L236):
  ```python
  raise HTTPException(
      status_code=400,
      detail=f"Tag '{tag[:50]}...' exceeds maximum length of {MAX_TAG_LENGTH} characters.",
  )
  ```

- Validation errors return HTTP 422 with `HTTPValidationError` schema containing:
  ```json
  {
    "detail": [
      {
        "type": "string",
        "loc": ["body", "field_name"],
        "msg": "validation error message",
        "input": "..."
      }
    ]
  }
  ```

- Chat endpoint uses safe error messages at [backend/app/api/v1/chat.py](backend/app/api/v1/chat.py#L20-L24):
  ```python
  SAFE_ERROR_MESSAGES = {
      "invalid_input": "Invalid request format",
      "service_unavailable": "Service temporarily unavailable",
      "processing_error": "Unable to process request",
  }
  ```

### 3. How does the frontend currently display validation errors?

**Finding: Generic error display with minimal user guidance.**

- Error mapping utility at [frontend/src/services/http.ts](frontend/src/services/http.ts#L26-L36):
  ```typescript
  export function mapApiErrorToMessage(err: unknown): string {
    const e = err as Partial<ApiError & { data?: Record<string, unknown> }>;
    if (e && typeof e === "object" && typeof e.status === "number") {
      const data = e.data as Record<string, unknown> | undefined;
      const detail =
        (typeof data?.detail === "string" && data.detail) ||
        (typeof data?.message === "string" && data.message) ||
        "";
      return `${e.status} ${e.statusText ?? "Error"}${detail ? ` – ${detail}` : ""}`;
    }
    return "Network or unexpected error";
  }
  ```

- The `save()` function in [frontend/src/hooks/useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts#L248-L252) returns errors as-is:
  ```typescript
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
  ```

- **No error transformation** maps technical errors to user-friendly messages with remediation guidance.

### 4. What error message mapping/transformation exists?

**Finding: No semantic error mapping exists in either layer.**

- Frontend does **not** have an error code registry or mapping table.
- Backend uses `detail` strings directly without error codes.
- The only pattern observed is `TagsModal.tsx` which has local `validationError` state for immediate UI feedback, but this doesn't apply to save operations.

### 5. Where is key paragraph handled in the UI?

**Locations identified:**

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| `TurnReferencesModal` | [frontend/src/components/app/editor/TurnReferencesModal.tsx](frontend/src/components/app/editor/TurnReferencesModal.tsx#L304-L341) | 304-341 | Primary key paragraph editor with character counter |
| `useGroundTruth` | [frontend/src/hooks/useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts#L122) | 122, 154 | Trims keyParagraph in reference mapping |
| API mapper | [frontend/src/adapters/apiMapper.ts](frontend/src/adapters/apiMapper.ts#L34) | 34, 64, 117, 127, 155 | Maps between `keyParagraph` (frontend) and `keyExcerpt` (backend) |

**Key UI behavior:**
- Character counter shows `{len}/40 (2000 max)` but this is **advisory only**
- Textarea has no `maxLength` attribute
- No client-side validation before submission

---

## Gap Analysis

### Current State vs Desired State

| Aspect | Current State | Desired State |
|--------|--------------|---------------|
| Backend validation | None for keyExcerpt length | 2000 char limit enforced |
| Error format | Generic `detail` string | Structured error with code, field, and remediation |
| Frontend mapping | Pass-through display | Semantic mapping to user-friendly messages |
| UI feedback | Post-submission error | Real-time validation + clear guidance |

### Root Causes of SA-334

1. **Missing backend validation**: The 2000-character limit mentioned in SA-334 doesn't exist in backend code
2. **Generic error handling**: `mapApiErrorToMessage()` produces messages like `"400 Bad Request – Invalid request format"` without context
3. **No error code system**: Cannot map backend errors to specific UI guidance
4. **Frontend-only limit display**: The `(2000 max)` indicator suggests a limit that isn't enforced

---

## Recommendations

### Immediate (SA-334 Fix)

1. **Add backend validation** for `keyExcerpt`:
   ```python
   # backend/app/domain/models.py
   keyExcerpt: str | None = Field(default=None, max_length=2000)
   ```

2. **Add frontend validation** in `TurnReferencesModal.tsx`:
   ```tsx
   // Add maxLength to textarea
   <textarea
     maxLength={2000}
     // existing props...
   />
   ```

3. **Display specific error** when limit exceeded:
   ```tsx
   {len > 2000 && (
     <span className="text-red-600">
       Key paragraph exceeds 2000 character limit
     </span>
   )}
   ```

### Long-term (Validation Error Clarity System)

1. **Create error code registry** in backend with structured errors:
   ```python
   class ValidationErrorCode(str, Enum):
       KEY_PARAGRAPH_TOO_LONG = "KEY_PARAGRAPH_TOO_LONG"
       TAG_EXCEEDS_LENGTH = "TAG_EXCEEDS_LENGTH"
       # ...
   ```

2. **Build frontend error mapper** that translates codes to guidance:
   ```typescript
   const ERROR_MESSAGES: Record<string, ErrorGuidance> = {
     KEY_PARAGRAPH_TOO_LONG: {
       title: "Key paragraph too long",
       message: "Shorten to under 2000 characters",
       field: "keyParagraph"
     }
   };
   ```

3. **Add real-time validation** with character counter styling:
   - Green when under limit
   - Yellow when approaching (e.g., 1800+)
   - Red when exceeded

---

## Files for Modification

| Priority | File | Change |
|----------|------|--------|
| High | [backend/app/domain/models.py](backend/app/domain/models.py) | Add `max_length=2000` to `keyExcerpt` |
| High | [frontend/src/components/app/editor/TurnReferencesModal.tsx](frontend/src/components/app/editor/TurnReferencesModal.tsx) | Add maxLength, validation styling |
| Medium | [frontend/src/services/http.ts](frontend/src/services/http.ts) | Create error mapping system |
| Medium | [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py) | Return structured validation errors |
| Low | [frontend/src/hooks/useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts) | Surface validation errors per-field |

---

## Appendix: Code References

### Backend HTTPValidationError Schema

From [frontend/src/api/openapi.json](frontend/src/api/openapi.json#L132-L136):
```json
{
  "description": "Validation Error",
  "content": {
    "application/json": {
      "schema": {
        "$ref": "#/components/schemas/HTTPValidationError"
      }
    }
  }
}
```

### Frontend Reference Model Mapping

From [frontend/src/services/groundTruths.ts](frontend/src/services/groundTruths.ts#L76):
```typescript
keyParagraph: r.keyExcerpt ?? undefined,
```

The field is called `keyParagraph` in frontend models and `keyExcerpt` in the backend/API schema.

### Configuration Flag

From [backend/app/core/config.py](backend/app/core/config.py#L89):
```python
REQUIRE_KEY_PARAGRAPH: bool = False  # Require key paragraphs for relevant references
```

This flag controls whether key paragraphs are required for approval, but doesn't enforce length limits.
