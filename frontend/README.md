---
title: Ground Truth Curator frontend
description: Local development guide for the Ground Truth Curator frontend.
ms.date: 2026-01-15
ms.topic: how-to
---

## Overview

Welcome. This is the React + Vite + TypeScript frontend for Ground Truth Curation. This guide helps you get running locally, connect to the backend, generate API types, and run tests.

## Prerequisites

- Node.js 18+ (LTS recommended)
- npm 9+ (bundled with Node)

## Quick start

1) Install dependencies

   ```bash
   npm install
   ```

2) Configure environment

   - Copy `.env.example` to `.env.local` and adjust as needed:
     - `VITE_API_BASE_URL` – backend base URL (default `http://localhost:8000`)
     - `VITE_OPENAPI_URL` – OpenAPI spec URL used for type generation
     - `VITE_DEV_USER_ID` – optional dev-only user id sent as `X-User-Id`
     - `VITE_SELF_SERVE_LIMIT` – optional default for self-serve assignments

3) Start the app

   ```bash
   npm run dev
   ```

   Visit http://localhost:5173. During development, all requests to `/v1/...` are proxied to `VITE_API_BASE_URL` (default `http://localhost:8000`) to avoid CORS.

## Connect to the backend

This app calls the backend under the `/v1` path. In development, Vite is configured to proxy `/v1` → `http://localhost:8000` by default. You can:

- Change the target host by editing `VITE_API_BASE_URL` in `.env.local`.
- Keep frontend calls relative (e.g., `fetch('/v1/ground-truths')`) so the proxy works seamlessly.
- Optionally set `VITE_DEV_USER_ID` in `.env.local` to send an `X-User-Id` header for dev-only flows.

More details: `CONNECT_TO_BACKEND.md`.

## Generate OpenAPI TypeScript types

Generate strongly-typed models from the backend OpenAPI spec into `src/api/generated.ts`:

```bash
npm run api:types
```

By default this uses `VITE_OPENAPI_URL` (falls back to `http://localhost:8000/v1/openapi.json`). If the backend spec changes, re-run the command. A CI-friendly drift check is available:

```bash
npm run api:types:check
```

## Scripts you’ll use

- Dev server: `npm run dev`
- Typecheck & build: `npm run build`
- Preview built app: `npm run preview` (served at http://localhost:4173)
- Lint/format: `npm run lint` (Biome)
- Unit tests: `npm test` or `npm run test:run` (Vitest)

## Demo mode

The UI includes a demo flow. You can toggle via env at startup:

- `VITE_DEMO_MODE=0` (default in tests) to run against the real backend
- `VITE_DEMO_MODE=1` to enable demo behavior

The build injects `import.meta.env.DEMO_MODE` to match `VITE_DEMO_MODE` for client code.

## Telemetry (optional)

Client telemetry is initialized early and can be configured via Vite env vars:

- `VITE_TELEMETRY_BACKEND`: `otlp` | `appinsights` | `none` (default `otlp`)
- `VITE_OTLP_EXPORTER_URL`: OTLP HTTP collector endpoint (for OTel)
- `VITE_APPINSIGHTS_CONNECTION_STRING`: Azure App Insights connection string (fallback)
- `VITE_ENVIRONMENT`: environment label (local/dev/staging/prod)
- `VITE_BUILD_SHA`: short commit SHA

Telemetry automatically no-ops in demo mode or when required config is missing.

## Troubleshooting

- API requests 404/CORS in dev
  - Use relative paths like `/v1/...` and ensure the Vite proxy is active by running `npm run dev`.
  - Confirm your backend is listening at `VITE_API_BASE_URL` (default `http://localhost:8000`).

- OpenAPI type generation fails
  - Verify `VITE_OPENAPI_URL` points to a valid OpenAPI JSON and the backend is running.

## Learn more / contribute

- Codebase map and how things fit: `CODEBASE_GUIDE.md`
- Backend wiring and types generation: `CONNECT_TO_BACKEND.md`
- Project requirements: `docs/MVP_REQUIREMENTS.md`

PRs welcome. Keep commits tidy and prefer conventional messages. Thanks for contributing!
