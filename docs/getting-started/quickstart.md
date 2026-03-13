# Quickstart

This guide will help you create your first ground truth item.

## Prerequisites

- Backend and frontend installed (see [Installation](installation.md))
- Environment configured (see [Configuration](configuration.md))

## Start the Backend

1. From the repository root, start the backend:
   ```bash
   make -f Makefile.harness backend
   ```

    The API will be available at `http://localhost:8000`.

2. Verify the backend is running:
   ```bash
   curl http://localhost:8000/healthz
   ```

## Start the Frontend

1. In a new terminal from the repository root, start the frontend:
   ```bash
   make -f Makefile.harness frontend
   ```

    The app will be available at `http://localhost:5173` by default.

    To run both services from one terminal instead, use `make -f Makefile.harness dev`.

    For agent-friendly background startup, use `make -f Makefile.harness dev-up` and later `make -f Makefile.harness dev-down`. Background logs and PID files are written to `.harness/dev/`.

    To launch the demo experience with seeded data and a fixed local user, run:

    ```bash
    VITE_DEMO_MODE=true VITE_DEV_USER_ID=demo-user make dev-up
    ```

    This starts both services in the background, enables demo mode in the frontend, and sets the backend demo user identity to `demo-user`.

## Create Your First Ground Truth Item

1. **Open the app**: Navigate to `http://localhost:5173` in your browser

2. **Browse items**: The Explorer view shows all ground truth items

3. **Create a draft**: Click the "Import" button to add items:
   - Use the bulk import for multiple items
   - Or create items manually through the API

4. **Assign to yourself**: Click an item and select "Assign to me"

5. **Curate the item**:
   - Edit the question to make it clear and specific
   - Review and edit the answer for accuracy
   - Add references to source materials
   - Apply relevant tags

6. **Approve**: Once satisfied, click "Approve" to finalize the item

## Next Steps

- [Learn the complete SME workflow](../guides/sme-workflow.md)
- [Explore the API](../api/index.md)
- [Understand the architecture](../architecture/index.md)

## Common Tasks

### Bulk Import CSV

```bash
curl -X POST http://localhost:8000/api/v1/ground-truths \
  -H "Content-Type: text/csv" \
  --data-binary @your-file.csv
```

### Export Snapshot

```bash
curl -X POST http://localhost:8000/api/v1/snapshot \
  -H "Content-Type: application/json" \
  -d '{"dataset": "default", "status": "approved"}'
```

### Search Items

```bash
curl "http://localhost:8000/api/v1/ground-truths?keyword=search+term&status=approved"
```
