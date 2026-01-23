# Configuration

Ground Truth Curator uses environment variables for configuration. This guide covers the key settings.

## Backend Configuration

The backend uses Pydantic Settings for configuration management.

### Environment Variables

Create a `.env` file in the `backend/` directory or set these environment variables:

```bash
# Database Configuration
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE_NAME=groundtruth
COSMOS_CONTAINER_NAME=items

# Or use mock repository for development
USE_MOCK_REPO=true

# Security
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256

# Rate Limiting
BULK_IMPORT_MAX_ITEMS=1000

# Feature Flags
PII_DETECTION_ENABLED=true
DUPLICATE_DETECTION_ENABLED=true

# Telemetry (optional)
APPLICATIONINSIGHTS_CONNECTION_STRING=your-connection-string
```

### Development Mode

For local development, you can use the mock repository:

```bash
export USE_MOCK_REPO=true
```

This stores data in memory and doesn't require Azure Cosmos DB.

## Frontend Configuration

The frontend uses runtime configuration loaded from the backend.

### Build-time Configuration

Set the API endpoint during build:

```bash
# In frontend/.env.local
VITE_API_BASE_URL=http://localhost:8000
```

### Runtime Configuration

The frontend fetches configuration from `/api/config` endpoint at runtime. This allows deploying the same build to different environments.

## Next Steps

- [Run the quickstart](quickstart.md)
- [Learn about the SME workflow](../guides/sme-workflow.md)
