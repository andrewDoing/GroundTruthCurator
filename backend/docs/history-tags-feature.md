# History Items Tags Feature

## Summary

Added support for optional `tags` field on `HistoryItem` objects in the Ground Truth Curator backend. This allows categorizing and labeling individual turns in multi-turn conversations.

## Changes Made

### 1. Domain Model (`app/domain/models.py`)

Added a `tags` field to the `HistoryItem` model:

```python
class HistoryItem(BaseModel):
    """Represents a single item in the multi-turn history."""

    role: HistoryItemRole  # User or Assistant
    msg: str
    refs: Optional[list[Reference]] = None  # References for agent messages
    tags: list[str] = Field(default_factory=list)  # Optional tags for categorizing history items
```

**Properties:**

- Type: `list[str]`
- Default: Empty list `[]`
- Optional: Yes (defaults to empty list if not provided)
- Purpose: Categorize and label conversation turns

### 2. API Endpoint Updates

Updated both `assignments.py` and `ground_truths.py` to parse and handle tags:

#### `app/api/v1/assignments.py`

- Added parsing logic for `tags` field in history items
- Validates that tags is a list (defaults to empty list if not)
- Includes tags when constructing `HistoryItem` objects

#### `app/api/v1/ground_truths.py`

- Added parsing logic for `tags` field in history items
- Validates that tags is a list (defaults to empty list if not)
- Includes tags when constructing `HistoryItem` objects

### 3. Test Coverage

Added comprehensive test coverage in `tests/unit/test_history_with_refs.py`:

- `test_history_item_with_tags()` - Creating history items with tags
- `test_history_item_without_tags()` - Verifying default empty list behavior
- `test_history_item_with_refs_and_tags()` - Combining refs and tags
- `test_history_item_serialization_with_tags()` - Serialization to dict
- `test_history_item_deserialization_with_tags()` - Deserialization from dict
- `test_history_item_empty_tags_list()` - Explicit empty list handling

All 99 unit tests pass successfully.

### 4. Documentation Updates

Updated `docs/multi-turn-refs.md` to document the tags feature:

- Updated model definition
- Updated example payloads
- Added use cases for tags
- Updated backward compatibility notes

## Example Usage

### JSON Payload with Tags

```json
{
  "history": [
    {
      "role": "user",
      "msg": "What is this product?",
      "tags": ["introduction", "basic-info"]
    },
    {
      "role": "assistant",
      "msg": "It is a CAD software...",
      "refs": [...],
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
      "refs": [...],
      "tags": ["installation", "step-by-step"]
    }
  ]
}
```

## Use Cases

1. **Categorization**: Tag conversation turns by topic (e.g., "installation", "troubleshooting", "configuration")
2. **Intent tracking**: Mark user intent (e.g., "clarification", "follow-up", "new-question")
3. **Content classification**: Label by complexity (e.g., "technical", "non-technical", "advanced")
4. **Workflow tracking**: Mark special interactions (e.g., "escalation", "resolved", "pending")
5. **Evaluation**: Filter and analyze conversations by specific tag criteria
6. **Reporting**: Generate insights based on tag distribution across conversations

## Backward Compatibility

✅ **Fully backward compatible:**

- The `tags` field is optional with a default value of `[]`
- Existing history items without tags continue to work
- Existing API consumers don't need to change
- New API consumers can optionally include tags

## Implementation Details

### Parsing Logic

Both endpoints use the same parsing pattern:

```python
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
```

This ensures:

- Tags default to empty list if not provided
- Non-list values are converted to empty list (defensive)
- List values are preserved as-is

### Validation

- Tags must be a list of strings (enforced by Pydantic)
- No format restrictions on individual tag values
- Empty lists are allowed
- Duplicate tags are allowed (no automatic deduplication at model level)

## Testing

All tests pass:

```text
tests/unit/test_history_with_refs.py::test_history_item_with_tags PASSED
tests/unit/test_history_with_refs.py::test_history_item_without_tags PASSED
tests/unit/test_history_with_refs.py::test_history_item_with_refs_and_tags PASSED
tests/unit/test_history_with_refs.py::test_history_item_serialization_with_tags PASSED
tests/unit/test_history_with_refs.py::test_history_item_deserialization_with_tags PASSED
tests/unit/test_history_with_refs.py::test_history_item_empty_tags_list PASSED
```

Total: 99/99 tests passing

## Files Modified

1. `app/domain/models.py` - Added `tags` field to `HistoryItem`
2. `app/api/v1/assignments.py` - Added tags parsing logic
3. `app/api/v1/ground_truths.py` - Added tags parsing logic
4. `tests/unit/test_history_with_refs.py` - Added comprehensive test coverage
5. `docs/multi-turn-refs.md` - Updated documentation

## Future Enhancements

Potential future improvements:

1. **Tag validation**: Add optional validation rules for tag format/values
2. **Tag schema**: Define a schema for common tag categories
3. **Tag deduplication**: Automatic deduplication at the API layer
4. **Tag search**: Enable filtering/searching by history item tags
5. **Tag analytics**: Aggregate tag statistics across conversations
6. **Tag suggestions**: Auto-suggest tags based on message content
