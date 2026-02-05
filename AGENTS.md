# Agent Instructions

## Testing and Build Commands

### Backend (Python with uv)

```bash
cd backend

# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific test file
uv run pytest tests/unit/test_dos_prevention.py -v

# Run tests matching keyword
uv run pytest tests/unit/ -k "bulk" -v

# Type checking (uses 'ty' not mypy)
uv run ty check app/  # Check entire app directory
uv run ty check app/api/v1/ground_truths.py  # Check specific file
```

### Frontend (Node.js)

```bash
cd frontend

# Run unit tests once (preferred for automation/agents)
# Note: Vitest 3.2.4 doesn't support `--no-threads` at runtime; use the threads pool in single-thread mode to avoid spawning many Node processes.
npm run test:run -- --pool=threads --poolOptions.threads.singleThread

# Pre-commit validation (lint + typecheck, no auto-fix)
npm run pre-commit

# Build
npm run build

# Type checking (note: 'typecheck' not 'type-check')
npm run typecheck

# Linting (auto-fix)
npm run lint

# Linting check only (no auto-fix)
npm run lint:check
```

## Documentation

```bash
# Build documentation site
cd backend
uv run mkdocs build -f ../mkdocs.yml

# Serve documentation locally
cd backend
uv run mkdocs serve -f ../mkdocs.yml
# Then open http://localhost:8000
```

## Cosmos DB Operations

### Indexing Policy Updates

To update the Cosmos DB indexing policy:

```bash
cd backend/scripts

# For local emulator
python cosmos_container_manager.py update-gt \
  --endpoint https://localhost:8081 \
  --indexing-policy indexing-policy-optimized.json

# For production (requires connection string)
python cosmos_container_manager.py update-gt \
  --connection-string "$COSMOS_CONNECTION_STRING" \
  --indexing-policy indexing-policy-optimized.json
```

**Note**: Reindexing takes 1-6 hours depending on data size. Monitor progress in Azure Portal or via SDK.

See `docs/operations/COSMOS-OPTIMIZATION-README.md` for detailed deployment guide.

### Query Performance Monitoring

To enable RU cost tracking and query performance monitoring:

```bash
# Enable all query metrics logging
export GTC_COSMOS_LOG_QUERY_METRICS=true
export GTC_COSMOS_LOG_SLOW_QUERIES_ONLY=false

# Enable only slow query logging (RU >= 10.0)
export GTC_COSMOS_LOG_QUERY_METRICS=true
export GTC_COSMOS_LOG_SLOW_QUERIES_ONLY=true
export GTC_COSMOS_SLOW_QUERY_RU_THRESHOLD=10.0
```

Metrics are logged with structured fields:

- `operation`: Operation name (e.g., "stats.count_all_items", "list_gt_paginated.direct_query")
- `ru_charge`: Request Units consumed
- `item_count`: Number of items returned
- `elapsed_ms`: Query execution time in milliseconds
- `query`: First 200 characters of SQL query

**Note**: Disabled by default to minimize log volume. Enable in staging/production for profiling.
