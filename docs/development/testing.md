# Testing Guide

This guide covers testing strategies and practices for Ground Truth Curator.

## Backend Testing

The backend uses pytest for unit and integration testing.

### Running Tests

```bash
cd backend

# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific test file
uv run pytest tests/unit/test_dos_prevention.py -v

# Run tests matching keyword
uv run pytest tests/unit/ -k "bulk" -v

# Run with coverage
uv run pytest tests/unit/ --cov=app --cov-report=html
```

### Test Structure

```
backend/tests/
├── unit/              # Unit tests
│   ├── test_*.py      # Test files
│   └── conftest.py    # Shared fixtures
└── integration/       # Integration tests
    ├── test_*.py
    └── conftest.py
```

### Writing Tests

Example unit test:

```python
import pytest
from app.services.validation_service import ValidationService

def test_validate_tags_rejects_invalid():
    service = ValidationService()
    result = service.validate_tags(["invalid:tag"])
    assert not result.is_valid
    assert len(result.errors) > 0
```

Example integration test:

```python
from fastapi.testclient import TestClient
from app.main import app

def test_bulk_import_endpoint(client: TestClient):
    response = client.post(
        "/api/v1/ground-truths",
        json=[{"question": "Test?", "answer": "Answer"}]
    )
    assert response.status_code == 200
```

### Type Checking

The backend uses `ty` (not mypy) for type checking:

```bash
uv run ty check app/api/v1/ground_truths.py
```

## Frontend Testing

The frontend uses Vitest and React Testing Library.

### Running Tests

```bash
cd frontend

# Run tests in watch mode
npm test

# Run tests once
npm test -- --run

# Run with coverage
npm test -- --coverage
```

### Test Structure

```
frontend/tests/
├── unit/              # Unit tests
│   ├── components/    # Component tests
│   ├── hooks/         # Hook tests
│   ├── services/      # Service tests
│   └── utils/         # Utility tests
└── integration/       # Integration tests
```

### Writing Tests

Example component test:

```typescript
import { render, screen } from '@testing-library/react';
import { TagChip } from '@/components/common/TagChip';

test('renders tag name', () => {
  render(<TagChip tag="source:synthetic" />);
  expect(screen.getByText('source:synthetic')).toBeInTheDocument();
});
```

Example hook test:

```typescript
import { renderHook } from '@testing-library/react';
import { useTagGlossary } from '@/hooks/useTagGlossary';

test('loads tag glossary', async () => {
  const { result } = renderHook(() => useTagGlossary());
  await waitFor(() => {
    expect(result.current.glossary).toBeDefined();
  });
});
```

### Type Checking

```bash
npm run typecheck
```

### Build Verification

```bash
npm run build
```

## Integration Testing Strategy

### Backend Integration Tests

- Test with Cosmos DB emulator when available
- Fall back to mock repository for CI
- Test full request/response cycle
- Verify authentication and authorization

### Frontend Integration Tests

- Test user workflows end-to-end
- Mock API responses with MSW
- Test error handling
- Verify accessibility

## Continuous Integration

The CI pipeline runs:

1. **Backend tests**: Unit and integration tests
2. **Frontend tests**: Unit tests with coverage
3. **Type checking**: Backend (ty) and frontend (tsc)
4. **Build verification**: Frontend build
5. **OpenAPI validation**: Schema validation

See `.github/workflows/gtc-ci.yml` for details.

## Test Coverage Goals

- **Backend**: Maintain >80% coverage for business logic
- **Frontend**: Maintain >70% coverage for components and hooks
- **Critical paths**: 100% coverage for security and data integrity

## Best Practices

### Unit Tests
- Test one thing at a time
- Use descriptive test names
- Keep tests independent
- Mock external dependencies

### Integration Tests
- Test realistic scenarios
- Use test fixtures for setup
- Clean up after tests
- Test error conditions

### Performance Tests
- Profile slow tests
- Use test.skip() for slow tests that don't need to run always
- Consider separate performance test suite

## Debugging Tests

### Backend
```bash
# Run with print statements visible
uv run pytest tests/unit/test_file.py -v -s

# Run with debugger
uv run pytest tests/unit/test_file.py --pdb
```

### Frontend
```bash
# Debug in watch mode
npm test

# Debug specific test
npm test -- path/to/test.tsx
```

## Common Issues

### Backend

**Import errors**: Ensure `pythonpath = ["."]` in pytest.ini_options

**Async test failures**: Use `@pytest.mark.asyncio` decorator

### Frontend

**Act warnings**: Wrap state updates in `act()`

**Mock issues**: Ensure mocks are reset between tests

**Type errors**: Regenerate types with `npm run generate:api`
