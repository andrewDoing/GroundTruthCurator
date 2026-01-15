---
title: Reference Identity
description: The reference identity system uses chunk ID from the search index as the primary uniqueness key instead of URL
jtbd: JTBD-007
author: spec-builder
ms.date: 2026-01-22
status: draft
stories: [SA-821, SA-257]
---

# Reference Identity

## Overview

The reference identity system uses chunk ID from the search index as the primary uniqueness key instead of URL.

**Parent JTBD:** Help GTC handle chunked document references correctly

## Problem Statement

When the search index contains chunked documents, multiple chunks can share the same URL but represent different content. The current URL-based de-duplication causes two problems:

1. **Accidental bulk-add**: Selecting one chunk from search results adds all chunks with that URL, since de-duplication treats them as identical.
2. **Content confusion**: Curators cannot independently reference specific chunks from the same source document.

The search index already provides a unique chunk ID (`chunk_id`), but GTC does not propagate or use it as the primary identifier.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | References shall use chunk ID as the primary uniqueness key | Must | De-duplication compares by chunk ID, not URL |
| FR-002 | Multiple chunks with the same URL shall be treated as distinct references | Must | Adding chunk A does not auto-add chunk B with same URL |
| FR-003 | URL shall remain available for user navigation | Must | Reference links still open the source URL |
| FR-004 | Legacy references without chunk ID shall fall back to URL-based identity | Should | Existing data continues to work |
| FR-005 | Backend shall persist chunk ID with references | Must | Chunk ID survives save/load cycle |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Compatibility | Legacy references without chunk ID remain functional | Zero data loss |
| NFR-002 | Data Integrity | Chunk ID is preserved through the full data lifecycle | ID matches search index source |

## User Stories

### US-001: Select specific chunk

**As a** curator  
**I want to** select a specific chunk from search results  
**So that** I reference exactly the content I reviewed, not all chunks from that URL

**Acceptance Criteria:**

- [ ] Given search returns chunks A, B, C with the same URL, when I select chunk B, then only chunk B is added
- [ ] Given chunk B is already selected, when I select chunk A, then both A and B appear as separate references

### US-002: Distinguish chunks in reference list

**As a** curator  
**I want to** see which chunk I selected when multiple share a URL  
**So that** I can verify I referenced the correct content

**Acceptance Criteria:**

- [ ] Given two chunks with the same URL are selected, when I view the reference list, then they appear as distinct entries
- [ ] Given a reference from a chunked document, when I view its details, then the chunk ID is visible
- [ ] Given a reference from a chunked document, when I click to view it, then I can read the chunk text content

## Technical Considerations

### Data Model Changes

**Backend Reference model** ([backend/app/domain/models.py](../backend/app/domain/models.py)):

Current:

```python
class Reference(BaseModel):
    url: str = Field(description="Reference URL (required, non-empty)")
    title: str | None = None
    # ... other fields, no id
```

Required:

```python
class Reference(BaseModel):
    id: str | None = Field(default=None, description="Chunk ID from search index")
    url: str = Field(description="Reference URL for navigation")
    title: str | None = None
    # ...
```

**Frontend Reference type** ([frontend/src/models/groundTruth.ts](../frontend/src/models/groundTruth.ts)) already has `id: string`. Change is ensuring this ID comes from the search index chunk ID rather than being generated.

### Identity Key Logic

Update [dedupeReferences](../frontend/src/models/gtHelpers.ts#L33-L46) to use chunk ID:

```typescript
export function dedupeReferences(existing: Reference[], chosen: Reference[]): Reference[] {
    // Primary key: id (chunk ID) if available, else fall back to URL
    const makeKey = (r: Reference) => r.id || r.url;  // Changed from URL + messageIndex
    // ... rest unchanged
}
```

Note: `messageIndex` is no longer part of the de-duplication key since references are already stored at the message level in `history[].refs[]`.

### Data Flow

```text
Search Index
    ↓ chunk_id, url, title, content
Inference Adapter (already extracts chunk_id as id)
    ↓ { id: chunk_id, url, ... }
Frontend Search Service (already uses id if present)
    ↓ Reference with id = chunk_id
De-duplication (CHANGE: use id instead of url)
    ↓ unique references by chunk ID
Backend Persistence (CHANGE: store id field)
    ↓ Reference.id persisted
API Response (CHANGE: return stored id, not generated)
    ↓ Reference with original chunk_id
```

### Files Requiring Changes

| File | Change |
|------|--------|
| [backend/app/domain/models.py](../backend/app/domain/models.py) | Add optional `id` field to Reference |
| [frontend/src/models/gtHelpers.ts](../frontend/src/models/gtHelpers.ts) | Update `dedupeReferences` to use `id` |
| [frontend/src/services/groundTruths.ts](../frontend/src/services/groundTruths.ts) | Preserve stored `id` instead of generating sequential IDs |
| [frontend/src/components/app/editor/TurnReferencesModal.tsx](../frontend/src/components/app/editor/TurnReferencesModal.tsx) | Update duplicate check to use `id` |

### Migration Considerations

- **Existing references**: Lack chunk ID; use URL as fallback identity key.
- **New references**: Chunk ID from search index becomes the identity key.
- **Mixed state**: De-duplication handles both cases via `id || url` fallback.

## Open Questions

(None - all resolved)

## Resolved Questions

| Q | Question | Resolution |
|---|----------|------------|
| Q1 | Should the UI display chunk ID or some chunk-distinguishing metadata? | Display chunk ID and allow users to view chunk text content |
| Q2 | What happens if the same chunk is added to different turns? Should chunk ID alone or chunk ID + messageIndex be the composite key? | Chunk ID alone; references are already stored at the message level in `history[].refs[]` |

## References

- [SA-821](https://example.atlassian.net/browse/SA-821) - Support Chunking
- [SA-257](https://example.atlassian.net/browse/SA-257) - BUG: References add everything with same URL
- [Research file](../.copilot-tracking/subagent/20260122/reference-identity-research.md) - Codebase analysis
- [reference-management.md](reference-management.md) - Current-state reference spec
