# Cosmos DB Emulator Unicode Character Workaround

## Problem

The Cosmos DB Emulator has a bug where it fails to parse certain Unicode characters in JSON documents, returning the error:

```text
azure.cosmos.exceptions.CosmosHttpResponseError: (InternalServerError) invalid input syntax for type json
```

This occurs when saving data containing:
- Smart quotes and apostrophes: `"` `"` `'` `'`
- Em and en dashes: `—` `–`
- Ellipsis: `…`
- Other special Unicode characters

**Common scenarios:**
- Multiturn conversation history with copied text from documents
- References with special characters in URLs, titles, or content
- Tags or comments containing formatted text
- Any ground truth content with non-ASCII punctuation

**Important:** This is **only** an emulator bug. Production Cosmos DB handles these characters correctly.

## Solution

When `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true`, the system normalizes Unicode characters before saving to Cosmos by replacing problematic characters with ASCII equivalents.

### Character Replacements

```python
'\u201c' → '"'   # Left double quotation mark  → regular quote
'\u201d' → '"'   # Right double quotation mark → regular quote
'\u2018' → "'"   # Left single quotation mark  → apostrophe
'\u2019' → "'"   # Right single quotation mark → apostrophe
'\u2013' → '-'   # En dash                     → hyphen
'\u2014' → '--'  # Em dash                     → double hyphen
'\u2026' → '...' # Horizontal ellipsis         → three periods
```

### Example

**Before normalization:**
```json
{
  "question": "What's the "best" approach…",
  "history": [
    {"role": "user", "content": "Tell me about the product's features—it's great!"}
  ]
}
```

**After normalization:**
```json
{
  "question": "What's the \"best\" approach...",
  "history": [
    {"role": "user", "content": "Tell me about the product's features--it's great!"}
  ]
}
```

## Implementation

### 1. Configuration (`app/core/config.py`)

Added environment variable:

```python
COSMOS_DISABLE_UNICODE_ESCAPE: bool = False
```

### 2. Normalization Function (`app/adapters/repos/cosmos_repo.py`)

```python
def _normalize_unicode_for_cosmos(obj: Any) -> Any:
    """
    Recursively normalize Unicode characters in strings to work around Cosmos emulator bugs.
    Replaces smart quotes, em dashes, and other problematic Unicode with ASCII equivalents.
    
    Only applies when COSMOS_DISABLE_UNICODE_ESCAPE is True (local dev with emulator).
    """
    if not settings.COSMOS_DISABLE_UNICODE_ESCAPE:
        return obj
    
    # Character replacements for common problematic Unicode
    replacements = {
        '\u201c': '"',  # Left double quotation mark
        '\u201d': '"',  # Right double quotation mark
        '\u2018': "'",  # Left single quotation mark
        '\u2019': "'",  # Right single quotation mark
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2026': '...', # Horizontal ellipsis
    }
    
    if isinstance(obj, str):
        # Apply specific replacements for known problematic characters
        result = obj
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result
    elif isinstance(obj, dict):
        return {k: _normalize_unicode_for_cosmos(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_normalize_unicode_for_cosmos(item) for item in obj]
    else:
        return obj
```

### 3. Applied in Save Operations

The normalization is applied in these methods before sending data to Cosmos:

#### `cosmos_repo.py`
- **`upsert_gt()`** - Main ground truth save operation
- **`import_bulk_gt()`** - Bulk import operations
- **`upsert_curation_instructions()`** - Dataset curation documents
- **`upsert_assignment_doc()`** - Assignment tracking documents

#### `tags_repo.py`
- **`save_global_tags()`** - Global tag storage

**Pattern used in all methods:**

```python
# Prepare document
doc = self._to_doc(item)
doc["updatedAt"] = now.isoformat()

# Apply normalization when using emulator
if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
    doc = CosmosGroundTruthRepo._ensure_utf8_strings(doc)

# Save to Cosmos
await container.upsert_item(doc)
```

## Usage

### Local Development (with Emulator)

Enable the workaround in `environments/local-development.env`:

```bash
# Disable Unicode escape sequences to work around Cosmos emulator bug
# When true, replaces smart quotes (""), apostrophes ('), em/en dashes with ASCII equivalents
# Only needed for local development with emulator - do NOT enable in production
GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true
```

Or set as environment variable:

```bash
export GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true
```

### Production Deployment

**DO NOT enable this setting in production.** Production Cosmos DB does not have this bug and handles all Unicode correctly. The setting should remain `false` (default) or be unset.

## Testing

Run the test script to validate the normalization:

```bash
cd backend
uv run python test_unicode_fix.py
```

The test validates:
- ✅ Smart quotes are replaced with regular quotes
- ✅ Em/en dashes are replaced with hyphens
- ✅ Ellipsis is replaced with three periods
- ✅ Nested structures (dicts and lists) are processed recursively
- ✅ Other Unicode (emojis, accents) is preserved
- ✅ Flag can be toggled on/off

## Why This Approach?

We chose **data normalization** over other approaches because:

1. **Predictable**: Known character replacements, no surprises
2. **Testable**: Easy to validate with unit tests
3. **Isolated**: Only affects data being saved, no global side effects
4. **Safe**: Doesn't interfere with other libraries or JSON serialization
5. **Conservative**: Only replaces known problematic characters, preserves everything else

### Alternative Approaches Considered

❌ **Monkey-patching `json.dumps()`** - Causes global side effects, harder to debug  
❌ **JSON round-trip serialization** - Doesn't work because SDK re-serializes internally  
❌ **Aggressive ASCII normalization** - Would strip emojis, non-Latin characters, etc.

## Design Decisions

### Why `_ensure_utf8_strings()` wrapper?

The `_ensure_utf8_strings()` method wraps `_normalize_unicode_for_cosmos()` to provide:

1. **Semantic clarity**: Name describes the *intent* (ensuring strings are safe) rather than the implementation detail
2. **Stable interface**: Call sites don't need to know *how* we fix Unicode, just that we do
3. **Future flexibility**: If we need to change the approach, we only update one place

### Why not normalize in `_to_doc()`?

We apply normalization **after** `_to_doc()` because:

1. **Separation of concerns**: `_to_doc()` converts models to dicts, normalization is a separate storage concern
2. **Testability**: Can test model serialization independently from Unicode handling
3. **Explicitness**: Makes it clear in each save operation that normalization is happening

## Troubleshooting

### Still getting Unicode errors?

1. **Check the flag is enabled**: `echo $GTC_COSMOS_DISABLE_UNICODE_ESCAPE`
2. **Restart the backend**: Changes to environment variables require a restart
3. **Check the character**: View the actual Unicode codepoint in the error
4. **Add to replacement map**: If it's a new problematic character, add it to the `replacements` dict

### Characters being removed unexpectedly?

The normalization should only replace the specific characters in the replacement map. If other characters are being affected, check:

1. Is there additional normalization happening elsewhere?
2. Is the character genuinely in the replacement map?
3. Check the test script output to validate behavior

## References

- [Azure Cosmos DB Emulator Documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/emulator)
- [Python JSON Module](https://docs.python.org/3/library/json.html)
- [Unicode Character Database](https://www.unicode.org/charts/)
