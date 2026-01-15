---
title: XSS Sanitization
description: The XSS sanitization system cleanses user-generated content to prevent script injection attacks
jtbd: JTBD-004
author: spec-builder
ms.date: 2026-01-22
status: draft
stories: [SA-565]
---

# XSS Sanitization

## Overview

This spec addresses URL validation consistency across reference-handling components, resolving a security gap where some components lack protection against malicious URL schemes.

**Parent JTBD:** Help administrators ensure data integrity and security

## Problem Statement

Research into SA-565 (originally filed for XSS concerns in key paragraph rendering) found that the primary concern is a false positive. React's controlled `<textarea>` components automatically escape content, and the codebase does not use `dangerouslySetInnerHTML`.

However, the investigation uncovered an **inconsistent URL validation pattern**:

- [InspectItemModal.tsx](../frontend/src/components/modals/InspectItemModal.tsx#L28-L54) implements robust `validateReferenceUrl` that blocks `javascript:`, `data:`, and other malicious schemes
- [TurnReferencesModal.tsx](../frontend/src/components/app/editor/TurnReferencesModal.tsx) and [SelectedTab.tsx](../frontend/src/components/app/ReferencesPanel/SelectedTab.tsx) do not validate URLs before opening

If a compromised backend sends references with `javascript:` or `data:` URLs, these unprotected components would allow them to execute when clicked.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | Consistent URL validation | Must | All reference URL handlers block `javascript:`, `data:`, `vbscript:`, `about:`, and `blob:` schemes |
| FR-002 | Shared utility extraction | Should | Extract `validateReferenceUrl` from InspectItemModal.tsx to a shared utility location |
| FR-003 | External link attributes | Should | All external links include `rel="noopener noreferrer"` for complete protection |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Security | No malicious URL schemes allowed | Zero `javascript:`, `data:` URLs openable |
| NFR-002 | Maintainability | Single validation implementation | One shared utility, no duplication |

## User Stories

### Story: Prevent malicious URL injection

**As an** administrator reviewing curated data,  
**I want** all reference URLs validated before opening,  
**So that** I'm protected from script injection via malicious URL schemes even if backend data is compromised.

**Acceptance criteria:**

- Clicking a reference with `javascript:alert('xss')` URL shows an error instead of executing
- Clicking a reference with `data:text/html,<script>...</script>` URL shows an error instead of executing
- Valid `http:` and `https:` URLs open normally

## Technical Considerations

### Affected Components

1. **InspectItemModal.tsx** - Already has `validateReferenceUrl` implementation
2. **TurnReferencesModal.tsx** - Uses `onOpenReference` callback without validation
3. **SelectedTab.tsx** - Uses `onOpenReference` callback without validation

### Implementation Approach

1. Extract `validateReferenceUrl` from [InspectItemModal.tsx#L28-L54](../frontend/src/components/modals/InspectItemModal.tsx#L28-L54) to `frontend/src/utils/urlValidation.ts`
2. Import and apply in TurnReferencesModal's reference link click handler
3. Import and apply in SelectedTab's reference link click handler
4. Update `rel` attributes from `noreferrer` to `noopener noreferrer` in both files

### Existing Mitigations

- React's JSX expression escaping handles content XSS automatically
- `react-markdown` uses allowlist approach with HTML disabled by default
- No `dangerouslySetInnerHTML` usage in the codebase

## Open Questions

1. Should SA-565 be closed as "not a bug" for the original XSS concern and a new story created for URL validation, or should SA-565 be updated to reflect the actual URL validation gap?
2. Should domain allowlisting be considered for reference URLs at the application level?

## References

- [SA-565](https://example.atlassian.net/browse/SA-565) - Original story
- [Research file](../.copilot-tracking/subagent/20260122/xss-sanitization-research.md) - Full investigation results
- [InspectItemModal.tsx validateReferenceUrl](../frontend/src/components/modals/InspectItemModal.tsx#L28-L54) - Reference implementation
