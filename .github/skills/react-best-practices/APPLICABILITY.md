# React Best Practices Applicability for Ground Truth Curator

Use this file as the repo-specific override for `.github/skills/react-best-practices/SKILL.md`.

The upstream skill mixes framework-agnostic React guidance with Next.js- and SWR-specific guidance. This repository's `frontend/` app is a Vite + React 19 + TypeScript application, so agents should use the matrix below before applying rules mechanically.

## Repo Facts

- Frontend stack: Vite, React 19, TypeScript, Tailwind via Vite plugin.
- Frontend data access uses `fetch` / `openapi-fetch` helpers in `frontend/src/api/` and `frontend/src/services/`.
- Frontend validation uses Biome, Vitest, and `npm run typecheck`.
- Backend routes and server workflows live in FastAPI under `backend/app/api/v1/`, not in Next.js route handlers.

## Status Legend

- **Applies**: Use the rule normally in this repo.
- **Applies with adaptation**: Keep the principle, but translate framework-specific examples to Vite/React patterns.
- **Conditional**: Use only when the affected rendering mode or architecture is actually present.
- **Not applicable**: Do not apply this rule in the current repo stack.
- **Reference only**: Keep as background context; do not introduce the referenced library or framework pattern without an explicit stack change.

## Rule Family Matrix

| Rule family | Status | Repo-specific guidance |
| --- | --- | --- |
| `async-*` | Applies with adaptation | Use `async-parallel`, `async-defer-await`, and `async-dependencies` for client orchestration. Treat `async-api-routes` as not applicable, and use `async-suspense-boundaries` only when the component tree already uses Suspense intentionally. |
| `bundle-*` | Applies with adaptation | Keep direct imports, conditional loading, and defer-heavy-third-party guidance. Translate `bundle-dynamic-imports` to `React.lazy()` or dynamic `import()` patterns instead of `next/dynamic`. |
| `server-*` | Not applicable | These rules target Next.js or server-rendered React patterns. For this repo, frontend work should not apply them; backend server work belongs in FastAPI and follows backend architecture rules instead. |
| `client-*` | Applies with adaptation | Event-listener and localStorage guidance applies. Treat `client-swr-dedup` as reference only because the repo uses `fetch` / `openapi-fetch`, not SWR. |
| `rerender-*` | Applies | These rules are generally useful for React component structure, state subscriptions, and avoiding unnecessary work. |
| `rendering-*` | Conditional | DOM/rendering rules usually apply, but hydration- and resource-hint-specific guidance depends on the actual rendering path. Use only when the component or page architecture warrants it. |
| `js-*` | Applies | General JavaScript hot-path guidance applies when it improves measured performance without harming readability. |
| `advanced-*` | Conditional | Use only for real hotspots or stable abstractions. Avoid adding complexity speculatively. |

## Common Translations

- `next/dynamic` -> `React.lazy()` with `Suspense`, route-level code splitting, or gated `import()`.
- Next.js API routes, server actions, `after()`, and RSC/server-only caching -> not applicable in `frontend/`.
- SWR -> keep using the repo's existing `fetch` / `openapi-fetch` helpers unless SWR is explicitly added.
- Server serialization and cross-request caching guidance -> reference only for architectural thinking, not direct frontend implementation.

## When In Doubt

- Prefer framework-agnostic React, rendering, re-render, bundle, and JavaScript rules first.
- If a rule example imports from `next/*` or assumes server components, treat it as not applicable unless the stack changes.
- If a rule assumes a library that is not already in `frontend/package.json`, treat it as reference only until that dependency is intentionally adopted.
