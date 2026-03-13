# Frontend Runtime Configuration

## Overview

The Ground Truth Curator application supports runtime configuration for the generic host plus plugin-owned evidence workflows. The frontend fetches configuration from the backend's `/v1/config` endpoint on startup so environment-specific approval and evidence-review rules can change without rebuilding the frontend.

## Configuration Architecture

```
Backend Environment → Backend Config → /v1/config API → Frontend Runtime Config
```

### How It Works

1. **Backend reads environment variables** (`GTC_REQUIRE_REFERENCE_VISIT`, `GTC_REQUIRE_KEY_PARAGRAPH`)
2. **Backend exposes `/v1/config` endpoint** that returns these values
3. **Frontend fetches config on startup** and caches it
4. **Frontend uses cached config** for all validation logic
5. **Fallback to env vars** if backend is unavailable (local dev only)

## Environment Variables

### Backend (environments/*.env) - PRIMARY

These are the **authoritative** configuration values:

```bash
# Require all references to be opened/visited before approval (default: true)
GTC_REQUIRE_REFERENCE_VISIT=true

# Require key paragraphs for relevant references (default: false)
GTC_REQUIRE_KEY_PARAGRAPH=false

# Default number of items to request from self-serve assignments (default: 10)
GTC_SELF_SERVE_LIMIT=10
```

### Frontend (.env.local) - FALLBACK ONLY

These are only used as **fallback** when backend is unavailable (e.g., local development):

```bash
# Fallback: Require all references to be opened/visited before approval (default: true)
VITE_REQUIRE_REFERENCE_VISIT=true

# Fallback: Require key paragraphs for relevant references (default: false)
VITE_REQUIRE_KEY_PARAGRAPH=false

# Fallback: Number of items to request from self-serve assignments (default: 10)
VITE_SELF_SERVE_LIMIT=10
```

**Note:** In production, the backend configuration always takes precedence.

## Validation Rules and Evidence Surfaces

Runtime config controls shared host behavior, but reference-specific rules apply only to workflows that still expose compatibility search/evidence or to plugin surfaces that opt into the same gating contract. The generic multi-turn host remains conversation- and expected-tools-driven.

### Reference Visit Requirement

**Environment Variable:** `VITE_REQUIRE_REFERENCE_VISIT` / `GTC_REQUIRE_REFERENCE_VISIT`  
**Default:** `true`  
**Applies to:** RAG-compat evidence workflows and any plugin surface that explicitly opts into visit gating

When enabled (`true`):
- References governed by the active compat/plugin workflow must be opened/visited before approval
- The "Needs visit" indicator appears for unvisited references
- Approval is blocked until all references have `visitedAt` timestamp

When disabled (`false`):
- Plugin-owned evidence can be approved without visit gating when the active workflow does not require it
- Visit status is tracked but not required for approval
- Useful for bulk imports or when references are pre-validated

### Key Paragraph Requirement

**Environment Variable:** `VITE_REQUIRE_KEY_PARAGRAPH` / `GTC_REQUIRE_KEY_PARAGRAPH`  
**Default:** `false`  
**Applies to:** RAG-compat evidence workflows and any plugin surface that explicitly opts into key-paragraph gating

When enabled (`true`):
- Selected references in the active compat/plugin workflow must have key paragraphs ≥40 characters
- Approval is blocked until all selected references have adequate key paragraphs

When disabled (`false`):
- Key paragraphs are optional unless the active compat/plugin workflow requires them
- Approval can proceed without key paragraphs
- Useful for workflows where key paragraphs are added in a separate pass

### Self-Serve Limit

**Environment Variable:** `VITE_SELF_SERVE_LIMIT` / `GTC_SELF_SERVE_LIMIT`  
**Default:** `10`  
**Applies to:** Self-serve assignment requests

This setting controls how many unassigned items are requested when a curator clicks the "Get Work" button.

- **Higher values:** Larger batches, fewer clicks needed
- **Lower values:** Smaller batches, more granular work allocation
- **Typical range:** 5-20 items per batch

Example configurations:
- `GTC_SELF_SERVE_LIMIT=5` - Small batches for focused work sessions
- `GTC_SELF_SERVE_LIMIT=10` - Default balanced batch size
- `GTC_SELF_SERVE_LIMIT=20` - Larger batches for experienced curators

## UI Indicators

### Reference Status Pills

The UI displays reference status with color-coded pills:

- **✓ Visited** (green): Reference has been opened and visited
- **Needs visit** (amber): Reference has not been visited (only shown when visit is required or reference is unvisited)
- **Open** (button): Click to open and mark as visited

**Note:** The duplicate "Needs visit" pill has been removed. Only one indicator is shown based on visit status.

### Key Paragraph Indicators

In single-turn mode:
- Label: "Key paragraph (optional)"
- Character count badge (gray)

In multi-turn mode:
- Label: "Key paragraph"
- Character count badge:
  - Green (≥40 chars) or gray (<40 chars) when `VITE_REQUIRE_KEY_PARAGRAPH=false`
  - Green (≥40 chars) or red (<40 chars) when `VITE_REQUIRE_KEY_PARAGRAPH=true`

## Configuration Examples

### Strict Validation (Production)

**Backend environment file:**
```bash
GTC_REQUIRE_REFERENCE_VISIT=true
GTC_REQUIRE_KEY_PARAGRAPH=true
```

Use case: Production environment where quality is critical

### Relaxed Validation (Development)

**Backend environment file:**
```bash
GTC_REQUIRE_REFERENCE_VISIT=false
GTC_REQUIRE_KEY_PARAGRAPH=false
```

Use case: Development or testing where quick iteration is needed

### Hybrid (Recommended)

**Backend environment file:**
```bash
GTC_REQUIRE_REFERENCE_VISIT=true
GTC_REQUIRE_KEY_PARAGRAPH=false
```

Use case: Ensure references are reviewed but allow flexibility on key paragraphs

## Implementation Details

### Backend API

**Endpoint:** `GET /v1/config`

**Response:**
```json
{
  "requireReferenceVisit": true,
  "requireKeyParagraph": false
}
```

**Implementation:** `backend/app/api/v1/endpoints/config.py`

### Frontend Runtime Config Service

**Service:** `frontend/src/services/runtimeConfig.ts`

**Features:**
- Fetches config from `/v1/config` on app startup
- Caches result for subsequent calls
- Falls back to `VITE_*` env vars if backend unavailable
- Provides synchronous access via `getCachedConfig()`

### Validation Logic

The validation logic is split intentionally:

- `frontend/src/models/validators.ts` - conversation integrity and reference-compat helpers
- `frontend/src/models/gtHelpers.ts` - generic approval plus plugin/compat bypass logic
- `frontend/src/components/app/pages/ReferencesSection.tsx` - generic evidence/review host that decides whether the compatibility search surface is shown

Runtime config only controls the reference-specific branch. Generic multi-turn approval remains conversation- and expected-tools-driven, while plugin-owned evidence panels decide whether to honor these shared reference rules.

### UI Components

The following components reflect configurable evidence validation:

- `frontend/src/components/app/pages/ReferencesSection.tsx`
- `frontend/src/components/app/ReferencesPanel/SelectedTab.tsx`
- `frontend/src/components/app/editor/TurnReferencesModal.tsx`

Help text and indicators now say "may be required based on configuration" rather than stating absolute requirements, and the shared host only renders search when the current workflow still uses the compatibility surface.

## Phase 1 Migration Inventory

- Keep: runtime delivery of reference-specific configuration.
- Rewrite: wording that implies every multi-turn workflow is permanently reference-first.
- Narrow: compatibility-focused UI help text once plugin-owned evidence panels replace the shared references mental model.
- Delete with shim: docs that only describe top-level reference approval after the legacy RAG path is retired.

## Local Development Setup

### Backend Configuration

1. **Edit backend environment file:**
   ```bash
   cd GroundTruthCurator/backend
   # Edit environments/local-development.env
   GTC_REQUIRE_REFERENCE_VISIT=false  # Relaxed for local dev
   GTC_REQUIRE_KEY_PARAGRAPH=false
   ```

2. **Start backend:**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

### Frontend Configuration (Optional Fallback)

If you want to work on frontend without backend running:

1. **Create frontend .env.local:**
   ```bash
   cd GroundTruthCurator/frontend
   cp .env.example .env.local
   # Edit .env.local
   VITE_REQUIRE_REFERENCE_VISIT=false
   VITE_REQUIRE_KEY_PARAGRAPH=false
   ```

2. **Start frontend:**
   ```bash
   npm run dev
   ```

**Note:** Frontend will use backend config if available, env vars only as fallback.

## Production Deployment

### Configuration Flow

1. **Set environment variables** in your deployment platform (Azure Container Apps, Kubernetes, etc.)
   ```bash
   GTC_REQUIRE_REFERENCE_VISIT=true
   GTC_REQUIRE_KEY_PARAGRAPH=false
   ```

2. **Build frontend once:**
   ```bash
   cd GroundTruthCurator/frontend
   npm run build
   ```

3. **Backend serves frontend** with runtime config from environment
   - Backend reads `GTC_*` variables
   - Exposes via `/v1/config` endpoint
   - Frontend fetches on startup

**Benefits:**
- ✅ Single frontend build works for all environments
- ✅ Change config by restarting backend (no rebuild needed)
- ✅ Different validation rules per environment
- ✅ Can be changed via environment variables in deployment platform

## Migration Notes

### Backward Compatibility

The default values maintain backward compatibility:
- `GTC_REQUIRE_REFERENCE_VISIT=true` (existing behavior)
- `GTC_REQUIRE_KEY_PARAGRAPH=false` (existing behavior)

### Existing Items

No data migration is needed. The configuration affects validation logic only, not data structure.

## Future Enhancements

1. **Per-Dataset Configuration**: Allow different validation rules per dataset
2. **Role-Based Validation**: Different rules for SMEs vs. curators
3. **Audit Logging**: Track when items are approved with relaxed validation
4. **Dynamic Config Updates**: WebSocket or polling to update config without refresh
