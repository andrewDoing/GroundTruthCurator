---
title: PII Detection
description: The PII detection system scans ground truth content during import to identify and flag personally identifiable information
jtbd: JTBD-004
author: spec-builder
ms.date: 2026-01-22
status: draft
stories: [SA-669]
---

# PII Detection

## Overview

The PII detection system scans ground truth content during bulk import to identify and warn users about personally identifiable information (email addresses and phone numbers) without blocking the import process.

**Parent JTBD:** Help administrators ensure data integrity and security

## Problem Statement

Ground truth datasets may inadvertently contain personally identifiable information such as email addresses and phone numbers embedded in question/answer content. Without proactive detection, this PII can propagate through training pipelines and downstream systems, creating compliance and privacy risks. SA-669 identifies the need for automated PII scanning during import to alert administrators while preserving import workflow efficiency.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Detect email addresses in text fields | Must | System identifies valid email patterns (user@domain.tld) with ≥95% precision |
| FR-002 | Detect US phone numbers in text fields | Must | System identifies phone patterns including (555) 123-4567, 555-123-4567, +1 555 123 4567 |
| FR-003 | Scan high-priority content fields | Must | System scans synthQuestion, editedQuestion, answer, comment, and history[].msg fields |
| FR-004 | Return warnings in import response | Must | ImportBulkResponse includes pii_warnings array with item_id, field, pattern_type, and masked snippet |
| FR-005 | Allow import to proceed with PII | Must | Import completes successfully regardless of PII warnings; warnings are informational only |
| FR-006 | Support feature flag toggle | Should | PII_DETECTION_ENABLED flag controls whether scanning runs (default: enabled) |
| FR-007 | Scan reference content fields | Could | System scans refs[].content and refs[].keyExcerpt fields |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | PII scan must not significantly degrade bulk import latency | <50ms overhead per 100 items |
| NFR-002 | Scalability | Scan must process items concurrently | Leverage asyncio.gather pattern |
| NFR-003 | Extensibility | Pattern detection must support future pattern types | Pluggable pattern registry design |
| NFR-004 | Accuracy | False positive rate for email detection | <5% |
| NFR-005 | Accuracy | False positive rate for phone detection | <10% |

## User Stories

### US-001: Administrator Receives PII Warnings During Import

**As an** administrator importing ground truth data,  
**I want to** receive warnings when imported content contains potential PII,  
**So that** I can review and remediate sensitive data before it enters production pipelines.

**Acceptance Criteria:**

1. Given a bulk import request containing items with email addresses, when the import completes, then the response includes pii_warnings identifying the affected items and fields.
2. Given a bulk import request containing items with phone numbers, when the import completes, then the response includes pii_warnings with pattern_type "phone".
3. Given a bulk import request with no PII, when the import completes, then the pii_warnings array is empty.
4. Given PII is detected in multiple fields of a single item, then each occurrence is reported as a separate warning.
5. Given PII detection is disabled via feature flag, when importing content with PII, then no warnings are returned.

### US-002: Administrator Reviews PII Warning Details

**As an** administrator reviewing import results,  
**I want to** see which specific field and item contains PII,  
**So that** I can locate and correct the problematic content.

**Acceptance Criteria:**

1. Each warning includes the item_id for identification.
2. Each warning includes the field name (e.g., "synthQuestion", "history[2].msg").
3. Each warning includes a masked snippet showing surrounding context.
4. Each warning includes the pattern_type ("email" or "phone").

## Technical Considerations

### Integration Point

PII detection integrates into the bulk import flow after ID generation and tag validation, but before persistence:

```
POST /v1/ground-truths
    → Generate IDs
    → Validate Tags
    → **PII Detection** ← New step
    → Apply Computed Tags
    → Persist to Cosmos DB
    → Return response with pii_warnings
```

### Recommended Implementation Approach

**Phase 1 (MVP):** Regex-based detection for email and phone patterns.

- Zero additional dependencies
- Fast execution
- Sufficient for high-signal patterns

**Phase 2 (Future):** Migrate to Microsoft Presidio for broader PII coverage.

- Support for SSN, credit cards, names
- ML-based detection for better accuracy
- Enterprise-grade, Microsoft-maintained

### Service Architecture

Create a dedicated `pii_service.py` following existing service patterns:

```python
class PIIDetectionService:
    def scan_text(self, text: str) -> list[PIIMatch]
    async def scan_item(self, item: GroundTruthItem) -> list[PIIWarning]
    async def scan_bulk(self, items: list[GroundTruthItem]) -> list[PIIWarning]
```

### Response Model Extension

```python
class PIIWarning(BaseModel):
    item_id: str
    field: str
    pattern_type: str  # "email", "phone"
    snippet: str       # Masked context snippet
    position: int      # Character position

class ImportBulkResponse(BaseModel):
    imported: int
    errors: list[str]
    uuids: list[str]
    pii_warnings: list[PIIWarning] = Field(default_factory=list)
```

### Feature Flag

Add `PII_DETECTION_ENABLED` configuration flag (default: `True`) to allow operators to disable scanning if needed during rollout or for performance-sensitive imports.

### Fields to Scan

| Field | Priority | Rationale |
|-------|----------|-----------|
| synth_question | High | Primary user-facing content |
| edited_question | High | Curator-modified content |
| answer | High | Response content |
| comment | High | Curator notes |
| history[].msg | High | Multi-turn conversation content |
| refs[].content | Medium | Reference material (Phase 2) |
| refs[].keyExcerpt | Medium | Excerpt text (Phase 2) |

## Open Questions

1. **Snippet masking strategy:** Should detected PII be fully masked in the snippet (e.g., `j***@example.com`) or partially visible for verification?
2. **Bulk import UI integration:** How should the frontend display PII warnings to users? Toast notification, modal, or inline in import results?
3. **Audit logging:** Should PII detection events be logged for compliance auditing?
4. **International phone formats:** Should Phase 1 include non-US phone number patterns?

## References

- SA-669 - GTC Needs PII Check
- [Research file](.copilot-tracking/subagent/20260122/pii-detection-research.md)
- [Microsoft Presidio documentation](https://microsoft.github.io/presidio/)
- [backend/app/services/validation_service.py](../backend/app/services/validation_service.py)
- [backend/app/api/v1/ground_truths.py](../backend/app/api/v1/ground_truths.py)
