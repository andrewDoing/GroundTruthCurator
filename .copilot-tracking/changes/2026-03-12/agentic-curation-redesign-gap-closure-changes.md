<!-- markdownlint-disable-file -->
# Release Changes: Agentic Curation Redesign Gap Closure

**Related Plan**: agentic-curation-redesign-gap-closure-plan.instructions.md
**Implementation Date**: 2026-03-12

## Summary

Phase 1 establishes foundational contracts and interfaces for the agentic curation redesign gap closure: frontend plugin component registry type definitions, expanded backend PluginPack extension surfaces, a per-tool-call RetrievalCandidate model, and a wireframe-to-schema field name mapping reference.

Phase 2 implements the frontend field component registry: a discriminator-based singleton registry with exact and prefix matching, three fallback renderers (KVDict, JSON, CodeBlock), a PluginErrorBoundary for runtime isolation, and a RegistryRenderer wrapper that ties resolution, fallback selection, and error handling together. Includes 18 unit tests.

Phase 3 implements workspace UX parity: the CSS grid layout is replaced with a resizable split-pane (react-resizable-panels) with a draggable gutter and localStorage persistence; mobile viewports get a slide-in evidence drawer; and context entries in TracePanel become editable with add/edit/remove operations wired through useGroundTruth.

## Changes

### Added

* frontend/src/registry/types.ts - TypeScript interfaces for the field component registry: RenderContext, ViewerProps, EditorProps, ComponentRegistration, FieldComponentRegistryAPI
* frontend/src/registry/index.ts - Public barrel export for registry types
* frontend/src/models/groundTruth.ts - RetrievalCandidate type for per-tool-call retrieval state with raw payload preservation
* backend/app/domain/models.py - RetrievalCandidate Pydantic model with url/title/chunk/raw_payload/relevance/tool_call_id fields and validators
* backend/app/plugins/base.py - ExplorerFieldDefinition, ImportTransform, ExportTransform dataclasses for plugin extension surfaces
* backend/app/plugins/base.py - PluginPack.get_stats_contribution(), get_explorer_fields(), get_import_transforms(), get_export_transforms() abstract methods with no-op defaults
* backend/app/plugins/base.py - PluginPackRegistry.collect_stats(), collect_explorer_fields(), collect_import_transforms(), collect_export_transforms() aggregation methods
* .copilot-tracking/research/2026-03-12/wireframe-schema-field-mapping.md - Wireframe-to-schema field name mapping reference document
* frontend/src/registry/FieldComponentRegistry.ts - Singleton registry with discriminator-based resolution (exact + prefix matching), dev-mode duplicate warnings, and reset for testing
* frontend/src/registry/PluginErrorBoundary.tsx - React class error boundary that catches plugin-contributed component errors and renders a fallback
* frontend/src/registry/RegistryRenderer.tsx - Wrapper that resolves from registry, selects fallback by data shape, and wraps in PluginErrorBoundary
* frontend/src/registry/fallbacks/KVDictFallback.tsx - Key-value pair fallback renderer for Record<string, unknown> data
* frontend/src/registry/fallbacks/JsonFallback.tsx - Formatted JSON fallback renderer with collapse/expand for large payloads
* frontend/src/registry/fallbacks/CodeBlockFallback.tsx - Code block fallback renderer for string data
* frontend/src/registry/fallbacks/index.ts - Barrel export for fallback components
* frontend/tests/unit/registry/FieldComponentRegistry.test.tsx - 12 tests: exact/prefix resolution, duplicate warnings, has, registrations, reset
* frontend/tests/unit/registry/RegistryRenderer.test.tsx - 6 tests: fallback rendering by data shape, registered component rendering, error boundary recovery
* frontend/src/components/app/layout/SplitPaneLayout.tsx - Resizable split-pane wrapper using react-resizable-panels (Group/Panel/Separator) with localStorage persistence
* frontend/src/components/app/layout/EvidenceDrawer.tsx - Slide-in drawer for mobile viewports with backdrop, outside-click dismiss, and Escape key handling
* frontend/src/components/app/editors/ContextEntryEditor.tsx - Editable context entry list with inline key/value editing, add, and remove operations

### Modified

* frontend/src/registry/index.ts - Expanded barrel to re-export FieldComponentRegistry, fieldComponentRegistry, fallbacks, PluginErrorBoundary, RegistryRenderer
* frontend/src/demo.tsx - Replaced CSS grid curate layout with resizable SplitPaneLayout (large screens) and EvidenceDrawer (mobile); added react-resizable-panels and drawer imports; removed cn import (unused after grid removal)
* frontend/src/components/app/TracePanel.tsx - Added optional onUpdateContextEntries prop; context entries section now renders ContextEntryEditor when handler is provided; imports ContextEntryEditor
* frontend/src/components/app/pages/ReferencesSection.tsx - Added onUpdateContextEntries prop pass-through to TracePanel; imported ContextEntry type
* frontend/src/hooks/useGroundTruth.ts - Added updateContextEntries callback and ContextEntry import; exposed in UseGroundTruth type and return object
* frontend/package.json - Added react-resizable-panels dependency

#### Phase 4: Tool-Call Decision Editing

### Added

* frontend/src/components/app/editors/ToolCallDetailView.tsx - Expanded tool-call view with collapsible arguments and response sections using CodeBlockFallback, parallelGroup visual indicator
* frontend/src/components/app/editors/ToolNecessityEditor.tsx - Tri-state toggle editor for tool necessity classification (required/optional/not-needed) per tool name
* frontend/tests/unit/components/app/editors/ToolNecessityEditor.test.tsx - 7 unit tests: row rendering, state display, toggling, empty state, tool preservation

### Modified

* frontend/src/models/groundTruth.ts - Added `arguments?: Record<string, unknown>` field to ToolCallRecord type
* frontend/src/models/gtHelpers.ts - Added `canBypassRequiredToolsCheck()` helper; `canApproveMultiTurn` now requires ≥1 required tool unless plugin declares bypass
* frontend/src/components/app/TracePanel.tsx - Replaced inline ToolCallEntry with ToolCallDetailView; added `onUpdateExpectedTools` prop; ExpectedToolsSection now renders ToolNecessityEditor when handler provided; imports ExpectedTools type
* frontend/src/components/app/pages/ReferencesSection.tsx - Added `onUpdateExpectedTools` prop pass-through to TracePanel; imports ExpectedTools type
* frontend/src/hooks/useGroundTruth.ts - Added `updateExpectedTools` callback and ExpectedTools import; exposed in UseGroundTruth type and return object
* frontend/src/demo.tsx - Wired `onUpdateExpectedTools={gt.updateExpectedTools}` to both ReferencesSection usages (desktop and mobile drawer)
* frontend/tests/unit/models/gtHelpers.expectedBehavior.test.ts - Updated tests for ≥1 required tool gate: baseItem now includes required tools; added plugin bypass and strictness tests (13 tests total in file)

### Removed

* (none)

#### Phase 5: Backend Compatibility Migration

### Added

* backend/tests/unit/test_rag_compat_approval.py - 10 tests: core strict assistant-message check, RagCompatPack waiver for assistant-message and required-tools errors, registry-level waiver filtering, backward compat with legacy q/a items
* backend/tests/unit/test_plugin_pack_extension.py - 13 tests: default no-op extension surface behavior, stats aggregation and merge, explorer field collection with pack_name, import/export transform aggregation
* backend/tests/unit/test_search_raw_payload.py - 6 tests: raw_payload included in search results, contains full provider response, independent copy, configurable field names with raw_payload
* backend/tests/unit/test_validation_required_tools.py - 8 tests: required-tool enforcement when tool calls present, RagCompatPack waiver for retrieval items, properly classified tools pass

### Modified

* backend/app/plugins/base.py - Added `collect_approval_waivers()` to PluginPack (default returns []) and `collect_approval_waivers()`, `filter_core_errors()` to PluginPackRegistry for waiver aggregation and filtering
* backend/app/services/validation_service.py - Removed RAG-specific `and item.totalReferences == 0` waiver from core approval check; `validate_item_for_approval()` now calls `filter_core_errors()` before adding pack errors
* backend/app/plugins/packs/rag_compat.py - Added `collect_approval_waivers()` that waives assistant-message and required-tools core errors when `totalReferences > 0`
* backend/app/services/search_service.py - Added `raw_payload: dict[str, Any]` to `SearchResult` TypedDict; `query()` now preserves full provider hit in each result
* backend/app/api/v1/stats.py - Stats endpoint now uses `plugin_pack_registry.collect_stats(base_stats.model_dump())` for plugin-extensible stats
* backend/tests/unit/test_phase1_rework.py - Added `filter_core_errors` mock to plugin-pack registry mock in bulk import approval test (required by new waiver filtering step)

#### Phase 6: Retrieval Normalization

### Added

* backend/tests/unit/test_retrieval_per_call.py - 14 tests: per-tool-call retrieval state CRUD (get/set retrievals and candidates), migration from top-level refs to per-call state with stepNumber→toolCallId association, flat candidate extraction, unassociated ref handling
* frontend/src/registry/ExplorerExtensions.ts - Explorer extension types (ExplorerColumnExtension, ExplorerFilterExtension, ExplorerExtension) and module-level registry with register/get/reset helpers; built-in RAG compat "Refs" column and "Has References" filter auto-registered on import

### Modified

* backend/app/plugins/packs/rag_compat.py - Added per-tool-call retrieval methods: get_retrievals(), get_retrieval_candidates(), set_retrieval_candidates(), set_retrievals(), has_per_call_state(), get_all_candidates_flat(), migrate_refs_to_per_call(); added _UNASSOCIATED_KEY constant
* frontend/src/models/groundTruth.ts - Removed `references: Reference[]` from GroundTruthItem; added `toolCallId?: string` to Reference type; added RetrievalBucket/RetrievalsMap types; added getItemReferences(), withUpdatedReferences(), getRetrievalsMap() helper functions
* frontend/src/adapters/apiMapper.ts - groundTruthFromApi() now populates per-call plugin state (rag-compat retrievals) instead of top-level references; groundTruthToPatch() reads from per-call state via getItemReferencesFromPlugins() and writes plugins to patch body; added RetrievalBucket/RetrievalsMap/internal helper types
* frontend/src/hooks/useReferencesEditor.ts - All reference mutations (toggle, approve, remove, reorder, add) now use getItemReferences()/withUpdatedReferences() instead of direct prev.references access
* frontend/src/hooks/useGroundTruth.ts - stateSignature, save merge, selectedRefCount, deleteTurn, appendAgentTurn, regenerateAgentTurn all updated to use getItemReferences()/withUpdatedReferences()
* frontend/src/demo.tsx - Two references= prop usages updated to getItemReferences()
* frontend/src/components/app/pages/CuratePane.tsx - Four .references reads replaced with getItemReferences()
* frontend/src/components/app/editor/MultiTurnEditor.tsx - Reference extraction uses getItemReferences()
* frontend/src/models/gtHelpers.ts - canApproveCandidate uses getItemReferences()
* frontend/src/models/validators.ts - refsApprovalReady uses getItemReferences()
* frontend/src/models/demoData.ts - Demo data uses per-call plugin state format instead of top-level references
* frontend/src/dev/self-tests.ts - Test fixture mk() puts refs in per-call plugin state
* frontend/src/components/app/QuestionsExplorer.tsx - Imports and renders plugin-contributed explorer columns from getExplorerExtensions() registry in table headers and row cells
* frontend/src/components/app/QuestionsExplorer.example.tsx - Removed 50 references properties from example data
* frontend/src/registry/index.ts - Re-exports ExplorerExtensions types and functions
* frontend/tests/unit/adapters/apiMapper.test.ts - Assertions use getItemReferences() for per-call state
* frontend/tests/unit/hooks/useGroundTruth-deleteTurn.test.tsx - Refs in plugin state format + getItemReferences() for assertions
* frontend/tests/unit/components/app/pages/ReferencesSection.test.tsx - Refs moved to per-call plugin state
* frontend/tests/unit/components/app/pages/CuratePane.test.tsx - Removed references: [] from test data
* frontend/tests/unit/components/app/pages/QuestionsList.test.tsx - Removed references: [] from test data
* frontend/tests/unit/components/app/CurateLayout.integration.test.tsx - Removed references: []
* frontend/tests/unit/components/app/QuestionsExplorer.test.tsx - Removed references: []
* ~9 additional test files updated to use per-call plugin state format

### Removed

* frontend/src/models/groundTruth.ts - `references: Reference[]` field removed from GroundTruthItem type

## Additional or Deviating Changes

* No deviations from the implementation details.
* Test files placed in `frontend/tests/unit/registry/` (matching vitest config include pattern) rather than `frontend/src/registry/__tests__/` as listed in the details file.
* Phase 3: Used `react-resizable-panels` (v1.x with Group/Panel/Separator API) instead of allotment — smaller bundle, maintained by bvaughn. The API uses `orientation` instead of `direction`, `Group` instead of `PanelGroup`, and `Separator` instead of `PanelResizeHandle`.
* Phase 3: ContextEntryEditor uses `useRef` + `useEffect` for focus instead of `autoFocus` attribute to satisfy Biome accessibility lint rule (`noAutofocus`).
* Phase 3: The implementation details suggested `editors/` (plural) for ContextEntryEditor path; this differs from the existing `editor/` (singular) directory. Both directories now exist.
* Phase 4: ToolCallDetailView placed in `editors/` directory alongside existing ContextEntryEditor, not as a standalone component in `components/app/`.
* Phase 4: ToolNecessityEditor test file placed in `frontend/tests/unit/components/app/editors/` (matching vitest include pattern) rather than `frontend/src/components/app/editors/__tests__/`.
* Phase 4: Backend tests for approval strictness (test_validation_required_tools.py) deferred to Phase 5 when the backend required-tool enforcement is added.
* Phase 4: Plugin bypass uses `data.canBypassRequiredTools: true` in any plugin payload rather than a separate registration mechanism — matches the existing plugin data model and avoids premature abstraction.
* Phase 5 Step 5.1: RAG waiver migration uses a `collect_approval_waivers()` pattern — packs return exact core error strings to suppress. `filter_core_errors()` on the registry applies waivers as a set-difference filter. This is more general than the details' "exemption hook" approach and allows any pack to waive any core error.
* Phase 5 Step 5.2: Extension surfaces (stats, explorer, import/export hooks) were already fully implemented in Phase 1. The dataclasses remain in `base.py` rather than `domain/models.py` — consistent with Phase 1 placement and avoids unnecessary churn.
* Phase 5 Step 5.4: `container.repo.stats()` returns a `Stats` Pydantic model, not a dict. Used `.model_dump()` before passing to `collect_stats()` to match the `dict[str, Any]` signature.
* Phase 5: Updated `test_phase1_rework.py` mock to include `filter_core_errors` since the new waiver step in `validate_item_for_approval()` calls it on the registry mock.
* Phase 6: ExplorerExtensions.ts is a module-level singleton with self-registering built-in RAG compat extension, rather than a class-based registry. The RAG "Refs" column and "Has References" filter are auto-registered on import.
* Phase 6: Per-call retrieval state stores additional candidate fields (keyParagraph, bonus, visitedAt) beyond the minimal url/title/chunk — preserves full fidelity during legacy migration.
* Phase 6: `withUpdatedReferences()` re-organizes references into per-call buckets by toolCallId, with unassociated refs going to the `_unassociated` bucket.

## Release Summary

Phase 1 (Contract & Interface Stabilization) complete. 5 files created, 2 files modified. All validation gates pass: ruff, ty, tsc, Biome. api:types regeneration confirmed no OpenAPI drift.

Phase 2 (Frontend Component Registry) complete. 9 files created, 1 file modified. All validation gates pass: tsc, Biome lint (131 files checked), 288/288 tests passing (38 test files, 18 new registry tests).

Phase 3 (Workspace UX Parity) complete. 3 files created, 6 files modified. All validation gates pass: tsc, Biome lint (134 files checked), 288/288 tests passing (38 test files). New dependency: react-resizable-panels.

Phase 4 (Tool-Call Decision Editing) complete. 3 files created, 7 files modified. All validation gates pass: tsc, Biome lint (137 files checked), 297/297 tests passing (39 test files, 7 new ToolNecessityEditor tests + 2 approval strictness tests).

Phase 5 (Backend Compatibility Migration) complete. 4 files created, 6 files modified. All validation gates pass: ruff, ty, 380/380 backend tests passing, tsc, api:types regeneration confirmed clean. RAG approval waiver migrated from core validation_service into RagCompatPack via collect_approval_waivers(). Search results now include raw_payload. Stats endpoint is plugin-extensible. 37 new backend unit tests added across 4 test files.

Phase 6 (Retrieval Normalization) complete. 2 files created, ~25 files modified. Removed top-level `references` from GroundTruthItem; all reference I/O now flows through per-tool-call plugin state in `plugins["rag-compat"].data.retrievals`. Added getItemReferences()/withUpdatedReferences() helpers; updated all 10+ consumer files. Backend RagCompatPack gained per-call CRUD and migration methods (14 new tests). Frontend ExplorerExtensions registry added with RAG "Refs" column and "Has References" filter. All validation gates pass: ruff, ty, 394/394 backend tests, tsc, Biome (138 files), 297/297 frontend tests.
