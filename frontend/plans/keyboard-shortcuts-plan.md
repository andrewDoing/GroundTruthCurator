# Keyboard Shortcuts and Accessible Keyboard Navigation — Initial Plan

Short overview: Add minimal, high-impact keyboard interactions where users type, pick from lists, switch tabs, navigate queues, and confirm dialogs. Focus on the search input (Enter to search), the tags dropdown (arrow keys + Enter), closing modals with Escape, quick tab switching, and queue navigation. Keep scope tight; no generic framework; ship basic, accessible behaviors first.

## Goals (do-now only)
- Enter triggers search in the Search tab input.
- Tags editor suggestions behave like a listbox: Up/Down to highlight, Enter to choose, Escape to close.
- Escape closes Generate/Export modals.
- Queue list supports Up/Down to move selection; Enter activates highlighted item.
- Shortcuts to switch right-panel tabs: Cmd/Ctrl+1 (Search), Cmd/Ctrl+2 (Selected).
- Global save shortcuts: Cmd/Ctrl+S saves draft; Cmd/Ctrl+Enter approves (when allowed).

## Out of scope (for now)
- Full roving tabindex across all interactive cards and checkboxes.
- Complex multi-select keyboard patterns in search results (we’ll keep mouse/checkbox for now).
- Cross-page/global command palette.

## Files to change
- `src/components/app/ReferencesPanel/SearchTab.tsx`
  - Add Enter-to-search on the input; optional Slash (/) or Cmd/Ctrl+K to focus later.
- `src/components/app/editor/TagsEditor.tsx`
  - Add listbox-like keyboard navigation for suggestions and basic ARIA roles/attributes.
- `src/components/modals/GenerateAnswerModal.tsx`
  - Add Escape to close; Enter triggers Generate & Apply unless busy.
- `src/components/modals/ExportModal.tsx`
  - Add Escape to close.
- `src/components/app/ReferencesPanel/ReferencesTabs.tsx`
  - Add Cmd/Ctrl+1 and Cmd/Ctrl+2 to switch tabs when panel is mounted.
- `src/components/app/QueueSidebar.tsx`
  - Add Up/Down to change highlighted/selected item; Enter to select.
- `src/demo.tsx`
  - Add global shortcuts for Save Draft (Cmd/Ctrl+S) and Approve (Cmd/Ctrl+Enter), gated by current state. Keep logic local for now.

Optional small helpers (if it stays simple):
- `src/hooks/useModalKeys.ts` — attach Escape handler while open.
- `src/hooks/useGlobalHotkeys.ts` — attach page-level Cmd/Ctrl+S and Cmd/Ctrl+Enter, with guards.
- `src/hooks/useListboxNav.ts` — tiny internal hook for TagsEditor only; don’t generalize broadly yet.

## Implementation details (minimal, practical)

### 1) Search input: Enter to search
- File: `SearchTab.tsx`
- Behavior: If input is focused and Enter is pressed, call `onRunSearch()` unless already `searching`.
- Guard: Trim empty queries to avoid no-op searches.
- Accessibility: Keep default input semantics; no ARIA changes required.

Functions:
- handleSearchInputKeyDown(e)
  - If e.key === "Enter" and query.trim() and not searching, prevent default and call onRunSearch().

### 2) Tags suggestions: Arrow keys + Enter + Escape
- File: `TagsEditor.tsx`
- Behavior: When suggestions panel is open, Up/Down moves an internal `activeIndex`; Enter selects the active suggestion; Escape closes suggestions (and clears activeIndex). When input is empty and Backspace is pressed, remove the last chip/tag.
- Accessibility: Add `role="combobox"` to input container, `aria-expanded`, `aria-controls`; set suggestions container `role="listbox"` and each option `role="option"` with `aria-selected` based on `activeIndex`. Use `id` + `aria-activedescendant` to tie input to the active option.

Functions:
- handleTagsKeyDown(e)
  - Up/Down: update activeIndex within bounds; ensure the option is scrolled into view.
  - Enter: if createLabel is shown and activeIndex === -1, add(q.trim()); else add(suggestions[activeIndex]).
  - Escape: setOpen(false), reset activeIndex.
  - Backspace (when q is empty): remove last selected tag.
- getOptionId(i)
  - Returns deterministic id string for aria-activedescendant reference.

### 3) Modals: Escape to close (and Enter to confirm for Generate)
- Files: `GenerateAnswerModal.tsx`, `ExportModal.tsx`
- Behavior: When modal is open, pressing Escape calls onCancel/onClose. In Generate modal, Enter acts as primary action (Generate & Apply) if not busy and focus is not within textarea or other text inputs.
- Implementation: Add `useEffect` that attaches a keydown listener on mount and cleans up on unmount; ignore if event originated from an editable element for Escape-optional, but generally Escape should always close.

Functions:
- useModalKeys({ onClose, onConfirm? })
  - Attaches keydown: Escape -> onClose(); Enter -> onConfirm() when appropriate.

### 4) Right panel tabs: Cmd/Ctrl+1 and Cmd/Ctrl+2
- File: `ReferencesTabs.tsx`
- Behavior: When the right panel is mounted, listen for Cmd/Ctrl+1 to setRightTab("search") and Cmd/Ctrl+2 to setRightTab("selected").
- Guard: Skip when the user is typing in an input/textarea/contenteditable.

Functions:
- useTabHotkeys({ setRightTab })
  - Global keydown handler mapping modifiers to tab changes.

### 5) Queue navigation: Up/Down + Enter
- File: `QueueSidebar.tsx`
- Behavior: When the Queue sidebar has focus (e.g., tabbed into it) or its list container is active, Up/Down moves a local `hoverIndex` across items and visually highlights it; Enter selects the highlighted item (calls onSelect(id)). Prefer not to disturb current selected unless user presses Enter.
- Accessibility: Make the scrollable list container focusable with `tabIndex={0}`; use `aria-activedescendant` to indicate the active item; each item gets an id.

Functions:
- handleQueueKeyDown(e)
  - ArrowUp/ArrowDown: clamp and update hoverIndex; scroll into view.
  - Enter: onSelect(items[hoverIndex].id).
- getItemId(i)
  - Returns deterministic id string for aria-activedescendant reference.

### 6) Global save/approve shortcuts
- File: `demo.tsx`
- Behavior: Cmd/Ctrl+S calls save draft action; Cmd/Ctrl+Enter calls approve action (only when `canApprove` is true and not saving/deleted). Ignore when focus is in an editable control (input, textarea, contenteditable) to avoid hijacking typing; still allow Cmd/Ctrl+S within editors as many apps do—here we’ll keep it global but prevent default to stop browser Save dialog.

Functions:
- useGlobalHotkeys({ onSaveDraft, onApprove, canApprove, disabled? })
  - keydown handler: metaKey|ctrlKey + S -> onSaveDraft(); metaKey|ctrlKey + Enter -> onApprove() if allowed.

## Edge cases and guards
- Don’t trigger actions while `searching` or `busy` (disable Enter confirm in Generate modal when busy).
- When suggestions are empty, Enter in TagsEditor should create when allowed; otherwise no-op.
- Modifier keys differ by OS: treat Ctrl on Windows/Linux and Meta on macOS equally.
- Avoid global shortcuts when a native control should keep them (e.g., typing inside a textarea for Enter in Generate modal).
- Keep scroll-into-view polite; only when the highlighted item is outside the viewport.

## Tests (Playwright e2e)
- search.enter-triggers-search
  - Press Enter in search input triggers fetch and renders results.
- tags.arrow-navigate-and-enter-selects
  - Up/Down highlights option; Enter adds tag; Escape closes.
- tags.backspace-removes-last-when-empty
  - Backspace on empty input removes last chip.
- modal.generate.escape-closes-and-enter-confirms
  - Escape closes; Enter triggers generate when not busy.
- modal.export.escape-closes
  - Escape closes export modal.
- tabs.cmd-1-2-switches-panels
  - Cmd/Ctrl+1 selects Search; +2 selects Selected.
- queue.arrows-move-and-enter-selects
  - Up/Down changes highlight; Enter selects item and loads it.
- save.cmd-s-saves-draft
  - Cmd/Ctrl+S triggers save draft and shows success toast.
- approve.cmd-enter-approves-when-allowed
  - Cmd/Ctrl+Enter approves when canApprove; otherwise ignored.

## Minimal success criteria
- Users can perform a search without clicking Search: Enter works.
- Tags can be selected from suggestions using only the keyboard.
- Modals are dismissible with Escape; Generate primary action can be confirmed with Enter.
- Queue can be navigated by keyboard to select an item.
- Common shortcuts (save/approve, tab-switching) work and don’t conflict with typing.

## Rollout notes
- Keep all behavior behind straightforward, inline key handlers or tiny hooks living next to the component.
- Do not introduce external dependencies.
- If any shortcut feels surprising in manual testing, prefer disabling it rather than adding configuration.
