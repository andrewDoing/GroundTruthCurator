# Architecture Overview

Ground Truth Curator follows a clean architecture pattern with clear separation between layers.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌────────────┐  ┌──────────┐  ┌─────────┐  ┌────────────┐ │
│  │ Components │  │  Hooks   │  │ Services│  │   Utils    │ │
│  └────────────┘  └──────────┘  └─────────┘  └────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API (HTTP/JSON)
┌──────────────────────────┴──────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                     API Layer                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐ │ │
│  │  │  Endpoints  │  │ Validation  │  │  Middleware   │ │ │
│  │  └─────────────┘  └─────────────┘  └───────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Service Layer                        │ │
│  │  ┌───────────┐ ┌────────────┐ ┌──────────────────────┐│ │
│  │  │Assignment │ │ Validation │ │  Duplicate Detection ││ │
│  │  │  Service  │ │  Service   │ │      Service         ││ │
│  │  └───────────┘ └────────────┘ └──────────────────────┘│ │
│  │  ┌───────────┐ ┌────────────┐ ┌──────────────────────┐│ │
│  │  │    PII    │ │   Search   │ │     Tag Registry     ││ │
│  │  │  Service  │ │  Service   │ │       Service        ││ │
│  │  └───────────┘ └────────────┘ └──────────────────────┘│ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Adapter Layer                         │ │
│  │  ┌──────────────┐  ┌──────────────┐                   │ │
│  │  │  Cosmos DB   │  │  Mock Repo   │                   │ │
│  │  │   Adapter    │  │   Adapter    │                   │ │
│  │  └──────────────┘  └──────────────┘                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Domain Layer                         │ │
│  │  ┌──────────┐  ┌────────┐  ┌─────────┐               │ │
│  │  │  Models  │  │  Enums │  │ Errors  │               │ │
│  │  └──────────┘  └────────┘  └─────────┘               │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   Data Storage                               │
│  ┌────────────────┐  ┌────────────────┐                     │
│  │   Cosmos DB    │  │  In-Memory     │                     │
│  │  (Production)  │  │  (Development) │                     │
│  └────────────────┘  └────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Architecture Principles

### 1. Separation of Concerns
- **API Layer**: HTTP concerns, request/response handling
- **Service Layer**: Business logic and orchestration
- **Adapter Layer**: External system integration
- **Domain Layer**: Core domain models and rules

### 2. Dependency Injection
- FastAPI's `Depends()` for request-scoped dependencies
- Container singleton for service instances
- Pydantic Settings for configuration

### 3. Repository Pattern
- Abstract base repository interface
- Multiple implementations (Cosmos, Mock)
- Easy testing and swapping data sources

### 4. Clean Data Flow
```
Request → Endpoint → Service → Adapter → Database
                ↓         ↓
            Validation  Business Logic
```

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: Azure Cosmos DB (Document store)
- **Package Manager**: uv
- **Testing**: pytest, pytest-asyncio
- **Type Checking**: ty
- **API Docs**: OpenAPI/Swagger

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **UI Library**: Material-UI
- **State Management**: React hooks
- **HTTP Client**: Custom fetch wrapper
- **Testing**: Vitest, React Testing Library

## Key Design Patterns

### Service Layer Pattern
All business logic lives in service classes:
- `AssignmentService` - Assignment workflow
- `ValidationService` - Data validation
- `DuplicateDetectionService` - Duplicate checking
- `PIIService` - PII detection
- `SearchService` - Search and filtering

### Adapter Pattern
External systems accessed through adapters:
- `CosmosRepoAdapter` - Cosmos DB access
- `MockRepoAdapter` - In-memory storage
- `GTCInferenceAdapter` - AI service integration

### Repository Pattern
Data access abstracted behind repository interface:
```python
class GroundTruthRepository(ABC):
    async def get(self, id: str) -> GroundTruth:
        ...
    async def create(self, item: GroundTruth) -> GroundTruth:
        ...
```

## Concurrency Control

### Optimistic Locking
- ETag-based concurrency control
- If-Match headers for updates
- Automatic conflict detection

### Assignment Atomicity
- Atomic patch operations for assignments
- Prevents double-assignment race conditions

## Security

### Authentication
- JWT-based authentication
- Role-based access control
- Claims-based authorization

### Input Validation
- Pydantic models for request validation
- Custom validators for complex rules
- Structured error responses

### Rate Limiting
- Per-endpoint rate limits
- Bulk operation size limits
- DoS prevention

## Observability

### Logging
- Structured logging with context
- Correlation IDs for request tracing
- Different log levels per environment

### Telemetry
- Azure Monitor integration
- OpenTelemetry instrumentation
- Performance metrics

### Health Checks
- `/healthz` endpoint
- Database connectivity checks
- Dependency status

## Learn More

- [Backend Architecture](backend.md)
- [Frontend Architecture](frontend.md)
- [Data Models](data-models.md)
