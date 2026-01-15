Got it—let’s talk strategy, not edits. A long “feature hook” like useGroundTruth.ts often happens when it becomes the orchestration hub for several domains (provider I/O, selection/editing, references, search, save/export, generation, undo). That’s normal during initial extraction, but you can trim it without losing cohesion.

Here’s how I’d think about right-sizing it.

Why it’s long

It owns multiple concerns: provider lifecycle, selection/current editing, QA change tracking, references CRUD + undo, search, save/versioning, export, generation.
It returns many actions, which makes the surface broad and encourages growth.
Split by concern (clean seams)

Core data + save layer
Keep: items, selectedId/current, updateQuestion/Answer, qaChanged/changeCategory, save (with state/vers. fingerprint, approval gating), toggleDeleted, export.
Move generic helpers to pure utils: dedupeReferences, canApproveCandidate (wraps refsApprovalReady).
Option: accept a provider via options (dependency injection) so the hook isn’t tied to JsonProvider/DEMO_JSON.
References editor sub-hook
useReferencesEditor(current, setCurrent)
Actions: updateReference, addReferences (dedupe), removeReferenceWithUndo (returns undo registration), openReference (just mark visited).
Benefit: isolate undo-timer logic and keep side effects in one spot.
Search sub-hook
useReferencesSearch({ getSeedQuery: () => current?.question })
State: query, searching, results
Action: runSearch
Keep selection of search results in UI (as you already do).
Generation sub-hook
useAnswerGeneration(current)
State: genBusy
Actions: generateDraftAnswer (gate check), applyGenerate
Keeps LLM integration separate (easier to swap mocks/real later).
Return shape: group logically

Instead of one flat object, return groups to reduce sprawl and keep stable identities with useMemo:
collection: items, refresh, selectedId, setSelectedId
editor: current, updateQuestion, updateAnswer, qaChanged, changeCategory, setChangeCategory
references: updateReference, addReferences, removeWithUndo, openReference
search: query, setQuery, searching, results, runSearch
save: saving, save, canApprove, toggleDeletedCurrent/Any
export: exportJson
generation: genBusy, generateDraftAnswer, applyGenerate
This makes it easier for components to pick only what they need and reduces accidental re-renders.
Performance considerations

Keep function identities stable with useCallback, but more importantly:
Memoize grouped return objects so consumers aren’t re-rendered on unrelated state.
If you later move to a Context provider, consider a selector pattern to slice state per consumer.
Testability improvements

Pure helpers:
dedupeReferences(existing, chosen)
canApproveCandidate(item) — thin wrapper over validators with any extra rules
generationGate(item) — returns {ok, reason}
These are easy to unit-test without React. The hook then becomes thin glue.
Configuration and DI

Let useGroundTruth accept options like { provider?: Provider, onError?: (err) => void }.
Default to JsonProvider(DEMO_JSON) only in demo; inject a real provider later.
Targets and scope

A good target is <200 lines per hook. With the split above:
Core ~120–180 LOC
References ~80–120 LOC (undo logic lives here)
Search ~50–80 LOC
Generation ~50–80 LOC
Low-risk migration path

Step 1: Extract pure helpers (dedupe, gates) to utils. No public API change.
Step 2: Move references/search/generation logic into sub-hooks used internally by useGroundTruth (no external API change).
Step 3: Optionally expose grouped return structure; keep backward-compat by reshaping internally so callers don’t break.
Step 4: Consider a GroundTruthProvider context only if prop drilling becomes painful.
What to keep centralized vs split

Keep save/versioning idempotency and approval gating centralized. That’s your single source of truth.
Keep UI-only concerns (like search selection, in-app preview toggle, modal visibility) outside the hook as you already do.
Keep toast orchestration outside; your “register undo” callback pattern is a good separation.
