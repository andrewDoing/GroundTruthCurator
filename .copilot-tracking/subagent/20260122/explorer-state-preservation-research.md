# Explorer State Preservation Research

**Research Date:** 2026-01-22
**Related Issue:** SA-364 - GTC Explorer: Assign from explorer switches to curation view, losing filters

---

## 1. Current Explorer Component Structure

### Primary Component
- **File:** [src/components/app/QuestionsExplorer.tsx](../../../frontend/src/components/app/QuestionsExplorer.tsx)
- **Type:** Functional component with internal state management
- **Purpose:** Displays ground truth items in a filterable, sortable table with actions (Assign, Inspect, Delete)

### Component Hierarchy
```
App.tsx
└── GTAppDemo (demo.tsx)
    ├── AppHeader
    ├── QuestionsExplorer (viewMode === "questions")
    ├── CuratePane (viewMode === "curate")
    └── StatsPage (viewMode === "stats")
```

### Key Interfaces

```typescript
interface FilterState {
  status: FilterType;      // "all" | "draft" | "approved" | "skipped" | "deleted"
  dataset: string;         // dataset name or "all"
  tags: string[];          // array of selected tags (AND logic)
  itemId: string;          // item ID filter text
  refUrl: string;          // reference URL filter text
  sortColumn: SortColumn;  // "refs" | "reviewedAt" | "hasAnswer" | null
  sortDirection: SortDirection; // "asc" | "desc"
}
```

---

## 2. Filter State Management Analysis

### Current Implementation: Local Component State

All filter state is managed via `useState` hooks **inside** `QuestionsExplorer`:

```typescript
// Filter state (unapplied - UI inputs)
const [activeFilter, setActiveFilter] = useState<FilterType>("all");
const [selectedDataset, setSelectedDataset] = useState<string>("all");
const [selectedTags, setSelectedTags] = useState<string[]>([]);
const [itemIdFilter, setItemIdFilter] = useState<string>("");
const [referenceUrlFilter, setReferenceUrlFilter] = useState<string>("");
const [sortColumn, setSortColumn] = useState<SortColumn>(null);
const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
const [itemsPerPage, setItemsPerPage] = useState(25);

// Applied filter state (what was last sent to backend)
const [appliedFilter, setAppliedFilter] = useState<FilterState>({...});
const [currentPage, setCurrentPage] = useState(1);
```

### Two-Phase Filter Pattern
1. **Unapplied state:** User modifies filters in UI
2. **Applied state:** User clicks "Apply Filters" button to execute query
3. `hasUnappliedChanges` computed via `useMemo` to track dirty state

### Problems with Current Approach
- **No state lifting:** Filter state is entirely local to `QuestionsExplorer`
- **No persistence:** When component unmounts (view switch), all state is lost
- **No URL sync:** Filters are not reflected in URL params
- **No context provider:** No shared state mechanism across views

---

## 3. Navigation Actions That Cause State Loss

### Identified Navigation Triggers

| Action | Code Location | Effect |
|--------|--------------|--------|
| **Assign button** | `demo.tsx:207-229` | Calls `assignItem()`, then `setViewMode("curate")` |
| **Header toggle** | `AppHeader.tsx:48-56` | Toggles between "curate" and "questions" |
| **Stats button** | `AppHeader.tsx:57-64` | Sets `viewMode` to "stats" |

### Critical Code Path (Assign Action)

```typescript
// demo.tsx lines 207-229
onAssign={async (item) => {
  // ...validation...
  await assignItem(item.datasetName, item.bucket, item.id);
  await gt.refreshList();
  await gt.selectItem(item.id);
  setViewMode("curate");  // <-- CAUSES UNMOUNT OF QuestionsExplorer
  toast("success", `Assigned ${item.id} for curation`);
}}
```

**Root cause:** `setViewMode("curate")` triggers React to unmount `QuestionsExplorer` and mount `CuratePane`, destroying all local filter state.

---

## 4. State Persistence Mechanisms

### Current State: **None implemented**

#### localStorage
- **Usage:** Commented out in `CuratePane.tsx` (line 163)
- **Status:** Not active for any feature

#### URL State / Query Parameters
- **Routing library:** **None** - app uses simple `viewMode` state switching
- **URL params:** Not used for any state persistence
- **`package.json`:** No `react-router`, `@tanstack/router`, or similar

#### Context API
- **Existing contexts:** None for filter/view state
- **Pattern:** App uses prop drilling from `GTAppDemo` to children

#### Session/Browser APIs
- `sessionStorage`: Not used
- `history.pushState/replaceState`: Not used

---

## 5. Routing Architecture

### Current Implementation: **No Routing Library**

The application uses a simple state-based view switching pattern:

```typescript
// demo.tsx
const [viewMode, setViewMode] = useState<"curate" | "questions" | "stats">("curate");

// Conditional rendering
{viewMode === "stats" && <StatsPage ... />}
{viewMode === "questions" && <QuestionsExplorer ... />}
{viewMode === "curate" && <CuratePane ... />}
```

### Implications
- No URL-based navigation
- No browser back/forward support
- No deep linking capability
- No route-based code splitting

---

## 6. Summary & Recommendations

### Key Findings

| Finding | Status | Impact |
|---------|--------|--------|
| Filter state is local to component | ✅ Confirmed | State lost on unmount |
| No routing library | ✅ Confirmed | No URL-based persistence |
| No localStorage usage | ✅ Confirmed | No browser persistence |
| No Context for filters | ✅ Confirmed | No cross-view sharing |
| Assign triggers view switch | ✅ Confirmed | Direct cause of SA-364 |

### Recommended Solutions (Priority Order)

#### Option A: Lift State to Parent (Minimal Change)
- Move `FilterState` to `GTAppDemo`
- Pass as props to `QuestionsExplorer`
- State survives view switches
- **Effort:** Low | **Risk:** Low

#### Option B: URL Query Parameters (Better UX)
- Sync filter state to URL search params
- Use `URLSearchParams` API directly (no router needed)
- Enables deep linking and back/forward
- **Effort:** Medium | **Risk:** Low

#### Option C: Context + localStorage (Full Persistence)
- Create `ExplorerFilterContext`
- Persist to localStorage on change
- Restore on mount
- **Effort:** Medium | **Risk:** Low

#### Option D: Add React Router (Future-Proof)
- Integrate routing library
- Route-based view switching
- URL state via loader/search params
- **Effort:** High | **Risk:** Medium

### Alternative Quick Fix
Per SA-364 proposed solution #1:
> "Do not automatically switch to the curation view when making an assignment from the explorer"

This would involve removing `setViewMode("curate")` from the assign handler, keeping user in Explorer after assignment. However, this may not match desired UX if user wants to immediately curate the assigned item.

---

## Files Referenced

- [frontend/src/demo.tsx](../../../frontend/src/demo.tsx) - Main app container
- [frontend/src/components/app/QuestionsExplorer.tsx](../../../frontend/src/components/app/QuestionsExplorer.tsx) - Explorer component
- [frontend/src/components/app/AppHeader.tsx](../../../frontend/src/components/app/AppHeader.tsx) - Navigation header
- [frontend/package.json](../../../frontend/package.json) - Dependencies
- [prd-refined-2.json](../../../prd-refined-2.json) - Issue SA-364 definition
