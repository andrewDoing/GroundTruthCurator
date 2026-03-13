<!-- markdownlint-disable-file -->
<!-- markdown-table-prettify-ignore-start -->
# RAG Workflow Current State - Product Requirements Document (PRD)
Version 1.0 | Status BASELINE | Owner TBD | Team Ground Truth Curator | Target Current Production Behavior | Lifecycle Current State

## Progress Tracker
| Phase | Done | Gaps | Updated |
|-------|------|------|---------|
| Context | ✅ | — | 2026-03-11 |
| Problem & Users | ✅ | — | 2026-03-11 |
| Scope | ✅ | — | 2026-03-11 |
| Requirements | ✅ | Minor source conflicts noted in Open Questions | 2026-03-11 |
| Metrics & Risks | ✅ | Live metric baselines need owner confirmation | 2026-03-11 |
| Operationalization | ✅ | Environment-specific details remain deployment-specific | 2026-03-11 |
| Finalization | 🔶 | Stakeholder review pending | 2026-03-11 |
Unresolved Critical Questions: 3 | TBDs: 3

## 1. Executive Summary
### Context
Ground Truth Curator currently operates a RAG-oriented curation workflow. Curators receive or claim work items, inspect generated question-and-answer content, search for and attach supporting references, edit content and metadata, and approve items once grounding requirements are satisfied.

This document captures the **current-state** product behavior at a high level so future work can preserve proven workflow expectations, identify intentional deltas, and avoid introducing regressions while adjacent initiatives evolve.

### Core Opportunity
Provide a single baseline artifact that explains what the RAG workflow already does today across assignment, search, editing, reference management, approval, and export so product, engineering, and operations teams can align on incumbent behavior.

### Goals
| Goal ID | Statement | Type | Baseline | Target | Timeframe | Priority |
|---------|-----------|------|----------|--------|-----------|----------|
| G-001 | Preserve the existing assignment-based curation workflow for RAG items | Product | Behavior spread across code and specs | Single documented baseline | Current state | P0 |
| G-002 | Preserve reference-grounded approval quality gates | Quality | Implemented in current workflow | Baseline documented and testable | Current state | P0 |
| G-003 | Preserve support for single-turn and multi-turn curation flows where currently supported | Product | Implemented in current workflow | Baseline documented and testable | Current state | P1 |
| G-004 | Preserve approved-item export and downstream dataset handoff behavior | Operational | Implemented in current workflow | Baseline documented and testable | Current state | P1 |
| G-005 | Preserve optimistic concurrency and assignment ownership protections | Technical | Implemented in current workflow | Baseline documented and testable | Current state | P0 |

### Objectives (Optional)
| Objective | Key Result | Priority | Owner |
|-----------|------------|----------|-------|
| Baseline the workflow | One current-state PRD covers assignment, curation, references, approval, export, and constraints | P0 | TBD |
| Reduce ambiguity | Current-state requirements can be traced to repo specs and implementation | P0 | TBD |
| Support safe future change | Future PRDs can diff against this baseline instead of inferring behavior from scattered docs | P1 | TBD |

## 2. Problem Definition
### Current Situation
The RAG workflow already exists in production-oriented code and repo specifications, but the behavior is described across multiple surfaces: backend APIs, frontend component flows, specs, implementation notes, and operational documentation. Teams can understand pieces of the system, but there is no single current-state PRD that explains the workflow end to end.

### Problem Statement
Without a current-state PRD, future changes risk misrepresenting incumbent behavior, weakening approval or reference-quality guarantees, or changing workflow expectations for curators and downstream dataset consumers.

### Root Causes
* Workflow expectations are distributed across backend, frontend, and spec artifacts rather than consolidated in one baseline document
* Some repo documents mix implemented behavior with future-oriented ideas, creating ambiguity about what is live today
* Current-state quality gates and workflow dependencies are easier to infer from code than from a single product artifact

### Impact of Inaction
* Future initiatives may accidentally regress core RAG curation behavior
* Product and engineering teams may debate current-state behavior from incomplete evidence
* Downstream consumers may not have a stable description of what an approved RAG item guarantees

## 3. Users & Personas
| Persona | Goals | Pain Points | Impact |
|---------|-------|------------|--------|
| **Curator / SME** | Review assigned items efficiently, edit content, add grounded references, and approve high-quality RAG entries | Workflow rules live across UI behavior and validation logic; approval expectations can be misunderstood | Primary user of the curation workflow |
| **Curation Lead** | Monitor work queues, throughput, and data quality expectations | Needs clarity on assignment, approval, and export semantics | Operational owner of workflow quality |
| **ML / Evaluation Engineer** | Consume approved snapshots for downstream evaluation and benchmarking | Needs confidence that approved items satisfy consistent grounding rules | Downstream consumer of approved datasets |
| **Platform Engineer** | Maintain APIs, storage, and deployment behavior without breaking workflow contracts | Current-state expectations are spread across code and docs | Maintains the workflow implementation |

### Journeys (Optional)
1. A curator requests or receives assignments from the queue.
2. The curator opens an item in the editing workspace.
3. The curator reviews question/answer content and, where supported, multi-turn history.
4. The curator searches for references, attaches relevant sources, visits them, and records key excerpts.
5. The curator updates tags or other metadata, saves changes, and resolves validation gaps.
6. The curator approves, skips, deletes, restores, or exports items according to workflow state.

## 4. Scope
### In Scope
* Current-state RAG workflow from assignment through approval and export
* Current user-facing workflow expectations in queue, editor, and reference-management surfaces
* Current backend expectations for ownership, optimistic concurrency, and snapshot export
* Current data and provenance behaviors that influence approval quality and downstream consumption
* Current non-functional expectations directly coupled to workflow integrity

### Out of Scope (justify if empty)
* New future-state feature ideation not supported by current repo evidence
* Agentic-mode workflow requirements
* Infrastructure redesign beyond what is necessary to describe current workflow dependencies
* Implementation-level code structure details that do not materially change workflow behavior

### Assumptions
* The current workflow remains centered on RAG ground-truth curation rather than agentic trace review
* Assignments and approved exports remain the primary operating model for curator throughput
* The present system continues to rely on optimistic concurrency and assignment ownership for safe writes
* Optional integrations such as Azure AI Search may vary by environment, while the baseline workflow remains reference-grounded

### Constraints
* Approval behavior must preserve current reference-quality gates
* Assignment mutations must preserve ownership expectations and concurrency protections
* Approved-item export must remain consistent enough for downstream consumers to ingest snapshots
* Current-state requirements should describe what the system already does, not prescribe speculative redesign

## 5. Product Overview
### Value Proposition
The current RAG workflow gives curators a structured way to convert candidate items into approved, reference-grounded ground truth. It combines queue management, editor tooling, reference search and annotation, validation, and export into a single curation loop intended to maintain quality and provenance.

### Differentiators (Optional)
* Assignment-based work acquisition instead of unmanaged item browsing alone
* Reference-grounded approval gates that require evidence, not only content edits
* Support for both baseline Q/A editing and broader conversation-history handling where the current implementation supports it
* Snapshot export that turns approved curation results into downstream-consumable artifacts

### UX / UI (Conditional)
The current workflow is organized around three major user-facing areas:

* **Queue / assignment surface** for requesting, browsing, and opening work items
* **Curation editor** for editing item content, metadata, and status
* **Reference management surface** for searching, selecting, visiting, and annotating grounding sources

UX Status: Implemented current-state workflow with known doc ambiguities around some advanced search behaviors

## 6. Functional Requirements
| FR ID | Title | Description | Goals | Personas | Priority | Acceptance | Notes |
|-------|-------|------------|-------|----------|----------|-----------|-------|
| FR-001 | Self-serve assignment queue | The system shall support an assignment-based workflow where a curator can request items and receive work from a queue rather than relying only on freeform browsing. | G-001 | Curator / SME; Curation Lead | P0 | A curator can obtain assigned work items through the current assignment flow and view their assigned queue. | Source baseline: assignment workflow specs and assignment API/service surfaces |
| FR-002 | Assignment ownership protection | The system shall preserve ownership rules for assigned draft work so one curator cannot silently overwrite another curator's active assignment. | G-005 | Curator / SME; Platform Engineer | P0 | Write attempts that violate assignment ownership are rejected with stable error handling. | Current-state behavior is coupled to assignment mutations and approval/update flows |
| FR-003 | Curation workspace | The system shall provide a curation workspace that lets a curator inspect and edit the current item's answer content, related metadata, and workflow status. | G-001 | Curator / SME | P0 | A curator can open an assigned item, make edits, and save or transition workflow state. | Baseline from current frontend curation surfaces |
| FR-004 | Multi-turn support where available | The system shall preserve current support for both traditional question/answer items and conversation-history editing where the current implementation supports multi-turn behavior. | G-003 | Curator / SME; ML / Evaluation Engineer | P1 | Current supported item shapes remain editable without breaking single-turn behavior. | Current repo evidence shows compatibility for multi-turn flows while preserving legacy shapes |
| FR-005 | Reference search and selection | The system shall support searching for references and attaching selected references to the item under curation. | G-002 | Curator / SME | P0 | A curator can search for candidate references and add them to the curated item. | Search capability may vary by backend/provider, but the workflow expectation is present |
| FR-006 | Reference visitation and key excerpts | The system shall track whether selected references were visited and capture key supporting excerpts that justify approval. | G-002 | Curator / SME; ML / Evaluation Engineer | P0 | Selected references can be visited and annotated with supporting excerpt content before approval. | Current workflow emphasizes visited state and minimum excerpt quality |
| FR-007 | Approval gating by reference completeness | The system shall prevent approval unless the item satisfies current grounding rules, including having at least one selected reference and meeting current visitation and excerpt completeness requirements. | G-002 | Curator / SME; Curation Lead | P0 | Items that do not satisfy current reference gates cannot be approved. | This is a defining quality invariant of the current workflow |
| FR-008 | Tag and metadata management | The system shall support curator-managed metadata updates, including tags, while preserving current normalization and computed-tag behavior. | G-001 | Curator / SME; Platform Engineer | P1 | Curators can manage supported metadata and stored tag values remain normalized and stable. | Tag semantics are part of the current curation loop and downstream data quality |
| FR-009 | Workflow state transitions | The system shall support current state transitions such as save draft, approve, skip, soft delete, and restore according to current workflow rules. | G-001; G-005 | Curator / SME; Curation Lead | P0 | A curator can perform supported workflow actions and the resulting item state is persisted consistently. | Current workflow includes soft-delete and restore rather than destructive removal |
| FR-010 | Snapshot export | The system shall support exporting approved items as snapshots suitable for downstream dataset consumption. | G-004 | ML / Evaluation Engineer; Curation Lead | P1 | Approved data can be exported using the current snapshot workflow and results are consumable downstream. | Current-state export supports attachment-oriented and artifact-oriented patterns |
| FR-011 | Explorer and filtering | The system shall allow users to browse existing items using the current set of supported filters, including status, dataset, tags, and other implemented search constraints. | G-001 | Curator / SME; Curation Lead | P1 | Users can narrow visible items with currently supported filters without changing assignment semantics. | Some advanced filtering ideas remain future-oriented or partially documented |
| FR-012 | Concurrency-safe updates | The system shall preserve optimistic concurrency on item updates so users do not unknowingly overwrite newer changes. | G-005 | Curator / SME; Platform Engineer | P0 | Updates require the latest concurrency token and return a conflict on stale writes. | Current state uses ETags as the primary concurrency contract |

### Feature Hierarchy (Optional)
```plain
RAG Workflow
|- Assignment and queue management
|  |- Self-serve assignment
|  |- Assigned queue view
|  |- Ownership enforcement
|- Curation workspace
|  |- Item editing
|  |- Multi-turn compatibility
|  |- Tags and metadata
|  |- State transitions
|- Reference workflow
|  |- Search
|  |- Selection
|  |- Visit tracking
|  |- Key excerpt capture
|  |- Approval gating
|- Export and downstream handoff
   |- Snapshot export
   |- Approved item consumption
```

## 7. Non-Functional Requirements
| NFR ID | Category | Requirement | Metric/Target | Priority | Validation | Notes |
|--------|----------|------------|--------------|----------|-----------|-------|
| NFR-001 | Reliability | The system shall expose a healthy backend service state suitable for operational checks before curation begins. | Health endpoint responds successfully in healthy environments | P1 | Operational smoke checks | Current backend baseline includes health checking |
| NFR-002 | Concurrency | The system shall use optimistic concurrency controls on mutable workflows. | Stale writes are rejected rather than silently accepted | P0 | API conflict tests and manual verification | Directly protects curator work from accidental overwrite |
| NFR-003 | Usability | Approval rules shall be visible through user-facing validation behavior rather than hidden post-submit failures alone. | Curators can identify unmet approval conditions before approval succeeds | P0 | UI validation and approval-path testing | Current workflow relies on explicit approval gates |
| NFR-004 | Data Integrity | Tag storage and comparable metadata shall remain normalized and deterministic. | Stable normalized values across repeated save/read cycles | P1 | Unit tests and data round-trip checks | Supports downstream consistency |
| NFR-005 | Provenance | Approved items shall retain reference provenance sufficient to explain grounding decisions. | Approved items preserve selected references and supporting excerpts | P0 | Export review and API payload inspection | Central to RAG quality expectations |
| NFR-006 | Compatibility | The system shall accept supported input naming conventions while preserving stable output contracts for clients. | Current API payload contract remains interoperable with existing clients | P1 | API integration tests | Current backend behavior accepts variant casing and emits stable wire output |
| NFR-007 | Security | The system shall preserve assignment ownership semantics and current user attribution behavior. | Mutations remain attributable to the acting user and ownership checks stay enforced | P1 | Assignment mutation tests | Production auth may vary by environment; dev simulation remains supported |
| NFR-008 | Observability | The system should preserve safe-by-default observability behavior so telemetry is opt-in and non-blocking where configured. | Workflow remains usable with telemetry disabled or absent | P2 | Environment smoke tests | Current frontend observability pattern is intentionally safe by default |

Categories: Performance, Reliability, Scalability, Security, Privacy, Accessibility, Observability, Maintainability, Localization (if), Compliance (if).

## 8. Data & Analytics (Conditional)
### Inputs
* Candidate RAG ground-truth items entering the curation workflow
* Reference search queries and selected reference metadata
* Curator edits to answers, history, tags, and workflow status
* User identity or simulated user headers used for assignment attribution

### Outputs / Events
* Updated item state, assignment state, and review metadata
* Approved snapshots for downstream dataset use
* Optional telemetry or operational traces when enabled

### Instrumentation Plan
| Event | Trigger | Payload | Purpose | Owner |
|-------|---------|--------|---------|-------|
| Assignment requested | Curator requests work | User, count, dataset context | Measure queue usage | TBD |
| Item updated | Curator saves changes | Item id, user, status, concurrency outcome | Measure edit/save behavior | TBD |
| Approval attempted | Curator attempts approval | Item id, validation outcome | Measure quality-gate friction | TBD |
| Snapshot exported | User exports approved set | Dataset, mode, count | Measure downstream handoff | TBD |

### Metrics & Success Criteria
| Metric | Type | Baseline | Target | Window | Source |
|--------|------|----------|--------|--------|--------|
| Approval success rate after validation | Workflow quality | TBD | Monitor current state | Rolling | App/API telemetry or logs |
| Average assignment-to-approval time | Operational | TBD | Monitor current state | Rolling | Assignment and review timestamps |
| Reference completeness failure rate | Quality | TBD | Monitor current state | Rolling | Approval validation results |
| Export success rate | Operational | TBD | Monitor current state | Rolling | Export logs or API results |

## 9. Dependencies
| Dependency | Type | Criticality | Owner | Risk | Mitigation |
|-----------|------|------------|-------|------|-----------|
| Repository-backed assignment and item storage | Data platform | High | TBD | Workflow breaks if reads/writes fail | Preserve repository abstractions and operational checks |
| Reference search capability/provider | Search | High | TBD | Curators cannot attach supporting evidence efficiently | Keep baseline provider behavior or an acceptable fallback |
| Frontend curation workspace | Product surface | High | TBD | Curators cannot edit or approve items | Preserve core editor flows and integration tests |
| Snapshot export path | Downstream integration | Medium | TBD | Approved data cannot be handed off reliably | Preserve export contract and smoke-test it |
| Identity / user attribution | Security / operations | Medium | TBD | Assignment ownership and auditing weaken | Preserve current auth or simulation mechanisms per environment |

## 10. Risks & Mitigations
| Risk ID | Description | Severity | Likelihood | Mitigation | Owner | Status |
|---------|-------------|---------|-----------|-----------|-------|--------|
| R-001 | Future changes weaken approval grounding rules | High | Medium | Treat FR-006 and FR-007 as regression-sensitive requirements | TBD | Open |
| R-002 | Search-related docs and implementation drift further apart | Medium | Medium | Use this PRD as the baseline and resolve documented open questions | TBD | Open |
| R-003 | Workflow changes bypass optimistic concurrency or ownership checks | High | Low | Preserve ETag and ownership tests on all write paths | TBD | Open |
| R-004 | Export changes break downstream consumers silently | Medium | Medium | Preserve snapshot contract and verify against representative consumers | TBD | Open |

## 11. Privacy, Security & Compliance
### Data Classification
The workflow manages curated dataset content, references, tags, and user-attribution metadata. Exact data classification depends on the dataset and deployment environment.

### PII Handling
Current repo evidence shows support for user attribution and PII-related service surfaces, but this document does not expand beyond the existing current-state workflow baseline.

### Threat Considerations
* Unauthorized or conflicting writes must be prevented through ownership and concurrency checks
* Evidence and export data should preserve integrity during curation and handoff
* Environment-specific authentication must not undermine assignment semantics

### Regulatory / Compliance (Conditional)
| Regulation | Applicability | Action | Owner | Status |
|-----------|--------------|--------|-------|--------|
| TBD | Environment-specific | Confirm per deployment | TBD | Open |

## 12. Operational Considerations
| Aspect | Requirement | Notes |
|--------|------------|-------|
| Deployment | The workflow shall remain deployable in local and hosted environments supported by the existing repo | Current repo supports local development plus Azure-oriented deployment patterns |
| Rollback | Changes affecting assignment, approval, or export should be rollbackable without data-loss surprises | Preserve current contracts before rolling out workflow changes |
| Monitoring | Operators should be able to confirm service health and core workflow readiness | Health and optional telemetry patterns already exist |
| Alerting | Critical workflow failures should surface through existing operational channels | Environment-specific implementation may vary |
| Support | Support teams need a clear baseline of current-state behavior when triaging workflow issues | This PRD is intended to be that baseline |
| Capacity Planning | Capacity depends on dataset size, search provider behavior, and curator throughput | Current-state PRD does not redefine platform sizing |

## 13. Rollout & Launch Plan
### Phases / Milestones
| Phase | Date | Gate Criteria | Owner |
|-------|------|--------------|-------|
| Current-state baseline authored | 2026-03-11 | PRD created and source-backed | Copilot / TBD |
| Stakeholder review | TBD | Product and engineering confirm baseline accuracy | TBD |
| Baseline adoption | TBD | Future PRDs reference this document for delta analysis | TBD |

### Feature Flags (Conditional)
| Flag | Purpose | Default | Sunset Criteria |
|------|---------|--------|----------------|
| Demo / mock provider configuration | Support non-production workflows where enabled | Environment-specific | Remains as long as demo workflows are supported |
| Optional telemetry configuration | Enable observability without making it mandatory | Disabled unless configured | Remains environment-specific |

### Communication Plan (Optional)
Share this baseline PRD with product, frontend, backend, and operations stakeholders before approving workflow changes that touch assignment, reference validation, or export behavior.

## 14. Open Questions
| Q ID | Question | Owner | Deadline | Status |
|------|----------|-------|---------|--------|
| Q-001 | Should reference search be treated as universally required current-state capability, or is provider-backed search optional in some environments? | TBD | TBD | Open |
| Q-002 | Which advanced filter behaviors are truly current state versus future-oriented specs? | TBD | TBD | Open |
| Q-003 | Are dataset-level curation instructions part of the baseline workflow everywhere or only in specific flows? | TBD | TBD | Open |

## 15. Changelog
| Version | Date | Author | Summary | Type |
|---------|------|-------|---------|------|
| 1.0 | 2026-03-11 | Copilot | Created current-state baseline PRD for the RAG workflow from repo evidence | Added |

## 16. References & Provenance
| Ref ID | Type | Source | Summary | Conflict Resolution |
|--------|------|--------|---------|--------------------|
| REF-001 | Spec | `specs/assignment-workflow.md` | Assignment-centric curation workflow and self-serve queue behavior | Used as assignment baseline |
| REF-002 | Spec | `specs/explorer-view.md` | Explorer and filter expectations for current browsing workflow | Open question retained for advanced filters |
| REF-003 | Spec | `specs/curation-editor.md` | Editor expectations for curation actions and item editing | Used as curation workspace baseline |
| REF-004 | Spec | `specs/reference-management.md` | Reference search, selection, visitation, and excerpt behavior | Used as evidence workflow baseline |
| REF-005 | Spec | `specs/export-snapshots.md` | Snapshot export patterns and downstream handoff behavior | Used as export baseline |
| REF-006 | Spec | `specs/data-persistence.md` | Data, persistence, and workflow write expectations | Used as storage/concurrency support |
| REF-007 | Codebase guide | `frontend/CODEBASE.md` | Frontend workflow surfaces, validation cues, and user interactions | Used when summarizing UX baseline |
| REF-008 | Codebase guide | `backend/CODEBASE.md` | Backend API and data contract expectations | Used for API and platform baseline |
| REF-009 | API/service implementation | `backend/app/api/v1/assignments.py`, `backend/app/api/v1/ground_truths.py`, `backend/app/services/assignment_service.py` | Concrete assignment, state transition, and workflow behavior | Used to anchor current-state implementation claims |
| REF-010 | Research note | `.copilot-tracking/research/20260121-high-level-requirements-research.md` | Prior repo-backed requirements synthesis | Used as supporting consolidation evidence |

### Citation Usage
This PRD intentionally describes **current-state** behavior only. Where repo artifacts disagree or mix implemented and planned behavior, the more conservative interpretation was used and the ambiguity was captured in Open Questions rather than resolved by speculation.

## 17. Appendices (Optional)
### Glossary
| Term | Definition |
|------|-----------|
| RAG | Retrieval-Augmented Generation workflow centered on grounded references |
| Curator / SME | User responsible for reviewing, editing, and approving ground-truth items |
| Reference | Supporting external source attached to an item to justify grounding |
| Snapshot export | Exported representation of approved items for downstream consumption |
| Optimistic concurrency | Update safety model that rejects stale writes instead of silently overwriting |

### Additional Notes
This document is intentionally a **baseline PRD** for incumbent behavior. It should be used to compare future changes, not as evidence that every adjacent idea in repo docs is currently implemented.

Generated 2026-03-11T12:34:07Z by Copilot (mode: full)
<!-- markdown-table-prettify-ignore-end -->
