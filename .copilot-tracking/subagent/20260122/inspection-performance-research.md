# Inspection Performance Research

**Date:** 2026-01-22
**Topic:** Caching and memoization patterns for inspection modals

## 1. InspectItemModal Implementation

**Location:** [frontend/src/components/modals/InspectItemModal.tsx](frontend/src/components/modals/InspectItemModal.tsx)

### Data Fetching Pattern

The `InspectItemModal` component fetches complete item data on every open:

```tsx
// Lines 62-111
useEffect(() => {
  if (!isOpen || !item) {
    setCompleteItem(null);
    setLoadError(null);
    return;
  }

  // Always fetch fresh data to ensure we get complete conversation history
  setIsLoading(true);
  setLoadError(null);

  (async () => {
    const completeItemData = await getGroundTruth(
      item.datasetName || "",
      item.bucket || "",
      item.id,
    );
    setCompleteItem(completeItemData);
  })()
}, [isOpen, item]);
```

### Data Fetched

- Complete `GroundTruthItem` via `getGroundTruth()` API call
- Runtime configuration for trusted reference domains
- Uses `MultiTurnEditor` component in read-only mode to display conversation

### Performance Issue

**No caching of previously viewed items.** Each time the modal opens for the same item, a fresh API call is made. The comment explicitly states "Always fetch fresh data" but this is unnecessary for recently viewed items in a read-only context.

## 2. TurnReferencesModal Implementation

**Location:** [frontend/src/components/app/editor/TurnReferencesModal.tsx](frontend/src/components/app/editor/TurnReferencesModal.tsx)

### References Computation

The modal filters references for a specific turn on every render:

```tsx
// Line 88 - computed on every render
const turnRefs = references.filter((r) => r.messageIndex === messageIndex);
```

Additional computed values on every render:
```tsx
// Line 91 - set computed on every render
const urlsInTurn = new Set(turnRefs.map((r) => normalizeUrl(r.url)));
```

### Performance Issue

**No memoization for references filtering.** The `turnRefs` filter and `urlsInTurn` Set are recomputed on every render, even when `references` and `messageIndex` haven't changed.

## 3. Existing Caching Patterns

### Service-Level Caching

| Service | Caching Pattern | TTL |
|---------|-----------------|-----|
| [datasets.ts](frontend/src/services/datasets.ts) | In-memory cache with TTL | 5 minutes |
| [runtimeConfig.ts](frontend/src/services/runtimeConfig.ts) | Single-fetch cache (permanent) | Forever |

**datasets.ts example:**
```typescript
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
let datasetsCache: { data: string[] | null; timestamp: number } = {
  data: null,
  timestamp: 0,
};
```

**runtimeConfig.ts example:**
```typescript
let cachedConfig: RuntimeConfig | null = null;
let configPromise: Promise<RuntimeConfig> | null = null;

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  if (cachedConfig) return cachedConfig;
  if (configPromise) return configPromise;
  // ... fetch and cache
}
```

### No Ground Truth Item Caching

The `groundTruths.ts` service has **no caching mechanism** for individual items. Each `getGroundTruth()` call makes a fresh API request.

## 4. React Query / Data Fetching Library Status

**React Query is NOT currently in use.**

The `package.json` shows no `@tanstack/query` or `react-query` dependency:

```json
"dependencies": {
  "@microsoft/applicationinsights-web": "^3.0.4",
  "openapi-fetch": "^0.9.8",
  "react": "^19.1.1",
  // ... no react-query
}
```

The reference in [connecting-e2e-best-practices.md](frontend/docs/connecting-e2e-best-practices.md) is documentation/guidance, not actual implementation.

**Current data fetching approach:**
- Direct `fetch()` calls via `openapi-fetch` client
- Manual state management with `useState`/`useEffect`
- No automatic caching, deduplication, or stale-while-revalidate patterns

## 5. Existing Memoization Patterns

### useCallback Usage

Found in multiple hooks:

| File | Pattern |
|------|---------|
| [useReferencesSearch.ts](frontend/src/hooks/useReferencesSearch.ts) | `runSearch`, `clearResults` wrapped in `useCallback` |
| [useTags.ts](frontend/src/hooks/useTags.ts) | `refresh`, `ensureTag`, `filter` wrapped in `useCallback` |
| [useToasts.ts](frontend/src/hooks/useToasts.ts) | `dismiss`, `clear`, `showToast` wrapped in `useCallback` |
| [useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts) | Extensive `useCallback` usage for all actions |

### useMemo Usage

Found in components:

| File | Pattern |
|------|---------|
| [QueueSidebar.tsx](frontend/src/components/app/QueueSidebar.tsx) | `ids` memoized |
| [QuestionsExplorer.tsx](frontend/src/components/app/QuestionsExplorer.tsx) | `hasUnappliedChanges`, `displayItems` memoized |
| [TagsEditor.tsx](frontend/src/components/app/editor/TagsEditor.tsx) | `suggestions` memoized |
| [InstructionsPane.tsx](frontend/src/components/app/InstructionsPane.tsx) | Memoization used |
| [useGroundTruth.ts](frontend/src/hooks/useGroundTruth.ts) | `qaChanged`, `canApprove`, `hasUnsaved` memoized |

### Gaps in Memoization

**InspectItemModal:** No `useMemo` or `useCallback` hooks used
**TurnReferencesModal:** No `useMemo` for `turnRefs` or `urlsInTurn` computations

## 6. Recommendations

### Immediate Optimizations

1. **Add item cache to InspectItemModal:**
   - Implement LRU cache for recently viewed items
   - Cache key: `${datasetName}:${bucket}:${id}`
   - Suggested TTL: 2-5 minutes or LRU with 10-20 item limit

2. **Memoize TurnReferencesModal computations:**
   ```tsx
   const turnRefs = useMemo(
     () => references.filter((r) => r.messageIndex === messageIndex),
     [references, messageIndex]
   );
   
   const urlsInTurn = useMemo(
     () => new Set(turnRefs.map((r) => normalizeUrl(r.url))),
     [turnRefs]
   );
   ```

### Medium-Term Improvements

3. **Service-level item caching:**
   - Add caching to `groundTruths.ts` similar to `datasets.ts` pattern
   - Consider cache invalidation on save operations

4. **Consider React Query adoption:**
   - Provides automatic caching, deduplication, background refetch
   - Simpler code for cache management
   - Already documented in best practices

## Summary

| Component | Issue | Severity |
|-----------|-------|----------|
| InspectItemModal | No item caching - fetches on every open | High |
| TurnReferencesModal | No memoization for references filter | Medium |
| groundTruths.ts | No service-level item cache | Medium |
| Overall | No React Query adoption | Low |
