---
title: Conventions and sources research
description: Repo guidance on documentation + identification of sources of truth for requirements vs implementation
author: GitHub Copilot
ms.date: 2026-01-21
ms.topic: reference
keywords:
  - conventions
  - requirements
  - documentation
  - source of truth
estimated_reading_time: 6
---

# Conventions and Sources Research — Requirements vs Implementation

## Scope

This note answers:

- Where this repo documents **product requirements** (sources of truth)
- Where this repo documents **implementation plans/behavior** (derived from requirements)
- What **doc-writing conventions** exist (including markdown style constraints, if any)

This is “research only” and does not propose changes.

## Primary instruction sources (repo)

### Copilot instruction files

- Backend Copilot conventions: [backend/.github/copilot-instructions.md](../../../backend/.github/copilot-instructions.md#L1-L4)
  - Timestamp rule: use `datetime.now(timezone.utc)` for timestamp updates.
  - Typing rule: prefer built-in generics (`dict`, `list`) over `typing.Dict`/`typing.List`.
  - Workflow hint: use notify MCP `show-notification` when done.
- Frontend Copilot conventions: [frontend/.github/copilot-instructions.md](../../../frontend/.github/copilot-instructions.md#L1)
  - Workflow hint: use notify MCP `show-notification` when done.

Note: There are duplicated copies under `workspace-1/` and `workspace-2/` mirroring the same instruction patterns.

### Repo prompt templates (doc/plan authoring)

- “Discussion prep” prompt: [backend/.github/prompts/build_context.prompt.md](../../../backend/.github/prompts/build_context.prompt.md#L1-L6)
  - Explicitly instructs creating a markdown file in `/docs` for discussion preparation.
- “Planning” prompt: [backend/.github/prompts/plan.prompt.md](../../../backend/.github/prompts/plan.prompt.md#L1-L16)
  - Explicitly instructs writing plans to `/plans/*-plan.md`.
- Frontend planning prompt: [frontend/.github/prompts/plan.prompt.md](../../../frontend/.github/prompts/plan.prompt.md#L1-L14)
  - Similar planning guidance, but **does not** prescribe a plan output folder.

## Sources of truth (product requirements)

### 1) Canonical requirements doc

- Requirements: [docs/ground-truth-curation-reqs.md](../../../docs/ground-truth-curation-reqs.md)
  - Explicitly labeled “MVP Requirements”.
  - Used as the declared requirements source of truth for backend implementation planning: [backend/docs/fastapi-implementation-plan.md](../../../backend/docs/fastapi-implementation-plan.md#L1-L7)

Interpretation:

- Treat `docs/ground-truth-curation-reqs.md` as the top-level contract for “what the system must do” (personas, scope, flows, and open questions).

### 2) Business value framing

- Product value narrative: [BUSINESS_VALUE.md](../../../BUSINESS_VALUE.md)
  - Declares ground truth as “source of truth for model and agent evaluation”.

Interpretation:

- This doc is not a detailed functional spec, but it is a “why we’re building this” source and can anchor prioritization.

### 3) Backlog / work-item source inputs

- Jira-derived backlog lists:
  - [prd.json](../../../prd.json)
  - [prd-refined-1.json](../../../prd-refined-1.json)
  - [prd-refined-2.json](../../../prd-refined-2.json)
  - [prd-genericize.json](../../../prd-genericize.json)
  - [Jira.csv](../../../Jira.csv)

Interpretation:

- These files look like work-item exports (issue IDs, titles, descriptions, status). They are useful for scope tracking and prioritization, but they are not written as a normative requirements spec.

## Secondary “spec/design” docs (normative by area)

These docs behave like “design specs” for specific subsystems and often use explicit language like “authoritative”, “canonical”, or “source of truth”. They appear intended to guide implementation behavior.

### Tagging: manual vs computed

- Manual tags design: [docs/manual-tags-design.md](../../../docs/manual-tags-design.md)
  - Manual tags “remain authoritative” and are “source of truth” in `manualTags`: [docs/manual-tags-design.md](../../../docs/manual-tags-design.md#L16-L22)
  - A merged `tags` view may exist, but is “not authoritative”: [docs/manual-tags-design.md](../../../docs/manual-tags-design.md#L43-L44)
- Computed tags design: [docs/computed-tags-design.md](../../../docs/computed-tags-design.md)
  - Includes explicit “authoritative manual tags” examples.

Related requirement gap:

- The MVP requirements doc explicitly lists “Authoritative source of truth for tags” as an open question: [docs/ground-truth-curation-reqs.md](../../../docs/ground-truth-curation-reqs.md#L382)

Interpretation:

- Tag “source of truth” is partly specified (manualTags authoritative) but still called out as an open requirements question at the MVP level.

### Frontend runtime configuration

- Runtime config precedence: [docs/frontend-runtime-configuration.md](../../../docs/frontend-runtime-configuration.md)
  - Declares backend env vars as “authoritative” and frontend `.env` as fallback-only: [docs/frontend-runtime-configuration.md](../../../docs/frontend-runtime-configuration.md#L23-L33)

### Export schema and migration

- Canonical export schema and migration: [docs/json-export-migration-plan.md](../../../docs/json-export-migration-plan.md)
  - Uses “canonical schema” language for the JSON wire format.

## Implementation sources (how the repo should be built/extended)

### Backend implementation guides

- Backend “authoritative” implementation guide: [backend/CODEBASE.md](../../../backend/CODEBASE.md)
  - Explicitly says to add clarifications there so it “stays authoritative”: [backend/CODEBASE.md](../../../backend/CODEBASE.md#L222)
- Backend staged implementation plan: [backend/docs/fastapi-implementation-plan.md](../../../backend/docs/fastapi-implementation-plan.md)
  - Explicitly derived from the canonical requirements doc.
- Backend feature/workflow specs (implementation-facing): [backend/docs/](../../../backend/docs/)
  - Examples: API consolidation plans, export pipeline, tagging plan, emulator limitations/workarounds.

Interpretation:

- `backend/CODEBASE.md` is the “how to work in this codebase” source.
- `backend/docs/*` appears to be the system’s implementation-oriented spec set.

### Frontend implementation guides

- Frontend codebase guide: [frontend/CODEBASE.md](../../../frontend/CODEBASE.md)
  - Documents architecture, conventions, and safe extension points.
- Frontend MVP checklist: [frontend/docs/MVP_REQUIREMENTS.md](../../../frontend/docs/MVP_REQUIREMENTS.md#L1)
  - Appears to be a status-tracking checklist (items marked `[x]/[ ]`), mixing frontend needs with backend status notes.

Interpretation:

- `frontend/CODEBASE.md` is the best “implementation guide” for frontend structure.
- `frontend/docs/MVP_REQUIREMENTS.md` is useful operationally, but it reads more like a progress checklist than a normative product requirements doc.

## Markdown / doc-writing style constraints (repo-observable)

### 1) Frontmatter convention is common

Many markdown documents include Microsoft Docs-style YAML frontmatter:

- Example: `ms.date` / `ms.topic` in [docs/manual-tags-design.md](../../../docs/manual-tags-design.md#L1-L12)
- Example: `ms.date` / `ms.topic` in [frontend/CODEBASE.md](../../../frontend/CODEBASE.md#L1-L12)

Interpretation:

- For “real” documentation/spec files (especially in `docs/` and major `CODEBASE.md` guides), using YAML frontmatter appears to be the convention.

### 2) Markdownlint appears in some artifacts, but no repo config was found

- Multiple `.copilot-tracking/*` documents start with `<!-- markdownlint-disable-file -->` (evidence via grep), suggesting markdownlint is used somewhere in the authoring workflow.
- No `.markdownlint*` config file was found in this repo (search across common config names returned none).

Interpretation:

- There is no repo-visible markdownlint ruleset to follow, but some generated/tracking artifacts proactively disable markdownlint.

### 3) Formatting/tooling constraints are primarily code-focused

- Frontend uses Biome for lint/format via `biome check --write`: [frontend/package.json](../../../frontend/package.json#L7-L18) and config in [frontend/biome.json](../../../frontend/biome.json)
  - This is primarily relevant to code (TS/JS/JSON). No repo evidence that markdown is formatted/linted by Biome here.

## Notes on repo layout duplicates

This repo contains `workspace-1/` and `workspace-2/` directories with mirrored docs and `.github` conventions. For “source of truth” purposes, the top-level `docs/`, `backend/`, and `frontend/` folders appear to be the canonical set; the workspace copies look like snapshots or sandboxes.
