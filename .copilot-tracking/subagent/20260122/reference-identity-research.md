# Reference Identity Research

**Date:** 2026-01-22  
**Topic:** Reference identity system using chunk ID from search index as primary uniqueness key

## Executive Summary

The current reference system uses **URL as the primary de-duplication key** in the frontend, with a secondary `id` field that is assigned at display time (sequential `ref_0`, `ref_1`, etc.) rather than from the search index. The search index **does provide a chunk ID** (via `chunk_id` field) from the inference adapter, but it is only partially propagated through the system.

## Findings

### 1. Current Reference Data Model

#### Backend Model ([backend/app/domain/models.py](../../../backend/app/domain/models.py#L13-L35))

```python
class Reference(BaseModel):
    url: str = Field(description="Reference URL (required, non-empty)")
    title: str | None = Field(default=None)
    content: str | None = None
    keyExcerpt: str | None = None
    type: str | None = None
    bonus: bool = False
    messageIndex: Optional[int] = None
```

**Key observation:** The backend `Reference` model has **no `id` field**. URL is the only required identifier.

#### Frontend Model ([frontend/src/models/groundTruth.ts](../../../frontend/src/models/groundTruth.ts#L16-L27))

```typescript
export type Reference = {
    id: string;           // Required in frontend
    title?: string;
    url: string;          // Required
    snippet?: string;
    visitedAt?: string | null;
    keyParagraph?: string;
    bonus?: boolean;
    messageIndex?: number;
};
```

**Key observation:** Frontend requires an `id` field, but this is **generated locally** and not persisted.

### 2. URL-Based De-duplication Location

#### Primary De-duplication: [frontend/src/models/gtHelpers.ts](../../../frontend/src/models/gtHelpers.ts#L33-L46)

```typescript
export function dedupeReferences(
    existing: Reference[],
    chosen: Reference[],
): Reference[] {
    const makeKey = (r: Reference) =>
        r.messageIndex !== undefined ? `${r.url}::turn${r.messageIndex}` : r.url;
    
    const map = new Map(existing.map((r) => [makeKey(r), r] as const));
    for (const r of chosen) {
        const key = makeKey(r);
        if (!map.has(key)) {
            map.set(key, r);
        }
    }
    return Array.from(map.values());
}
```

**De-duplication key:** `URL` (or `URL::turnN` for multi-turn contexts)

#### TurnReferencesModal duplicate check: [frontend/src/components/app/editor/TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx#L85)

```typescript
const urlsInTurn = new Set(turnRefs.map((r) => normalizeUrl(r.url)));
```

### 3. Backend Storage/Persistence

References are stored as part of `GroundTruthItem` documents in Cosmos DB:

- **Top-level refs:** `GroundTruthItem.refs: list[Reference]`
- **Turn-level refs:** `GroundTruthItem.history[].refs: list[Reference]`

The backend persists all reference fields **except** the frontend-only `id`. The Reference model validates that URL cannot be empty ([backend/app/domain/models.py](../../../backend/app/domain/models.py#L31-L34)).

### 4. Search Index Fields - Chunk ID Availability

#### Chat/Inference Adapter: [backend/app/adapters/gtc_inference_adapter.py](../../../backend/app/adapters/gtc_inference_adapter.py#L103-L128)

```python
def _extract_references(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for call in calls:
        results = call.get("results", [])
        for doc in results:
            ref = {
                "id": doc.get("chunk_id") or doc.get("id"),  # ✅ chunk_id IS available
                "title": doc.get("title"),
                "url": doc.get("url"),
                "snippet": doc.get("content"),
            }
            references.append(ref)
```

**The chunk ID is extracted from search results** as `chunk_id` (preferred) or `id` (fallback).

#### Azure AI Search Tool Processing: [backend/app/adapters/inference/inference.py](../../../backend/app/adapters/inference/inference.py#L419)

```python
call["results"].append({"title": titles[i], "url": urls[i], "chunk_id": ids[i]})
```

**The search index provides:** `titles[]`, `urls[]`, `ids[]` (chunk IDs) in the metadata.

#### Frontend Search Service: [frontend/src/services/search.ts](../../../frontend/src/services/search.ts#L24-L53)

```typescript
function mapWireToReference(x: SearchResultWire): Reference | null {
    // ...
    let id: string = randId("ref");  // Default: random ID
    if (typeof o.id === "string" && o.id) id = o.id;  // Use provided ID if available
    else if (doc && typeof doc.id === "string") id = doc.id as string;
    return { id, title, url, snippet, visitedAt: null, keyParagraph: "" };
}
```

**Current behavior:** Uses the ID from search results if available, but falls back to random ID.

### 5. Downstream Systems Affected by Identity Key Change

| System | Current Usage | Impact of Change |
|--------|---------------|------------------|
| **De-duplication** ([gtHelpers.ts](../../../frontend/src/models/gtHelpers.ts)) | Uses URL | Must switch to chunk ID |
| **Reference Updates** ([useReferencesEditor.ts](../../../frontend/src/hooks/useReferencesEditor.ts)) | Uses `ref.id` for patch targeting | Would use chunk ID instead |
| **Export Pipeline** ([backend/app/exports/pipeline.py](../../../backend/app/exports/pipeline.py)) | Outputs refs with URL as key field | May need to include chunk ID |
| **API Ground Truth Mapping** ([groundTruths.ts](../../../frontend/src/services/groundTruths.ts#L63-L100)) | Generates sequential `ref_N` IDs | Would need to preserve chunk ID from storage |
| **Turn References Modal** ([TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx)) | Checks URL for duplicates | Would check chunk ID |
| **SelectedTab** ([SelectedTab.tsx](../../../frontend/src/components/app/ReferencesPanel/SelectedTab.tsx)) | Displays and manages by `ref.id` | Unchanged (uses existing id field) |

### 6. Gap Analysis

| Layer | Current State | Required for Chunk ID Identity |
|-------|--------------|-------------------------------|
| **Search Index** | ✅ Provides `chunk_id` | No change needed |
| **Inference Adapter** | ✅ Extracts `chunk_id` as `id` | No change needed |
| **Backend Reference Model** | ❌ No `id` field | Add optional `id` field |
| **Frontend Search Service** | ⚠️ Uses `id` if present, fallback to random | Ensure consistent propagation |
| **API Mapping** | ❌ Generates sequential IDs | Preserve chunk ID from storage |
| **De-duplication** | ❌ Uses URL | Switch to chunk ID |
| **Backend Persistence** | ❌ Doesn't store `id` | Store chunk ID in Reference |

## Recommendations

1. **Add `id` field to backend Reference model** (optional, string)
2. **Persist chunk ID** when saving references from chat/search
3. **Update de-duplication logic** to use `id` (chunk ID) instead of URL
4. **Update API mapping** to preserve stored chunk ID instead of generating sequential IDs
5. **Maintain URL as fallback** for legacy data without chunk IDs

## Files Referenced

- [backend/app/domain/models.py](../../../backend/app/domain/models.py) - Backend Reference model
- [frontend/src/models/groundTruth.ts](../../../frontend/src/models/groundTruth.ts) - Frontend Reference type
- [frontend/src/models/gtHelpers.ts](../../../frontend/src/models/gtHelpers.ts) - De-duplication logic
- [frontend/src/services/search.ts](../../../frontend/src/services/search.ts) - Search result mapping
- [frontend/src/services/groundTruths.ts](../../../frontend/src/services/groundTruths.ts) - API-to-frontend mapping
- [frontend/src/hooks/useReferencesEditor.ts](../../../frontend/src/hooks/useReferencesEditor.ts) - Reference editing hook
- [frontend/src/components/app/editor/TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx) - Turn references UI
- [frontend/src/components/app/ReferencesPanel/SelectedTab.tsx](../../../frontend/src/components/app/ReferencesPanel/SelectedTab.tsx) - Selected references UI
- [backend/app/adapters/gtc_inference_adapter.py](../../../backend/app/adapters/gtc_inference_adapter.py) - Inference adapter
- [backend/app/adapters/inference/inference.py](../../../backend/app/adapters/inference/inference.py) - Azure AI Search processing
- [backend/app/exports/pipeline.py](../../../backend/app/exports/pipeline.py) - Export pipeline
- [specs/reference-management.md](../../../specs/reference-management.md) - Reference management spec
