---
title: Observability and Operations
description: The observability and operations system provides opt-in telemetry, error handling, and health status.
jtbd: JTBD-001
author: spec-builder
ms.date: 2026-01-22
status: draft
---

# Observability and Operations

## Overview

The observability and operations system provides opt-in telemetry, error handling, and health status.

**Parent JTBD:** Help curators review and approve ground-truth data items through an assignment-based workflow

## Problem Statement

Operators and developers need visibility into system health, errors, and usage patterns, while ensuring telemetry is opt-in and safe-by-default to avoid leaking data in demo or unconfigured environments.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-001 | The backend shall expose a health endpoint at `GET /healthz` | Must | Endpoint returns repository and backend status |
| FR-002 | Client telemetry shall be opt-in and disabled by default | Must | No telemetry is sent unless explicitly configured |
| FR-003 | Client telemetry shall no-op safely in demo mode or when configuration is missing | Must | Missing config does not cause errors |
| FR-004 | The UI shall provide an error boundary that catches rendering errors | Must | Rendering failures show a user-friendly fallback |
| FR-005 | The error boundary may integrate with telemetry when enabled | Should | Errors are logged to telemetry if configured |

### Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Privacy | Telemetry shall not transmit PII unless explicitly configured | Default config excludes PII |
| NFR-002 | Reliability | Health endpoint shall respond even when storage is degraded | Returns partial status |

## User Stories

### US-001: Check System Health

**As an** operator
**I want to** call a health endpoint
**So that** I can monitor system status

**Acceptance Criteria:**
- [ ] Given the system is running, when I call `/healthz`, then I receive a status response
- [ ] Given storage is degraded, when I call `/healthz`, then I see degraded status in the response

### US-002: View Error Fallback

**As a** curator
**I want to** see a friendly error message when the UI crashes
**So that** I know something went wrong without seeing a blank screen

**Acceptance Criteria:**
- [ ] Given a rendering error occurs, when the error boundary catches it, then a fallback UI is displayed

### US-003: Enable Telemetry

**As an** operator
**I want to** enable telemetry by providing configuration
**So that** usage and errors are tracked in Application Insights

**Acceptance Criteria:**
- [ ] Given telemetry is configured, when events occur, then they are sent to the configured endpoint
- [ ] Given telemetry is not configured, when events occur, then no errors are thrown

## Technical Considerations

### Data Model

- Health response includes: `status`, `repoBackend`, `cosmosEndpoint` (masked), `timestamp`.
- Telemetry events include: `eventName`, `properties`, `measurements`.

### Integrations

| System | Purpose | Data Flow |
|--------|---------|-----------|
| Application Insights | Telemetry sink | Client SDK sends events |
| Backend health endpoint | Status check | HTTP GET |

### Constraints

- Demo mode disables telemetry regardless of configuration.
- Error boundary is a React component that wraps the application tree.

## Open Questions

(None)

## References

- [backend/app/main.py](../backend/app/main.py)
- [frontend/docs/OBSERVABILITY_IMPLEMENTATION.md](../frontend/docs/OBSERVABILITY_IMPLEMENTATION.md)
- [frontend/README.md](../frontend/README.md)
