# Multi-Turn History with References

## Overview

This document describes the enhancement to the Ground Truth Curator backend to support storing references alongside agent messages in the multi-turn conversation history. This change maintains backward compatibility with the existing top-level `refs` field.

## Changes Made

### 1. Domain Model Updates

**File: `app/domain/models.py`**

Added an optional `refs` field to the `HistoryItem` model to allow storing references with agent responses:

```python
class HistoryItem(BaseModel):
    """Represents a single item in the multi-turn history."""

    role: HistoryItemRole  # User or Assistant
    msg: str
    refs: Optional[list[Reference]] = None  # References for agent messages
    tags: list[str] = Field(default_factory=list)  # Optional tags for categorizing history items
```

### 2. API Endpoint Updates

**Files: `app/api/v1/assignments.py` and `app/api/v1/ground_truths.py`**

Both update endpoints now support receiving and parsing history items with embedded references and tags:

- Added `history` field to `AssignmentUpdateRequest` model
- Added history parsing logic that:
  - Converts dict representations to `HistoryItem` models
  - Parses and validates `refs` within each history item
  - Parses optional `tags` array within each history item
  - Supports both `msg` and `content` field names for compatibility
  - Validates reference structure using the `Reference` model

Example payload handling:

```python
if "history" in provided_fields and payload.history is not None:
    history_items = []
    for h in payload.history:
        refs_data = h.get("refs")
                refs_list = None
                if refs_data is not None:
                    refs_list = [
                        r if isinstance(r, Reference) else Reference(**r)
                        for r in refs_data
                    ]
                # Parse tags if present in the history item
                tags_data = h.get("tags", [])
                history_items.append(
                    HistoryItem(
                        role=h["role"],
                        msg=h.get("msg") or h.get("content", ""),
                        refs=refs_list,
                        tags=tags_data if isinstance(tags_data, list) else [],
                    )
                )
    it.history = history_items
```

## Backward Compatibility

The changes maintain full backward compatibility:

1. **Top-level `refs` field preserved**: The `GroundTruthItem.refs` field at the top level remains unchanged and continues to work as before.

2. **Optional refs in history**: The `refs` field in `HistoryItem` is optional (defaults to `None`), so existing history items without refs continue to work.

3. **Optional tags in history**: The `tags` field in `HistoryItem` is optional (defaults to an empty list), so existing history items without tags continue to work.

4. **Flexible field names**: The parser supports both `msg` and `content` field names for the message text, accommodating different client implementations.

## Data Structure

### Example with refs and tags in history

```json
{
  "id": "example-1",
  "datasetName": "demo",
  "synthQuestion": "How do I use this product?",
  "answer": "It is a powerful CAD tool...", 
  "refs": [
    {
      "url": "https://example.com/doc1",
      "content": "General documentation"
    }
  ],
  "history": [
    {
      "role": "user",
      "msg": "What is this product?",
      "tags": ["introduction", "basic-info"]
    },
    {
      "role": "assistant",
      "msg": "It is a CAD software...",
      "refs": [
        {
          "url": "https://example.com/intro",
          "content": "Introduction",
          "keyExcerpt": "It is a comprehensive 3D CAD solution"
        }
      ],
      "tags": ["product-overview"]
    },
    {
      "role": "user",
      "msg": "How do I install it?",
      "tags": ["installation", "getting-started"]
    },
    {
      "role": "assistant",
      "msg": "To install the product, follow these steps...",
      "refs": [
        {
          "url": "https://example.com/install",
          "content": "Installation guide",
          "type": "kb"
        }
      ],
      "tags": ["installation", "step-by-step"]
    }
  ]
}
```

## Frontend Integration

The frontend already has support for tracking which agent turn references belong to via the `turnIndex` field on the `Reference` type. This backend change complements that by allowing the references to be stored directly with the history items.

### Mapping between frontend and backend

- **Frontend**: Uses `turnIndex` on references to indicate which turn they belong to
- **Backend**: Stores references directly within the `HistoryItem` that generated them

When syncing between frontend and backend:

1. Frontend can group references by `turnIndex` and include them in the corresponding history item when saving
2. Backend stores these references with the history item
3. When loading, backend returns history items with embedded refs
4. Frontend can extract refs and set the appropriate `turnIndex` based on the history position

## Testing

A comprehensive test suite has been added in `tests/unit/test_history_with_refs.py` that validates:

- Creating history items with refs
- Creating history items without refs (optional field)
- Serialization (model_dump)
- Deserialization (from dict)
- Both user and agent messages with/without refs

All tests pass successfully.

## Use Cases

This enhancement enables several important use cases:

1. **Multi-turn conversations**: Each agent response can include its own set of references, making it clear which sources were used for each part of the conversation.

2. **Reference tracking**: Track exactly which documents informed each response in a multi-turn dialogue.

3. **Categorization and filtering**: Use tags to categorize history items by topic, intent, or any other custom dimension. This enables filtering and analysis of conversations by tag.

4. **Evaluation**: Enable more precise evaluation of multi-turn conversations by associating references and tags with specific turns.

5. **Transparency**: Provide users with clear attribution for each agent response in a conversation.

6. **Content organization**: Tags can be used to mark special types of interactions (e.g., "clarification", "follow-up", "technical", "non-technical", "escalation").

## Migration Notes

No migration is required for existing data:

- Existing items without history continue to work
- Existing items with history but no refs in history items continue to work
- The top-level `refs` field remains the primary location for references in single-turn items

## Future Enhancements

Potential future improvements:

1. **Automatic reference aggregation**: Logic to automatically collect all refs from history items and merge them into the top-level `refs` field for backward compatibility with consumers that only read the top-level field.

2. **Reference deduplication**: Logic to deduplicate references across multiple turns in a conversation.

3. **Turn-specific reference validation**: Validate that references are appropriate for the specific turn they're associated with.
