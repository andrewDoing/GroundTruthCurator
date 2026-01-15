# Backend API Schema Changes Required

## Overview
The multi-turn ground truth curation feature requires backend API schema updates to persist the new fields. This document outlines the required changes.

## Ground Truth Item Schema Updates

### New Fields to Add

```typescript
{
  // Existing fields...
  id: string;
  question: string;
  answer: string;
  references: Reference[];
  status: "draft" | "approved" | "skipped";
  // ... other existing fields
  
  // NEW FIELDS:
  history?: ConversationTurn[];  // Optional array of conversation turns
  context?: string;               // Optional application context
}
```

### ConversationTurn Type

```typescript
type ConversationTurn = {
  role: "user" | "agent";  // Role of the speaker
  content: string;          // Message content
}
```

## Reference Schema Updates

### New Fields to Add

```typescript
{
  // Existing fields...
  id: string;
  title?: string;
  url: string;
  snippet?: string;
  visitedAt?: string | null;
  keyParagraph?: string;
  selected?: boolean;
  bonus?: boolean;
  
  // NEW FIELDS:
  relevance?: "relevant" | "irrelevant" | "neutral";  // Reference relevance
  turnIndex?: number;                                   // Associated turn (optional)
}
```

## API Endpoints to Update

### GET /api/ground-truths/:id
**Response Updates:**
- Include `history` field if present
- Include `context` field if present
- Include `relevance` and `turnIndex` in references array

### POST /api/ground-truths
**Request Body Updates:**
- Accept `history` field (optional)
- Accept `context` field (optional)
- Accept `relevance` and `turnIndex` in references array

### PUT /api/ground-truths/:id
**Request Body Updates:**
- Accept `history` field (optional)
- Accept `context` field (optional)
- Accept `relevance` and `turnIndex` in references array

### GET /api/ground-truths (list endpoint)
**Response Updates:**
- Include `history` field in items if present
- Include `context` field in items if present
- Include `relevance` and `turnIndex` in references

## Backward Compatibility

### Ensure Support For:
1. **Existing Items**: Items without `history` should work as before
2. **Legacy Fields**: `question` and `answer` fields must remain for single-turn compatibility
3. **Migration**: No automatic migration required - new fields are optional

### Sync Logic:
When `history` is present, the frontend will sync:
- Last user turn → `question` field
- Last agent turn → `answer` field

This ensures backward compatibility with systems expecting Q/A format.

## Validation Rules

### Multi-Turn Items:
- If `history` exists and has length > 0, validate:
  - At least one turn with role "user"
  - At least one turn with role "agent"
  - All references must have `relevance` set
  - References marked "relevant" must have `keyParagraph` ≥ 40 chars

### Single-Turn Items (Backward Compatible):
- If no `history` or `history.length === 0`:
  - Existing validation rules apply
  - `question` and `answer` required
  - At least one selected reference (if references present)

## Database Schema Example (MongoDB)

```javascript
{
  _id: ObjectId,
  id: String,
  question: String,
  answer: String,
  
  // NEW:
  history: [{
    role: { type: String, enum: ['user', 'agent'] },
    content: String
  }],
  context: String,
  
  references: [{
    id: String,
    url: String,
    // ... other fields
    
    // NEW:
    relevance: { 
      type: String, 
      enum: ['relevant', 'irrelevant', 'neutral'],
      required: false 
    },
    turnIndex: { type: Number, required: false }
  }],
  
  // ... other existing fields
  status: { type: String, enum: ['draft', 'approved', 'skipped'] },
  providerId: String,
  deleted: Boolean,
  tags: [String],
  comment: String,
  datasetName: String,
  bucket: String,
  curationInstructions: String
}
```

## Database Schema Example (SQL)

### ground_truths table:
```sql
ALTER TABLE ground_truths 
ADD COLUMN history JSONB,
ADD COLUMN context TEXT;
```

### references table (if separate):
```sql
ALTER TABLE references 
ADD COLUMN relevance VARCHAR(20) CHECK (relevance IN ('relevant', 'irrelevant', 'neutral')),
ADD COLUMN turn_index INTEGER;
```

Or if references are embedded JSON:
```sql
-- No schema change needed, JSON field automatically supports new properties
```

## Export Format Updates

The export endpoint should support expanding multi-turn conversations:

```javascript
// Single multi-turn item becomes multiple single-turn items
{
  id: "Q001",
  history: [
    { role: "user", content: "What is X?" },
    { role: "agent", content: "X is..." },
    { role: "user", content: "Can you elaborate?" },
    { role: "agent", content: "Sure..." }
  ],
  references: [...]
}

// Expands to:
[
  {
    id: "Q001-a",
    question: "What is X?",
    answer: "X is...",
    history: [
      { role: "user", content: "What is X?" },
      { role: "agent", content: "X is..." }
    ],
    references: [...] // filtered by turnIndex or global
  },
  {
    id: "Q001-b",
    question: "Can you elaborate?",
    answer: "Sure...",
    history: [
      { role: "user", content: "What is X?" },
      { role: "agent", content: "X is..." },
      { role: "user", content: "Can you elaborate?" },
      { role: "agent", content: "Sure..." }
    ],
    references: [...]
  }
]
```

## Testing Checklist

### API Testing:
- [ ] POST new multi-turn item with history
- [ ] GET multi-turn item returns history
- [ ] PUT updates history correctly
- [ ] References include relevance and turnIndex
- [ ] Backward compatibility: items without history work
- [ ] Export expands multi-turn items correctly

### Integration Testing:
- [ ] Frontend saves multi-turn conversations
- [ ] Frontend loads multi-turn conversations
- [ ] Reference relevance persists across saves
- [ ] Turn indices persist correctly
- [ ] Context field saves and loads

## Migration Notes

1. **No Breaking Changes**: All new fields are optional
2. **Gradual Adoption**: Teams can continue using single-turn mode
3. **Data Integrity**: Existing data unaffected
4. **Rollback Safe**: Can roll back frontend without data loss

## Timeline Recommendation

1. **Phase 1**: Update backend schema (1-2 days)
2. **Phase 2**: Deploy backend with new fields (1 day)
3. **Phase 3**: Deploy frontend multi-turn feature (same day)
4. **Phase 4**: User testing and feedback (1 week)
5. **Phase 5**: LLM service integration for turn generation (TBD)

## Questions for Backend Team

1. Which database system is in use (MongoDB, PostgreSQL, etc.)?
2. Are there any size limits on the `history` array?
3. Should `history` be indexed for search/filtering?
4. Are there any concerns about JSON field size for references?
5. Should export expansion happen on backend or frontend?
6. What is the preferred approach for validating the new fields?

## Contact

For questions or clarifications about these schema changes, please contact the frontend development team or refer to the implementation plan document.
