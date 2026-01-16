<!-- markdownlint-disable-file -->
# Release Changes: Export pipeline design

**Related Plan**: 20260116-export-pipeline-design-plan.instructions.md
**Implementation Date**: 2026-01-16

## Summary

Planned updates for the export pipeline design implementation.

## Changes

### Added

### Modified

* docs/computed-tags-design.md - Documented the snapshot export baseline contract for pipeline compatibility.
* docs/computed-tags-design.md - Defined the v1 export pipeline API surface and defaults.
* docs/computed-tags-design.md - Updated the pipeline entry point to reuse the snapshot POST route.
* docs/computed-tags-design.md - Added processor and formatter interface rules with determinism guidance.
* docs/computed-tags-design.md - Documented registries, config env vars, and container wiring.
* docs/computed-tags-design.md - Added execution flow, delivery modes, and initial formatter output shapes.
* docs/computed-tags-design.md - Documented export storage interface and Blob configuration strategy.
* docs/computed-tags-design.md - Selected backend streaming delivery for Blob-hosted artifacts.
* docs/computed-tags-design.md - Updated Blob authentication to managed identity only with local export warning.
* docs/computed-tags-design.md - Added test strategy and rollout guidance for the export pipeline.

### Removed

## Release Summary

**Total Files Affected**: 3

### Files Modified (3)

* docs/computed-tags-design.md - Added export pipeline design details across baseline, interfaces, execution, storage, and testing.
* .copilot-tracking/changes/20260116-export-pipeline-design-changes.md - Recorded implementation progress and summaries.
* .copilot-tracking/plans/20260116-export-pipeline-design-plan.instructions.md - Marked all phases and tasks complete.

### Dependencies & Infrastructure

* **New Dependencies**: None
* **Updated Dependencies**: None
* **Infrastructure Changes**: None
* **Configuration Updates**: None
