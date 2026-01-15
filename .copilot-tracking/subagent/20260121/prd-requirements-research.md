# PRD Requirements Research — High-level requirements consistent with current system

Date: 2026-01-21

## Scope and method

This report extracts **high-level “shall/should/may” product requirements** from the PRD sources in this repo and then labels each requirement:

- **Matches existing system**: Yes / No / Unclear
- With a brief justification grounded in **current backend/frontend docs and code**.

Primary requirement sources used:

- [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md) (MVP requirements)
- [prd-genericize.json](prd-genericize.json) (genericization PRD)
- [prd.json](prd.json) (backlog items / future requirements)

Notes:

- [ralph/ralph-prd.txt](ralph/ralph-prd.txt) appears to be **agent execution instructions**, not product requirements.
- [BUSINESS_VALUE.md](BUSINESS_VALUE.md) is treated as **goals/KPIs**, not normative requirements.

---

## Supported / consistent requirements (candidate “current PRD”)

### R-001 — Product-agnostic configuration

- Requirement (shall): The system shall be **product-agnostic**, removing hard-coded product/vendor branding and domain-specific content.
- Requirement (shall): The system shall make **branding** configurable.
- Requirement (shall): The system shall make **trusted reference domains** configurable.
- Requirement (shall): The system shall support a **generic demo mode** (generic sample data).
- Requirement (should): The system should make **manual tags** configurable.
- Primary evidence: [prd-genericize.json](prd-genericize.json#L13-L18), [prd-genericize.json](prd-genericize.json#L39-L45)
- Matches existing system: **Yes**
- System evidence: [frontend/src/config/branding.ts](frontend/src/config/branding.ts#L11), [frontend/src/services/runtimeConfig.ts](frontend/src/services/runtimeConfig.ts#L49), [backend/app/main.py](backend/app/main.py#L44), [frontend/src/config/demo.ts](frontend/src/config/demo.ts#L2-L13)

### R-002 — Bulk import ground-truth items

- Requirement (shall): The system shall allow a curator/admin to **bulk import** generated ground-truth items via an API.
- Requirement (should): The system should support importing **negative cases** via the same mechanism.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L142-L143)
- Matches existing system: **Yes**
- System evidence: [backend/CODEBASE.md](backend/CODEBASE.md#L103)

### R-003 — Assignment visibility isolation

- Requirement (shall): The system shall ensure an SME only sees **their assigned work** (and cannot access other SMEs’ assignments without override).
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L137-L139)
- Matches existing system: **Yes** (documented)
- System evidence: [backend/CODEBASE.md](backend/CODEBASE.md#L111-L112)

### R-004 — Self-serve assignment (pull model)

- Requirement (shall): The system shall allow SMEs to **self-serve** (request) a limited number of items to work on.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L44-L44)
- Matches existing system: **Yes**
- System evidence: [backend/CODEBASE.md](backend/CODEBASE.md#L111)

### R-005 — SME review actions (draft/save/approve/delete)

- Requirement (shall): The system shall allow an SME to **edit and save**, **approve**, or **delete** an assigned item.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L147-L147)
- Matches existing system: **Yes**
- System evidence: [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L29-L160)

### R-006 — Snapshot & export of approved items

- Requirement (shall): The system shall support a **weekly snapshot** and export an immutable JSON artifact containing **approved items + metadata**.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L193-L195)
- Matches existing system: **Yes**
- System evidence: [backend/CODEBASE.md](backend/CODEBASE.md#L108), [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L352-L352)

### R-007 — Controlled-vocabulary tagging (apply tags)

- Requirement (shall): The system shall allow an SME to apply **multiple tags from a controlled list** to an item, and those tags shall be reflected in exports.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L167-L169)
- Matches existing system: **Yes** (apply + schema retrieval)
- System evidence: [backend/app/api/v1/tags.py](backend/app/api/v1/tags.py#L32), [backend/tests/integration/test_tags_schema_api.py](backend/tests/integration/test_tags_schema_api.py#L6), [backend/app/api/v1/assignments.py](backend/app/api/v1/assignments.py#L41-L46)

### R-008 — Soft delete for ground-truth items

- Requirement (shall): The system shall support **soft deletion** of items (hidden from default views/exports while retained for history), and allow deletion via the review workflow.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L173-L175)
- Matches existing system: **Partial / Unclear** (soft delete exists; restore/cleanup requirements appear incomplete)
- System evidence: [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py#L1253-L1254), [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L16)

### R-009 — Aggregate stats endpoint

- Requirement (should): The system should provide a stats endpoint for progress/visibility.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L303-L303)
- Matches existing system: **Yes (aggregate)**
- System evidence: [backend/app/api/v1/stats.py](backend/app/api/v1/stats.py#L11-L14)

---

## Out-of-scope / Not yet supported (per current system)

These are high-level requirements present in PRD sources, but **do not currently match** what the repo documents/implements.

### O-001 — LLM answer generation endpoint/workflow

- Requirement (must/shall): SMEs shall be able to generate an answer using an LLM given the question + relevant context.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L150-L150)
- Matches existing system: **No**
- System evidence: [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L33-L36)

### O-002 — AI Search integration for attaching/detaching references

- Requirement (must/shall): The UI shall connect to AI Search and allow SMEs to attach/detach relevant documents, persisting them into item metadata/exports.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L158-L161)
- Matches existing system: **No**
- System evidence: [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L29-L31)

### O-003 — Tag administration (manage controlled vocabulary)

- Requirement (must/shall): Admins shall be able to manage the controlled tag list.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L167-L167)
- Matches existing system: **No**
- System evidence: [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L24-L27)

### O-004 — SME-specific stats

- Requirement (must/shall): SMEs shall see statistics about *their assigned items* to track progress toward sprint goals.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L188-L188)
- Matches existing system: **No** (current stats is not per-user)
- System evidence: [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L48-L48), [backend/app/api/v1/stats.py](backend/app/api/v1/stats.py#L11-L14)

### O-005 — Batch as a first-class concept

- Requirement (must/shall): Items shall be grouped into batches, with a single assignee per batch.
- Primary evidence: [docs/ground-truth-curation-reqs.md](docs/ground-truth-curation-reqs.md#L182-L182)
- Matches existing system: **Unclear** (assignments exist; “batch” entity support is not clearly implemented/documented)
- System evidence: [backend/CODEBASE.md](backend/CODEBASE.md#L111-L112)

### O-006 — Entra-based authentication / access control design + implementation

- Requirement (should/shall): The system should support Entra-based access control (design and/or implementation stories are captured in PRD backlog).
- Primary evidence: [prd.json](prd.json#L166-L173)
- Matches existing system: **No** (explicitly documented as placeholder)
- System evidence: [backend/CODEBASE.md](backend/CODEBASE.md#L120-L120)

### O-007 — Keyword search of ground-truth items

- Requirement (should/shall): The system should provide keyword search over question/answer for locating items.
- Primary evidence: [prd.json](prd.json#L16-L16)
- Matches existing system: **No**
- System evidence: [frontend/docs/MVP_REQUIREMENTS.md](frontend/docs/MVP_REQUIREMENTS.md#L29-L31)

### O-008 — PII detection in approval flow

- Requirement (should/shall): The system should detect PII during (or before) approval to prevent sensitive data from entering the approved set.
- Primary evidence: [prd.json](prd.json#L94-L95)
- Matches existing system: **No**
- System evidence: (no current backend/frontend evidence found in docs indicating PII scanning)

### O-009 — Duplicate detection / prevention

- Requirement (should/shall): The system should detect duplicates (draft vs approved) and prevent SMEs from working on duplicates.
- Primary evidence: [prd.json](prd.json#L148-L155)
- Matches existing system: **No**
- System evidence: (no current backend/frontend evidence found in docs indicating duplicate detection)

### O-010 — Chunking support

- Requirement (should/shall): The system should support chunking (as described in backlog).
- Primary evidence: [prd.json](prd.json#L40-L41)
- Matches existing system: **No**
- System evidence: (no current backend/frontend evidence found in docs indicating chunking support)

---

## Quick takeaways

- The **core curation loop** (bulk import → self-serve assignments → SME approve/edit/delete → export snapshot) is well supported and consistently documented.
- “Stretch” requirements (AI Search attach/detach, LLM generation, RBAC/Entra, per-user stats, tag administration) are present in PRD sources but are **not yet supported** per current repo docs.
