# Conventions Research — Backend Refactor (Repo/Service/API layering + Cosmos emulator)

## Scope

This note summarizes repository conventions and layering rules relevant to:

- Moving workflow logic out of API/routes and repo implementations into services
- Handling Cosmos DB emulator differences (including a potential “emulator subclass” strategy)

## Primary Sources

- Architecture overview: [backend/CODEBASE.md](../../../../backend/CODEBASE.md#L8-L36)
- DI/composition container: [backend/app/container.py](../../../../backend/app/container.py#L1-L322)
- App startup wiring: [backend/app/main.py](../../../../backend/app/main.py#L1-L85)
- Repo protocol: [backend/app/adapters/repos/base.py](../../../../backend/app/adapters/repos/base.py#L1-L120)
- Cosmos repo implementation: [backend/app/adapters/repos/cosmos_repo.py](../../../../backend/app/adapters/repos/cosmos_repo.py#L630-L1890)
- Emulator docs:
  - Conditional patch pattern: [backend/CONDITIONAL_PATCH_IMPLEMENTATION.md](../../../../backend/CONDITIONAL_PATCH_IMPLEMENTATION.md#L1-L88)
  - Emulator limitations: [backend/docs/cosmos-emulator-limitations.md](../../../../backend/docs/cosmos-emulator-limitations.md#L1-L90)
  - Unicode/backslash workarounds: [backend/docs/cosmos-emulator-unicode-workaround.md](../../../../backend/docs/cosmos-emulator-unicode-workaround.md#L1-L219), [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](../../../../backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L1-L230)

## Conventions & Layering Rules

### 1) Explicit layered architecture (API → Services → Repos/Adapters)

The backend explicitly documents a layered architecture with composition in a central container:

- API layer: routers in [backend/CODEBASE.md](../../../../backend/CODEBASE.md#L24-L30)
- Services layer: workflow logic in [backend/CODEBASE.md](../../../../backend/CODEBASE.md#L24-L30)
- Repositories/adapters layer: Cosmos repo implements a protocol in [backend/CODEBASE.md](../../../../backend/CODEBASE.md#L24-L30)
- Composition via singleton container: [backend/CODEBASE.md](../../../../backend/CODEBASE.md#L24-L30)

Practical implication for refactor:

- Route handlers should remain “thin” (HTTP parsing/validation + calling services).
- Services should own workflow/state validation and call repos.
- Repos should be storage-focused (querying/persistence, ETag enforcement), not business policy.

### 2) Service layer owns state validation; repo methods can be intentionally state-agnostic

The “assign single item” backend design doc explicitly states that `assign_to()` is state-agnostic and that state validation belongs in the service layer:

- “State validation is the responsibility of the service layer” in [backend/docs/assign-single-item-endpoint.md](../../../../backend/docs/assign-single-item-endpoint.md#L78-L87)

This is a strong precedent for moving validations/decision logic out of repo implementations and into services.

### 3) DI/composition pattern: singleton `container` wires repos and services

The DI approach is a simple global singleton container object used by routers and services:

- Container class and global instance: [backend/app/container.py](../../../../backend/app/container.py#L34-L71), [backend/app/container.py](../../../../backend/app/container.py#L321-L322)
- Container lazily initializes repo/services; tests and lifespan call `init_cosmos_repo()` to bind to the current event loop: [backend/app/container.py](../../../../backend/app/container.py#L50-L56)
- Cosmos startup is centralized in `startup_cosmos()` and explicitly:
  - creates repo instances
  - initializes async clients
  - validates containers
  in [backend/app/container.py](../../../../backend/app/container.py#L190-L223)

Practical implication for refactor:

- New services should be registered on `Container` (as attributes) and wired in `init_cosmos_repo()` (or in `__init__` if repo-independent).
- Route handlers should call `container.<service>` rather than `container.repo` when a workflow exists.

### 4) Current state: routers sometimes call repos directly (mixed style)

There is evidence of both patterns:

- Direct repo calls from API routes: e.g. [backend/app/api/v1/ground_truths.py](../../../../backend/app/api/v1/ground_truths.py#L241-L246) and [backend/app/api/v1/ground_truths.py](../../../../backend/app/api/v1/ground_truths.py#L277-L293)
- But also service usage from routes: snapshot endpoints call `container.snapshot_service`: [backend/app/api/v1/ground_truths.py](../../../../backend/app/api/v1/ground_truths.py#L135-L151)

Interpretation:

- The repo supports both direct usage and service-orchestrated usage today.
- The documented architecture (and newer design docs) push toward service-owned workflows.

## Emulator Handling Conventions

### 1) Emulator is expected to be flaky/unready at startup; startup should be fail-soft

Startup intentionally does not block if Cosmos init fails (emulator might not be ready):

- “Don’t block startup; emulator may not be ready yet” in [backend/app/main.py](../../../../backend/app/main.py#L56-L85)
- Same idea documented in [backend/CODEBASE.md](../../../../backend/CODEBASE.md#L11-L14)

Practical implication:

- Emulator-specific subclasses/branches should preserve fail-soft behavior (don’t crash the app on emulator-only issues where possible).

### 2) Conditional behavior for emulator compatibility is a standard pattern here

The repo already uses “if emulator then alternate implementation” in multiple places:

- Emulator detection via endpoint string: [backend/app/adapters/repos/cosmos_repo.py](../../../../backend/app/adapters/repos/cosmos_repo.py#L639-L641)

**Conditional patching example (`assign_to`)**

- Documented split into main + prod patch path + emulator read-modify-replace path: [backend/CONDITIONAL_PATCH_IMPLEMENTATION.md](../../../../backend/CONDITIONAL_PATCH_IMPLEMENTATION.md#L11-L22)
- Implemented selection logic in code: [backend/app/adapters/repos/cosmos_repo.py](../../../../backend/app/adapters/repos/cosmos_repo.py#L1719-L1737)

This establishes a repo convention:

- Prefer a single public method that routes internally based on emulator detection.
- Keep emulator compatibility paths available when Cosmos emulator lacks features.

### 3) Emulator limitations drive in-memory fallbacks and test skips

The emulator limitation on `ARRAY_CONTAINS` is explicitly documented:

- Emulator does not support `ARRAY_CONTAINS`; tag filtering queries fail; tests are skipped: [backend/docs/cosmos-emulator-limitations.md](../../../../backend/docs/cosmos-emulator-limitations.md#L5-L27)
- Workaround: in-memory tag filtering fallback described in [backend/docs/cosmos-emulator-limitations.md](../../../../backend/docs/cosmos-emulator-limitations.md#L29-L36)

And the Cosmos repo uses emulator-specific fallback for pagination with tags/ref_url:

- “For queries with tags… filter in-memory… use in-memory filtering for ref_url if Cosmos emulator is used…” in [backend/app/adapters/repos/cosmos_repo.py](../../../../backend/app/adapters/repos/cosmos_repo.py#L694-L709)

### 4) Emulator Unicode/backslash issues are handled via flag-driven transforms

There are two related docs here:

1) “Unicode character” normalization doc (smart quotes/dashes etc)

- Workaround is activated by `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true` and should not be enabled in production: [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](../../../../backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L27-L33), [backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md](../../../../backend/COSMOS_EMULATOR_UNICODE_WORKAROUND.md#L148-L161)

2) “Unicode escape sequence / backslash” bug doc (Base64 encode `refs.content`)

- Final solution is Base64 encoding `refs[*].content` when `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true`: [backend/docs/cosmos-emulator-unicode-workaround.md](../../../../backend/docs/cosmos-emulator-unicode-workaround.md#L35-L39)
- Encoding/decoding helpers and `_contentEncoded` marker: [backend/docs/cosmos-emulator-unicode-workaround.md](../../../../backend/docs/cosmos-emulator-unicode-workaround.md#L41-L88)
- Explicit scope is only `refs[*].content` and only when the flag is true: [backend/docs/cosmos-emulator-unicode-workaround.md](../../../../backend/docs/cosmos-emulator-unicode-workaround.md#L105-L120)

Practical implication:

- Emulator-specific behavior is controlled through settings flags and is intentionally scoped to the minimum necessary.
- Any emulator subclass approach should respect and reuse these flags rather than introducing a second, parallel flag.

## Settings / Flag Conventions Relevant to Emulator and Backend Selection

- Settings use `GTC_` prefix and load env defaults from `environments/sample.env`: [backend/app/core/config.py](../../../../backend/app/core/config.py#L11-L21)
- Backend selection is via `REPO_BACKEND` (memory|cosmos): [backend/app/core/config.py](../../../../backend/app/core/config.py#L31-L34)
- Emulator-related flags:
  - `USE_COSMOS_EMULATOR`: [backend/app/core/config.py](../../../../backend/app/core/config.py#L41-L46)
  - `COSMOS_CONNECTION_VERIFY` (self-signed cert): [backend/app/core/config.py](../../../../backend/app/core/config.py#L44-L49)
  - `COSMOS_DISABLE_UNICODE_ESCAPE`: [backend/app/core/config.py](../../../../backend/app/core/config.py#L47-L52)
  - `COSMOS_TEST_MODE` (don’t init cosmos in lifespan): [backend/app/core/config.py](../../../../backend/app/core/config.py#L49-L53), [backend/app/main.py](../../../../backend/app/main.py#L58-L69)

## Style / Misc. Engineering Conventions

- Timestamp updates should use UTC: [backend/.github/copilot-instructions.md](../../../../backend/.github/copilot-instructions.md#L1)
- Prefer built-in generics (`dict`, `list`) over `typing.Dict`/`typing.List`: [backend/.github/copilot-instructions.md](../../../../backend/.github/copilot-instructions.md#L2)

## Guidance for the Planned Refactor

### Moving logic from repos/API into services

Repository conventions support:

- Keeping repo operations storage-centric and state-agnostic when appropriate, with state validation in services: [backend/docs/assign-single-item-endpoint.md](../../../../backend/docs/assign-single-item-endpoint.md#L78-L87)
- Using the singleton container to expose services (as already done for snapshots): [backend/app/api/v1/ground_truths.py](../../../../backend/app/api/v1/ground_truths.py#L135-L151)

Suggested “shape” aligned with conventions:

- Add/extend a service in `backend/app/services/*_service.py`
- Wire it on the container in `init_cosmos_repo()` so it gets the active repo
- Update routers to call the service

### Introducing a Cosmos emulator subclass (interpretation)

No doc explicitly mandates “subclassing,” but the repo has a clear convention of environment-conditional paths:

- Internal switching inside the Cosmos repo based on `is_cosmos_emulator_in_use()`: [backend/app/adapters/repos/cosmos_repo.py](../../../../backend/app/adapters/repos/cosmos_repo.py#L639-L641)
- `assign_to()` explicitly uses two implementations (patch vs read-modify-replace) selected at runtime: [backend/app/adapters/repos/cosmos_repo.py](../../../../backend/app/adapters/repos/cosmos_repo.py#L1719-L1737)

If you introduce a subclass, it should fit the existing composition pattern:

- The selection should happen in container wiring (e.g., `init_cosmos_repo()`), not in routers.
- The emulator-specific class should still implement the same `GroundTruthRepo` protocol.
- It should retain the fail-soft startup posture (emulator might not be ready).

A minimal-risk alternative consistent with existing code:

- Keep a single `CosmosGroundTruthRepo` and add conditional internal branches for emulator-only incompatibilities (the existing pattern).

## Notes / Gaps

- There is no explicit “ports/adapters hexagonal architecture” guidance beyond the documented folder layout and the `GroundTruthRepo` protocol.
- Observability docs are extensive but not directly prescriptive for repo/service refactors, except indirectly (fail-soft + structured logging patterns).
