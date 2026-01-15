# API change checklist — Assignments and Ground Truths

This checklist captures the developer-facing changes required to support the integration use-case tests while hardening assignment semantics and avoiding dataset-wide scans.

Scope
- Enrich `GET /v1/assignments/my` response.
- Add `GET /v1/ground-truths/{dataset}/{item_id}` point-read.
- Enforce ownership on SME update route with 403 and stable error code.
- Require `If-Match` on all write paths (approve/skip/delete) and return updated ETag.
- Clear assignment fields atomically on transitions (skipped/approved/deleted).

Notes
- Use timezone-aware UTC timestamps via `datetime.now(timezone.utc)` when setting or updating `assignedAt` or other timestamps.

## 1) Endpoint specifications

### 1.1 GET /v1/assignments/my

- Auth: caller identity from `X-User-Id` (dev mode) or normal auth middleware in other environments.
- Request headers:
  - `X-User-Id: <user>` (dev/testing)
- Response 200 (application/json): Array of AssignmentSummary

AssignmentSummary (response item)
- `id` (string)
- `dataset` (string)
- `bucket` (string)
- `status` (enum: draft | approved | skipped | deleted)
- `etag` (string)
- `assignedAt` (string, RFC3339 UTC)

HTTP headers
- `ETag` header is optional per-item, but the item’s `etag` MUST be included in the JSON body.

OpenAPI sketch (YAML)
```yaml
paths:
  /v1/assignments/my:
    get:
      summary: List current user's assignments
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/AssignmentSummary'
components:
  schemas:
    AssignmentSummary:
      type: object
      required: [id, dataset, bucket, status, etag, assignedAt]
      properties:
        id:
          type: string
        dataset:
          type: string
        bucket:
          type: string
        status:
          type: string
          enum: [draft, approved, skipped, deleted]
        etag:
          type: string
        assignedAt:
          type: string
          format: date-time
```


### 1.3 PUT /v1/assignments/{dataset}/{bucket}/{item_id}

- Purpose: SME updates: approve OR update status (skipped/deleted).
- Request headers (required):
  - `If-Match: <etag>` (all write paths)
  - `X-User-Id: <user>` (dev/testing)
- Body: One of
  - Approve form: `{ "approve": true, "answer": string | null }`
  - Status update form: `{ "status": "skipped" | "deleted" }`
- Responses:
  - 200 OK: returns updated item with new `etag` and current `status`.
  - 403 Forbidden: Ownership violation. Error code `ASSIGNMENT_OWNERSHIP`.
  - 412 Precondition Failed: Missing/invalid ETag. Error code `IF_MATCH_REQUIRED` or `ETAG_MISMATCH`. Include current ETag in `ETag` header.

Error response schema
```json
{
  "error": {
    "code": "ASSIGNMENT_OWNERSHIP",
    "message": "Item is assigned to a different user."
  }
}
```

OpenAPI sketch
```yaml
paths:
  /v1/assignments/{dataset}/{bucket}/{item_id}:
    put:
      summary: Update an assignment (approve / change status)
      parameters:
        - name: dataset
          in: path
          required: true
          schema: { type: string }
        - name: bucket
          in: path
          required: true
          schema: { type: string }
        - name: item_id
          in: path
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              oneOf:
                - type: object
                  required: [approve]
                  properties:
                    approve: { type: boolean }
                    answer: { type: string, nullable: true }
                - type: object
                  required: [status]
                  properties:
                    status:
                      type: string
                      enum: [skipped, deleted]
      responses:
        '200':
          description: Updated
          headers:
            ETag:
              schema: { type: string }
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GroundTruthSummary'
        '403':
          description: Ownership violation
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '412':
          description: If-Match missing or ETag mismatch
          headers:
            ETag:
              schema: { type: string }
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
components:
  schemas:
    ErrorResponse:
      type: object
      required: [error]
      properties:
        error:
          type: object
          required: [code, message]
          properties:
            code: { type: string }
            message: { type: string }
```

Semantics
- Ownership: Only the currently assigned user may mutate. If unassigned or assigned to a different user, return 403/`ASSIGNMENT_OWNERSHIP`.
- Concurrency: All writes require `If-Match` with the current ETag. On mismatch, return 412 and provide the current ETag in the `ETag` header.
- ETag: Return the new ETag in the 200 response body and `ETag` header.
- Assignment clearing: On transitions to skipped/approved/deleted, clear `assignedTo` and `assignedAt` atomically with the status change.

## 2) Data model and repository updates

- Items store: ensure fields exist and are updated atomically:
  - `status`: draft | approved | skipped | deleted
  - `etag`: version token (Cosmos `_etag` or app-level value)
  - `assignedTo` (nullable)
  - `assignedAt` (nullable, RFC3339 UTC). Set with `datetime.now(timezone.utc)`.
- Repository methods must:
  - Perform conditional writes via ETag (If-Match).
  - Clear `assignedTo`/`assignedAt` during status transitions (approve/skip/delete) in the same write.
  - Return updated `etag` and `status`.

## 3) Backend tasks checklist

- [ ] Update `GET /v1/assignments/my` handler to return: id, dataset, bucket, status, etag, assignedAt.
- [ ] Implement `GET /v1/ground-truths/{dataset}/{item_id}` point-read.
- [ ] Enforce ownership in SME update path; return 403 with code `ASSIGNMENT_OWNERSHIP`.
- [ ] Require `If-Match` for approve/skip/delete; return 412 on mismatch; echo current ETag in header.
- [ ] Clear `assignedTo` and `assignedAt` atomically on transitions to skipped/approved/deleted.
- [ ] Include `ETag` header with new value on successful writes.
- [ ] Update Pydantic schemas: `AssignmentSummary`, `GroundTruthSummary`, `ErrorResponse`.
- [ ] Update OpenAPI/route docs accordingly.
- [ ] Add audit logging for ownership violations and 412 conflicts (include request id, item id, dataset, user).

## 4) Tests checklist

- [ ] Unit tests: ownership enforcement returns 403 with `ASSIGNMENT_OWNERSHIP`.
- [ ] Unit tests: missing `If-Match` → 412 `IF_MATCH_REQUIRED`.
- [ ] Unit tests: wrong ETag → 412 `ETAG_MISMATCH`, response includes current ETag header.
- [ ] Integration tests: helpers use `/v1/assignments/my` fields; no dataset enumeration.
- [ ] Integration tests: approve/skip/delete require `If-Match` and return new ETag; ETag changes asserted.
- [ ] Integration tests: `GET /v1/ground-truths/{dataset}/{item_id}` used for point reads.

## 5) Rollout and compatibility

- `GET /v1/assignments/my` enrichment is additive (backward compatible).
- Requiring `If-Match` is a breaking change for clients that previously omitted it. Options:
  - Immediate enforcement (recommended for test envs).
  - Short deprecation window: log warnings when missing, then enforce in prod.
- Communicate error codes and new header requirements to client teams.

## 6) Examples

Fetch my assignments
```bash
curl -sS \
  -H 'X-User-Id: alice' \
  http://localhost:8000/v1/assignments/my | jq .
```


Approve with If-Match
```bash
curl -sS -X PUT \
  -H 'X-User-Id: alice' \
  -H 'If-Match: "W/\"etag-123\""' \
  -H 'Content-Type: application/json' \
  -d '{"approve": true, "answer": "final answer"}' \
  http://localhost:8000/v1/assignments/dataset123/bucketA/item-001 | jq .
```

Skip with If-Match
```bash
curl -sS -X PUT \
  -H 'X-User-Id: alice' \
  -H 'If-Match: "W/\"etag-456\""' \
  -H 'Content-Type: application/json' \
  -d '{"status": "skipped"}' \
  http://localhost:8000/v1/assignments/dataset123/bucketA/item-002 | jq .
```

Handling 412 ETag mismatch (example response)
```json
{
  "error": { "code": "ETAG_MISMATCH", "message": "ETag does not match current resource version." }
}
```

## 7) Acceptance

- `GET /v1/assignments/my` returns id, dataset, bucket, status, etag, assignedAt for each item.
- SME update path: 403 with `ASSIGNMENT_OWNERSHIP` for cross-user mutations.
- All writes require `If-Match` and return a new ETag; mismatches return 412 and include current ETag header.
- Assignment fields are cleared atomically on transitions (skipped/approved/deleted).
