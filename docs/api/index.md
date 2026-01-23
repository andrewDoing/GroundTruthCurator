# API Reference

Ground Truth Curator provides a RESTful API for managing ground truth data, assignments, and metadata.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

All API endpoints require authentication via JWT tokens. Include the token in the Authorization header:

```bash
Authorization: Bearer <token>
```

## Endpoints

### Ground Truths
- [Ground Truth Management](ground-truths.md) - Create, read, update, and delete ground truth items

### Assignments
- [Assignment Management](assignments.md) - Assign items to users and track ownership

### Tags
- [Tag Management](tags.md) - Manage and query available tags

### Search
- [Search and Filter](search.md) - Advanced search and filtering capabilities

## Common Patterns

### Pagination

List endpoints support pagination:

```bash
GET /api/v1/ground-truths?limit=50&offset=100
```

### Filtering

Use query parameters for filtering:

```bash
GET /api/v1/ground-truths?status=draft&dataset=default&keyword=search+term
```

### Sorting

Specify sort field and direction:

```bash
GET /api/v1/ground-truths?sort_by=created_at&sort_direction=desc
```

## Error Responses

The API uses standard HTTP status codes:

- `200 OK` - Request succeeded
- `201 Created` - Resource created
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., already assigned)
- `413 Payload Too Large` - Request exceeds size limits
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

Error response format:

```json
{
  "detail": "Error message",
  "field": "fieldName",
  "code": "ERROR_CODE"
}
```

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- Bulk import: 1000 items per request
- Standard endpoints: 100 requests per minute

## OpenAPI Specification

The complete API specification is available at:

```
http://localhost:8000/api/openapi.json
```

Interactive documentation:

```
http://localhost:8000/docs
```

## Client Libraries

TypeScript types are auto-generated from the OpenAPI spec:

```bash
cd frontend
npm run generate:api
```
