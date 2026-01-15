# Drift Cleanup Plan — API vs Design

This document captures how the implemented API differs from the consolidation design in `docs/api-write-consolidation-plan.v2.md`, and outlines a focused plan to converge. No code changes are included here per plan.prompt.md.

## Overview

Goal: align current FastAPI endpoints so all Ground Truth writes happen only via SME PUT and Curator PUT, with Curator POST reserved for import/create, ETag-based concurrency enforced, and reference-specific routes removed. We will keep anything that’s already compliant and prune or adjust what’s not.

## What we’ll do (short)

- Keep endpoints that match the design and document their current shapes.
- Remove or hide routes that aren’t in the design (or consolidate where noted).
- Tighten request/response shapes where the design requires (ETag field, refs handling).
- Add/confirm tests for concurrency (If-Match/etag), soft-delete via SME PUT, and absence of reference subroutes.

## Current implementation inventory (observed)

- /v1/assignments
  - POST "/self-serve" — requests a batch (size query) [exists]
  - GET "/my" — lists assignment documents [exists]
  - PUT "/{item_id}" — updates item; supports approve, refs list; accepts If-Match header or body etag; 412 on mismatch [exists]

- /v1/ground-truths
  - POST "" — bulk import of GroundTruthItem list; 409 on conflict [exists]
  - GET "/{datasetName}" — lists items; returns `etag` property in payload [exists]
  - PUT "/{datasetName}/{bucket}/{item_id}" — update with If-Match or body etag; requires one, 412 otherwise; refs accepted; returns serialized dict with `etag` [exists]
  - PUT "/{datasetName}/{item_id}" — bucketless convenience that maps to bucket=0 [extra but harmless]
  - DELETE "/{datasetName}" — delete dataset [exists]
  - DELETE "/{datasetName}/{bucket}/{item_id}" — delete item [exists]
  - DELETE "/{datasetName}/{item_id}" — bucketless convenience [extra but harmless]
  - POST "/snapshot" — trigger snapshot/export [exists]
  - Reference subroutes — none present (no /references add/remove) [compliant]

- /v1/ground-truths/stats
  - GET — returns counts via repo.stats() [exists]

- /v1/assignments (supporting self-serve UX; not part of consolidation matrix)
  - POST "/self-serve" — request N assignments; returns assignment documents [extra]
  - GET "/my" — list caller’s assignment documents [extra]

- Schemas & Tags helpers (out of scope for consolidation but present)
  - GET /v1/schemas, GET /v1/schemas/{name}
  - GET /v1/tags/schema

## Design vs implementation — drift summary

- Keep list matches:
  - POST /v1/assignments/self-serve — implemented.
  - GET /v1/assignments/my — implemented.
  - PUT /v1/assignments/{item_id} — implemented; supports refs and ETag.
  - POST /v1/ground-truths — implemented as import-only.
  - GET /v1/ground-truths/{datasetName} — implemented; returns `etag` per item.
  - PUT /v1/ground-truths/{datasetName}/{item_id} — effectively implemented with optional bucket segment; requires ETag; supports refs.
  - DELETE /v1/ground-truths/{datasetName} — implemented.
  - DELETE /v1/ground-truths/{datasetName}/{item_id} — implemented; bucket form also present.
  - POST /v1/ground-truths/snapshot — implemented.
  - GET /v1/ground-truths/stats — implemented.

- Removal targets (per design):
  - Reference subroutes — not present; already compliant.
  - SME DELETE under assignments — not present; soft delete via PUT implemented; compliant.

- Extras not listed in design (non-blocking but noteworthy):
  - PUT/DELETE bucketless convenience forms under /v1/ground-truths — present; acceptable if we keep them documented as convenience aliases.
  - /v1/assignments/self-serve and /v1/assignments/my — additional endpoints supporting self-serve assignment flow. Design matrix scoped write consolidation for GT items; these are orthogonal but should be documented.

- Concurrency and refs handling:
  - Curator PUT requires If-Match or body `etag`; returns 412 when missing or mismatched — matches design.
  - SME PUT accepts If-Match header or body `etag`; does not explicitly require an ETag before update, but repo upsert can enforce mismatch. Consider aligning SME PUT to require ETag when updating existing GT fields; approval path may be exempt if repo ensures safe transition.

## Implementation-only-now focus (what to change or confirm)

We will implement only what’s needed to meet the design; no legacy fallbacks unless required.

- Confirm SME PUT behavior:
  - Require ETag for non-approve mutations (edited_question, answer, refs, status).
  - Keep approve flow, passing through to repo.mark_approved; either require ETag or ensure atomic transition in repo.

- Keep convenience bucketless routes but document them as aliases; no extra logic.

- Ensure response bodies include updated `etag` where applicable (already true for Curator PUT and list; verify SME PUT response includes latest etag).

## Functions to implement/adjust (names + purpose)

- app/api/v1/assignments.update_item
  - Enforce ETag required for non-approve updates; surface 412 on missing or mismatch.

- app/api/v1/ground_truths.update_ground_truth_default_bucket (no behavior change)
  - Thin alias to bucketed PUT; ensure docs mention it as convenience.

- app/api/v1/ground_truths.update_ground_truth
  - Already enforces ETag and supports refs; keep as-is.

- app/services/assignment_service.approve
  - Ensure atomic approve semantics in repo; confirm it clears assignment documents as needed.

## Tests to add/update (names + behavior)

- tests/integration/test_assignments_etag_required.py (or consolidated in existing integration tests)
  - SME PUT non-approve without ETag returns 412.

- tests/integration/test_assignments_etag_mismatch.py
  - SME PUT with wrong ETag returns 412.

- tests/integration/test_assignments_returns_etag.py
  - Response includes updated etag after successful update.

- tests/unit/test_no_reference_subroutes.py
  - Ensure no /references subroutes exist in router.

- tests/integration/test_curator_put_refs_and_etag.py
  - Curator PUT updates refs and requires ETag; returns new etag.

## Out-of-scope but observed

- /v1/assignments/* endpoints power self-serve assignment; they are not GT item writes and can remain. Document them in API README to avoid confusion with consolidation scope.

---
Acceptance readiness summary:
- Two write paths confirmed: SME PUT and Curator PUT.
- Import POST kept for create-only and implemented.
- Reference subroutes absent; soft delete via SME PUT already folded.
- ETag logic present; SME PUT should be tightened to require ETag for edits (add tests).
