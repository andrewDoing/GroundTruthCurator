# Modal Keyboard Handling Research

**Date:** 2025-01-22  
**Topic:** modal-keyboard-handling  
**Status:** Complete

## Key Findings Summary

| Question | Finding |
|----------|---------|
| Modal/dialog library | Custom implementation using React Portals (`createPortal`) |
| TurnReferencesModal location | [TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx) |
| Keyboard handling approach | Per-modal `onKeyDown` handlers + `useModalKeys` hook |
| Global keyboard system | Yes - `useGlobalHotkeys` and `ReferencesTabs` listeners |
| Input field handling | `stopPropagation()` pattern used inconsistently |

---

## 1. Modal/Dialog Component Library

**Finding:** The project uses a **custom modal system** built on React Portals - no third-party dialog library.

### Components

| File | Purpose |
|------|---------|
| [ModalPortal.tsx](../../../frontend/src/components/modals/ModalPortal.tsx) | Portal wrapper rendering to `#modal-root` |
| [InspectItemModal.tsx](../../../frontend/src/components/modals/InspectItemModal.tsx) | Read-only item inspection modal |
| [TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx) | Reference management modal |
| [TagsModal.tsx](../../../frontend/src/components/app/editor/TagsModal.tsx) | Tag management modal |

### Portal Target

```html
<!-- frontend/index.html:12 -->
<div id="modal-root"></div>
```

---

## 2. TurnReferencesModal Implementation

**Location:** [frontend/src/components/app/editor/TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx)

### Structure

```tsx
<ModalPortal>
  <div className="fixed inset-0 z-50 ...">           {/* Backdrop */}
    <button onClick={onClose} tabIndex={-1} />       {/* Backdrop close button */}
    <div role="dialog" aria-modal="true" ...>        {/* Dialog container */}
      {/* Header, content, footer */}
    </div>
  </div>
</ModalPortal>
```

### Current Keyboard Handling (Lines 395-400)

```tsx
onKeyDown={(e) => {
  // Allow Escape to close, but let other keys pass through
  if (e.key === "Escape") {
    e.stopPropagation();
    onClose();
  }
}}
```

### Input Field Handler (Lines 442-447)

```tsx
<input
  onKeyDown={(e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSearchSubmit();
    }
  }}
/>
```

**Issue:** Does NOT use `useModalKeys` hook or call `stopPropagation()` for the search input.

---

## 3. Global Keyboard Shortcut System

### useGlobalHotkeys Hook

**Location:** [frontend/src/hooks/useGlobalHotkeys.ts](../../../frontend/src/hooks/useGlobalHotkeys.ts)

```typescript
// Handles: Cmd/Ctrl+S (save draft), Cmd/Ctrl+Enter (approve)
// Checks isEditable before handling Enter
window.addEventListener("keydown", onKeyDown);
```

### useModalKeys Hook

**Location:** [frontend/src/hooks/useModalKeys.ts](../../../frontend/src/hooks/useModalKeys.ts)

```typescript
// Handles: Escape (close), Enter (confirm if not busy)
// Checks isEditable before handling Enter
// Used by InspectItemModal but NOT TurnReferencesModal
```

### ReferencesTabs Global Listener

**Location:** [frontend/src/components/app/ReferencesPanel/ReferencesTabs.tsx](../../../frontend/src/components/app/ReferencesPanel/ReferencesTabs.tsx#L59-L76)

```typescript
// Handles: Cmd/Ctrl+1 (search tab), Cmd/Ctrl+2 (selected tab)
// Checks isEditable before processing
window.addEventListener("keydown", onKeyDown);
```

---

## 4. Input Field Focus and Event Handling

### Pattern Analysis

| Component | Pattern | Issue |
|-----------|---------|-------|
| TagsModal | `onKeyDown={(e) => e.stopPropagation()}` on outer div | ✅ Prevents ALL key events from propagating |
| TurnReferencesModal | Only stops propagation for Escape | ⚠️ Other keys may leak to global listeners |
| InspectItemModal | Uses `useModalKeys` hook | ✅ Hook checks `isEditable` |

### TagsModal Pattern (Best Practice Found)

```tsx
<div
  onClick={(e) => e.stopPropagation()}
  onKeyDown={(e) => e.stopPropagation()}  // Blocks all keyboard events
  role="dialog"
  aria-modal="true"
>
```

### TurnReferencesModal Pattern (Current)

```tsx
<div
  onClick={(e) => e.stopPropagation()}
  onKeyDown={(e) => {
    if (e.key === "Escape") {  // Only Escape is handled
      e.stopPropagation();
      onClose();
    }
  }}
  role="dialog"
>
```

---

## 5. Potential Issues Identified

### Issue 1: Inconsistent `stopPropagation()` Usage

- **TagsModal** blocks ALL keyboard events from propagating
- **TurnReferencesModal** only blocks Escape - other keys like `Cmd+1`, `Cmd+2` may trigger `ReferencesTabs` tab switching

### Issue 2: Missing `useModalKeys` Hook

- **TurnReferencesModal** implements its own partial keyboard handling
- **InspectItemModal** uses the standardized `useModalKeys` hook
- This creates inconsistent behavior across modals

### Issue 3: Global Listener Race Conditions

Multiple global `keydown` listeners exist:
1. `useGlobalHotkeys` (save/approve)
2. `useModalKeys` (escape/enter)
3. `ReferencesTabs` (tab switching)

Each checks `isEditable` independently, but order of execution is not guaranteed.

---

## 6. Recommendations

1. **Standardize keyboard handling** - Update TurnReferencesModal to use `useModalKeys` hook
2. **Block all events on modal container** - Add `onKeyDown={(e) => e.stopPropagation()}` to prevent global listener interference
3. **Keep input-specific handlers** - Let Enter in search input trigger search, not modal close
4. **Consider event delegation** - Centralize keyboard event handling to avoid race conditions

---

## Files Referenced

- [frontend/src/components/app/editor/TurnReferencesModal.tsx](../../../frontend/src/components/app/editor/TurnReferencesModal.tsx)
- [frontend/src/components/app/editor/TagsModal.tsx](../../../frontend/src/components/app/editor/TagsModal.tsx)
- [frontend/src/components/modals/ModalPortal.tsx](../../../frontend/src/components/modals/ModalPortal.tsx)
- [frontend/src/components/modals/InspectItemModal.tsx](../../../frontend/src/components/modals/InspectItemModal.tsx)
- [frontend/src/hooks/useModalKeys.ts](../../../frontend/src/hooks/useModalKeys.ts)
- [frontend/src/hooks/useGlobalHotkeys.ts](../../../frontend/src/hooks/useGlobalHotkeys.ts)
- [frontend/src/components/app/ReferencesPanel/ReferencesTabs.tsx](../../../frontend/src/components/app/ReferencesPanel/ReferencesTabs.tsx)
- [frontend/index.html](../../../frontend/index.html) (line 12 - modal-root div)
