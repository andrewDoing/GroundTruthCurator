# React Best Practices

This directory is a vendored copy of Vercel's React best-practices skill, kept in this repository for agent and developer use.

## What is in this vendored copy

- `SKILL.md` - the main skill entrypoint agents should follow.
- `AGENTS.md` - the compiled guidance document included with the vendored copy.
- `APPLICABILITY.md` - the **repo-specific override layer** for this repository's Vite + React frontend; use it to translate or suppress upstream Next.js- and SWR-specific guidance.
- `rules/` - the vendored upstream rule source files included for reference.
- `metadata.json` - upstream metadata and attribution.

## How to use it here

- Use this skill when working on React performance, rendering, bundle, and component-structure changes in `frontend/`.
- Read `APPLICABILITY.md` alongside `SKILL.md` before applying rules mechanically.
- Prefer framework-agnostic React guidance first; treat Next.js- or SWR-specific rules as conditional, adapted, or not applicable based on the applicability matrix.

## Maintenance note

This repository contains a repo-facing vendored copy, not the full upstream authoring/build workspace. Do not expect local regeneration assets such as `src/`, `pnpm` build scripts, or generated `test-cases.json` in this folder.

If this skill needs to be refreshed, use the upstream Vercel-authored source as the source of truth for regeneration, then re-apply this repository's `APPLICABILITY.md` guidance.

## Attribution

Originally created by [@shuding](https://x.com/shuding) at [Vercel](https://vercel.com).
