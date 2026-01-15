# PII Detection Research

**Date:** 2026-01-22  
**Story:** SA-669 - GTC Needs PII Check  
**Status:** Research Complete

## Executive Summary

This document captures research findings for implementing PII detection in the Ground Truth Curator's bulk import flow. The feature should scan imported content for personally identifiable information (email addresses and phone numbers first) and warn users without blocking import.

---

## 1. Current Import Flow Analysis

### Bulk Import Endpoint

**File:** [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py#L54-L114)

The `import_bulk()` endpoint processes ground truth items through these steps:

```
1. Receive items via POST /v1/ground-truths
2. Generate IDs for items without one (randomname)
3. Validate items via validate_bulk_items() ← CURRENT VALIDATION HOOK
4. Filter invalid items, collect errors
5. Optionally set approval metadata if approve=true
6. Apply computed tags to each item
7. Persist via container.repo.import_bulk_gt()
8. Return ImportBulkResponse with imported count, errors, and uuids
```

### Current Validation Service

**File:** [backend/app/services/validation_service.py](backend/app/services/validation_service.py)

The validation service currently:

- Validates manual tags against the tag registry
- Returns a dict mapping item ID to list of validation errors
- Uses async/concurrent validation for performance
- Pre-fetches tag registry once for all items (efficiency pattern)

**Key functions:**

- `validate_ground_truth_item(item, valid_tags_cache)` - validates single item
- `validate_bulk_items(items)` - validates list concurrently

### Fields Containing Scannable Content

From [backend/app/domain/models.py](backend/app/domain/models.py#L52-L120):

| Field | Type | Description | PII Scan Priority |
|-------|------|-------------|-------------------|
| `synth_question` | str | Primary question text | **High** |
| `edited_question` | str | User-edited question | **High** |
| `answer` | str | Answer content | **High** |
| `comment` | str | Curator notes | **High** |
| `history[].msg` | str | Multi-turn messages | **High** |
| `refs[].content` | str | Reference content | Medium |
| `refs[].keyExcerpt` | str | Key excerpt text | Medium |
| `contextUsedForGeneration` | str | Context source | Medium |

---

## 2. Python PII Detection Libraries

### Microsoft Presidio (Recommended)

**Package:** `presidio-analyzer`  
**Repository:** https://github.com/microsoft/presidio  
**License:** MIT

**Pros:**

- Microsoft-maintained, enterprise-grade
- Extensible recognizer architecture
- Supports custom patterns and ML models
- Good out-of-box support for email, phone, SSN, credit cards
- Active maintenance and community

**Cons:**

- Heavier dependency footprint (spaCy optional but recommended)
- Requires model downloads for best accuracy

**Usage Example:**

```python
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()
results = analyzer.analyze(
    text="Contact john.doe@example.com or call 555-123-4567",
    entities=["EMAIL_ADDRESS", "PHONE_NUMBER"],
    language="en"
)
# Returns list of RecognizerResult with entity_type, start, end, score
```

### Scrubadub

**Package:** `scrubadub`  
**Repository:** https://github.com/datascopeanalytics/scrubadub

**Pros:**

- Lightweight, pure Python
- Simple API
- Good for basic patterns

**Cons:**

- Less actively maintained
- Fewer entity types
- Lower accuracy than Presidio

### Regex-Only Approach

For MVP/Phase 1, simple regex patterns could suffice:

```python
import re

EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)
PHONE_PATTERN = re.compile(
    r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
)
```

**Pros:** Zero dependencies, fast, simple  
**Cons:** Higher false positive/negative rates, harder to extend

### Recommendation

**Phase 1:** Start with regex patterns for email and phone (per story requirements)  
**Phase 2:** Migrate to Presidio for broader PII coverage and better accuracy

---

## 3. Patterns to Detect (Per SA-669)

Story states: "Detection focuses on high-signal patterns first (email addresses and phone numbers)."

### Phase 1 Patterns

| Pattern | Regex | Examples |
|---------|-------|----------|
| Email | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}` | user@domain.com |
| Phone (US) | `(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}` | 555-123-4567, (555) 123-4567 |

### Future Patterns (Phase 2+)

- SSN: `\d{3}-\d{2}-\d{4}`
- Credit card: Luhn-validated 16-digit numbers
- IP addresses: `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}`
- Names (ML-based via Presidio)

---

## 4. Warning Flow Design

### Requirements from SA-669

> "If potential PII is detected, the system warns the user but still allows the import to proceed."

### Proposed Response Model

Extend `ImportBulkResponse` to include PII warnings:

```python
class PIIWarning(BaseModel):
    item_id: str
    field: str
    pattern_type: str  # "email", "phone", etc.
    snippet: str  # Masked snippet showing context
    position: int  # Character position in field

class ImportBulkResponse(BaseModel):
    imported: int
    errors: list[str]
    uuids: list[str]
    pii_warnings: list[PIIWarning] = Field(default_factory=list)  # NEW
```

### Flow Diagram

```
POST /v1/ground-truths
         │
         ▼
   Generate IDs
         │
         ▼
   Validate Tags (existing)
         │
         ▼
┌────────────────────────┐
│   PII Detection (NEW)  │
│  - Scan text fields    │
│  - Collect warnings    │
│  - Continue import     │
└────────────────────────┘
         │
         ▼
   Apply Computed Tags
         │
         ▼
   Persist to Cosmos DB
         │
         ▼
   Return Response with:
   - imported count
   - errors
   - uuids
   - pii_warnings ◄── NEW
```

---

## 5. Recommended Integration Points

### Option A: Extend `validation_service.py` (Recommended)

Add PII scanning alongside tag validation:

```python
# validation_service.py

async def scan_for_pii(item: GroundTruthItem) -> list[PIIWarning]:
    """Scan item content fields for PII patterns."""
    warnings = []
    fields_to_scan = [
        ("synthQuestion", item.synth_question),
        ("editedQuestion", item.edited_question),
        ("answer", item.answer),
        ("comment", item.comment),
    ]
    
    # Also scan history messages
    for idx, turn in enumerate(item.history or []):
        fields_to_scan.append((f"history[{idx}].msg", turn.msg))
    
    for field_name, content in fields_to_scan:
        if content:
            warnings.extend(_detect_pii_in_text(item.id, field_name, content))
    
    return warnings

async def validate_bulk_items_with_pii(
    items: list[GroundTruthItem]
) -> tuple[dict[str, list[str]], list[PIIWarning]]:
    """Validate items and scan for PII."""
    validation_errors = await validate_bulk_items(items)
    
    # Scan for PII concurrently
    pii_tasks = [scan_for_pii(item) for item in items]
    pii_results = await asyncio.gather(*pii_tasks)
    
    all_warnings = []
    for warnings in pii_results:
        all_warnings.extend(warnings)
    
    return validation_errors, all_warnings
```

### Option B: New `pii_service.py`

Create a dedicated service (better separation of concerns):

```python
# app/services/pii_service.py

class PIIDetectionService:
    def __init__(self):
        self._email_pattern = re.compile(...)
        self._phone_pattern = re.compile(...)
    
    def scan_text(self, text: str) -> list[PIIMatch]:
        """Scan text for PII patterns."""
        ...
    
    async def scan_item(self, item: GroundTruthItem) -> list[PIIWarning]:
        """Scan all text fields in a ground truth item."""
        ...
    
    async def scan_bulk(self, items: list[GroundTruthItem]) -> list[PIIWarning]:
        """Scan multiple items concurrently."""
        ...
```

### Recommendation

**Option B (new service)** is preferred because:

1. Follows existing service patterns (see `tagging_service.py`, `search_service.py`)
2. Easier to test in isolation
3. Cleaner separation from tag validation concerns
4. Easier to evolve (e.g., swap regex for Presidio later)

---

## 6. Implementation Checklist

### Backend Changes

- [ ] Create `app/services/pii_service.py` with regex-based detection
- [ ] Add `PIIWarning` model to `app/domain/models.py`
- [ ] Extend `ImportBulkResponse` with `pii_warnings` field
- [ ] Call PII service in `import_bulk()` endpoint
- [ ] Add unit tests for PII detection patterns
- [ ] Add integration tests for bulk import with PII warnings

### Configuration

- [ ] Add `PII_DETECTION_ENABLED` feature flag (default: True)
- [ ] Add `PII_PATTERNS` config for enabled pattern types

### Documentation

- [ ] Update API docs with new response field
- [ ] Document PII detection patterns and limitations

---

## 7. Test Cases

### Unit Tests

```python
def test_detect_email_in_question():
    item = GroundTruthItem(
        synthQuestion="Contact support@company.com for help"
    )
    warnings = scan_for_pii(item)
    assert len(warnings) == 1
    assert warnings[0].pattern_type == "email"

def test_detect_phone_in_answer():
    item = GroundTruthItem(
        answer="Call us at 555-123-4567"
    )
    warnings = scan_for_pii(item)
    assert len(warnings) == 1
    assert warnings[0].pattern_type == "phone"

def test_no_pii_returns_empty():
    item = GroundTruthItem(
        synthQuestion="How do I reset my password?"
    )
    warnings = scan_for_pii(item)
    assert len(warnings) == 0
```

### Integration Tests

```python
async def test_bulk_import_returns_pii_warnings(async_client):
    payload = [{
        "datasetName": "test",
        "synthQuestion": "Email john@example.com for details"
    }]
    response = await async_client.post("/v1/ground-truths", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 1  # Import succeeds
    assert len(data["pii_warnings"]) == 1  # Warning returned
```

---

## 8. References

- **Story:** SA-669 - GTC Needs PII Check
- **Presidio Docs:** https://microsoft.github.io/presidio/
- **Existing Validation:** [backend/app/services/validation_service.py](backend/app/services/validation_service.py)
- **Import Endpoint:** [backend/app/api/v1/ground_truths.py](backend/app/api/v1/ground_truths.py)
- **Domain Models:** [backend/app/domain/models.py](backend/app/domain/models.py)
