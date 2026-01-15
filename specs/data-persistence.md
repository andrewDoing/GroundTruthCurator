---
title: Data Persistence
description: The persistence layer abstracts storage behind repositories with Cosmos DB as the primary backend.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Data Persistence

## Overview

The persistence layer abstracts storage behind repositories with Cosmos DB as the primary backend.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

The system needs a flexible storage abstraction that supports multiple backends (in-memory for testing, Cosmos DB for production) while enforcing concurrency controls and gracefully handling initialization failures.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The backend shall abstract persistence behind a repository protocol | Must | Storage operations use protocol methods, not direct SDK calls |
| FR-002 | The backend shall support Cosmos DB as the production storage backend | Must | Cosmos implementation passes integration tests |
| FR-003 | The backend shall support in-memory storage for testing | Should | Tests can run without Cosmos dependency |
| FR-004 | Application startup shall not block if Cosmos initialization fails | Must | App starts and healthz reflects degraded state |
| FR-005 | The backend shall enforce optimistic concurrency via ETag on writes | Must | Missing or mismatched ETag returns HTTP 412 |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Resilience | Emulator-incompatible queries shall be gated or skipped in tests | CI passes with emulator |
| NFR-002 | Portability | Repository protocol shall not leak Cosmos-specific constructs | Protocol is backend-agnostic |

## User Stories

### US-001: Persist Item

**As a** service layer
**I want to** persist a ground-truth item
**So that** it is durably stored and retrievable

**Acceptance Criteria:**
- [ ] Given valid item data, when I call the repository upsert, then the item is stored
- [ ] Given an ETag mismatch, when I call upsert, then a concurrency error is raised

### US-002: Graceful Degradation

**As an** operator
**I want to** the app to start even if Cosmos is unavailable
**So that** health checks and diagnostics are accessible

**Acceptance Criteria:**
- [ ] Given Cosmos is unreachable at startup, when the app starts, then it does not crash
- [ ] Given Cosmos is unreachable, when I call healthz, then I see degraded status

## Technical Considerations

### Data Model

- `GroundTruthRepo` protocol defines: `get`, `list`, `upsert`, `delete`, `query`.
- Cosmos implementation uses partition key: `datasetName`.
- Items include `_etag` for concurrency.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Azure Cosmos DB | Production storage | Async SDK calls |
| Cosmos Emulator | Local development | Same SDK, emulator endpoint |

### Constraints

- Cosmos emulator lacks some query operators (e.g., `ARRAY_CONTAINS` in certain contexts); tests gate or skip accordingly.
- Optional Unicode escape workaround for emulator-only invalid escape failures is available via configuration.

## Open Questions

(None)

## References

- [backend/app/adapters/repos/base.py](../backend/app/adapters/repos/base.py)
- [backend/app/adapters/repos/cosmos_repo.py](../backend/app/adapters/repos/cosmos_repo.py)
- [backend/docs/cosmos-emulator-limitations.md](../backend/docs/cosmos-emulator-limitations.md)
- [backend/CODEBASE.md](../backend/CODEBASE.md)
