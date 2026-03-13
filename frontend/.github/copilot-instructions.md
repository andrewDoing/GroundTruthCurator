# Frontend Copilot Instructions

- Stack: Vite 7, React 19, TypeScript, Tailwind CSS v4, Biome, Vitest, and `openapi-fetch`.
- For React performance, rendering, bundle, and client data-flow work, consult `.github/skills/react-best-practices/SKILL.md` and `.github/skills/react-best-practices/APPLICABILITY.md`.
- Apply general React and Vite guidance. Do not copy Next.js-only patterns such as `next/dynamic`, API routes, server actions, `after()`, or RSC/server-only optimizations into this frontend.
- Treat SWR guidance as reference-only unless SWR is intentionally added to the frontend dependencies.
- Keep HTTP calls in `src/api/` or `src/services/`, not presentational components.
- Validate frontend changes with `npm run lint:check`, `npm run typecheck`, and for behavior changes `npm run test:run -- --pool=threads --poolOptions.threads.singleThread`.
