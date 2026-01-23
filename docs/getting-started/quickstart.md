# Quickstart

This guide will help you create your first ground truth item.

## Prerequisites

- Backend and frontend installed (see [Installation](installation.md))
- Environment configured (see [Configuration](configuration.md))

## Start the Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Start the development server:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

   The API will be available at `http://localhost:8000`.

3. Verify the backend is running:
   ```bash
   curl http://localhost:8000/healthz
   ```

## Start the Frontend

1. In a new terminal, navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

   The app will be available at `http://localhost:5173`.

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
