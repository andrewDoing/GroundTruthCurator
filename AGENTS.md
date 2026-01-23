# Agent Instructions

## Version Control Workflow (Jujutsu)

This repository uses [Jujutsu (jj)](https://martinvonz.github.io/jj/) for version control. Follow this workflow when making changes.

### Before Making Changes

1. Check if the current commit is empty:

   ```bash
   jj log --no-pager --limit 1
   ```

   If the commit is empty, set a descriptive commit message:

   ```bash
   jj describe -m "initial commit description"
   ```

2. If the commit is not empty, create a new commit for your changes:

   ```bash
   jj new -m "description of the change"
   ```

3. Verify you are working on the new commit:

   ```bash
   jj log --no-pager --limit 5
   ```

### Making Changes

- Make all necessary code changes within this workspace.
- Use `jj status` to review uncommitted changes
- Use `jj diff --no-pager` to see what has changed
- Use `--no-pager` with commands that may open a pager, such as `jj log` and `jj diff`

### After Completing Changes

1. Update the commit description if needed:

   ```bash
   jj describe -m "final description of changes"
   ```

2. Prompt the user before advancing the main bookmark:

   > ⚠️ **User Action Required**
   >
   > Changes are complete. Please review the changes:
   >
   > ```bash
   > jj log --no-pager --limit 5
   > jj diff --no-pager -r @
   > ```
   >
   > If you are satisfied with the changes, move the main bookmark forward:
   >
   > ```bash
   > jj bookmark set main -r @
   > ```
   >
   > Or if you need to make additional changes, do so now before advancing the bookmark.

### Important Notes

- Never automatically move the main bookmark, always prompt the user first
- Keep commits atomic and focused on a single logical change
- Write clear, descriptive commit messages

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
uv run ty check app/api/v1/ground_truths.py
```

### Frontend (Node.js)

```bash
cd frontend

# Run unit tests once (preferred for automation/agents)
# Note: Vitest 3.2.4 doesn't support `--no-threads` at runtime; use the threads pool in single-thread mode to avoid spawning many Node processes.
npm run test:run -- --pool=threads --poolOptions.threads.singleThread

# Build
npm run build

# Type checking (note: 'typecheck' not 'type-check')
npm run typecheck
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
