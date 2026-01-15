---
topic: data-persistence
jtbd: JTBD-001
date: 2026-01-22
status: complete
---

# Research: Data Persistence

## Context

The persistence layer abstracts storage behind a repository protocol with Azure Cosmos DB as the primary backend.

## Sources Consulted

### URLs
- (None)

### Codebase
- [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py): Defines the `GroundTruthRepo` protocol that abstracts storage operations.
- [backend/app/adapters/repos/cosmos_repo.py](backend/app/adapters/repos/cosmos_repo.py): Implements the Cosmos DB repository.
- [backend/app/main.py](backend/app/main.py): Shows lifespan initialization for Cosmos repo; does not block startup on failure.

### Documentation
- [.copilot-tracking/research/20260121-high-level-requirements-research.md](.copilot-tracking/research/20260121-high-level-requirements-research.md): Consolidates persistence and Cosmos emulator requirements.
- [backend/CODEBASE.md](backend/CODEBASE.md): Documents layered architecture and configuration for Cosmos.
- [backend/docs/cosmos-emulator-limitations.md](backend/docs/cosmos-emulator-limitations.md): Documents emulator query limitations and test gating.
- [backend/docs/cosmos-emulator-unicode-workaround.md](backend/docs/cosmos-emulator-unicode-workaround.md): Documents optional Unicode escape workaround.

## Key Findings

1. The backend defines a `GroundTruthRepo` protocol to abstract storage, enabling in-memory and Cosmos backends.
2. The Cosmos implementation is the production backend and is initialized during app lifespan.
3. Startup does not block if Cosmos initialization fails; this supports emulator-not-ready scenarios.
4. The Cosmos emulator has query limitations (for example, lack of `ARRAY_CONTAINS`), and incompatible tests are gated/skipped.
5. An optional Unicode escape workaround exists for emulator-only invalid escape failures.

## Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| Repository protocol abstraction | [backend/app/adapters/repos/base.py](backend/app/adapters/repos/base.py) | Defines interface for pluggable storage |
| Non-blocking lifespan init | [backend/app/main.py](backend/app/main.py) | Supports graceful degradation when emulator is unavailable |

## Open Questions

- (None)

## Recommendations for Spec

- Specify that storage is abstracted via a repository protocol with Cosmos as the primary backend.
- Specify non-blocking startup behavior when Cosmos is unavailable.
- Specify that emulator-incompatible behaviors are gated or skipped in tests.
