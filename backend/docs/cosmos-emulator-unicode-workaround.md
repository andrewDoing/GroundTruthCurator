# Cosmos Emulator Unicode Escape Workaround (Consolidated)

> Consolidates prior docs: previous "Unicode Escape Sequence Fix" (sentinel approach) and updated Base64 workaround.

## 1. Problem

The Azure Cosmos DB Emulator rejects documents containing certain character sequences in strings, specifically invalid JSON escape sequences like `\_`, `\q`, etc. (Only `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, and `\uXXXX` are valid JSON escapes.)

Example error:

```text
CosmosHttpResponseError: (InternalServerError) unsupported Unicode escape sequence
```

This issue does **not** occur in production Azure Cosmos DB — only the local emulator.

## 2. Root Cause Summary

1. Documentation content (refs) includes patterns like `EFX\_ITEM\_NR` → contains invalid escape fragments `\_`.
2. Python serializes safely (`EFX\\_ITEM...`) but the emulator's JSON parser mishandles certain backslash sequences.
3. The Azure Cosmos Python SDK internally re-serializes payloads, defeating naive string sanitization.

## 3. Evolution of Attempts

| Attempt | Technique | Result | Reason Rejected |
|--------|-----------|--------|-----------------|
| A | NFKC normalization + control char removal | ❌ Fails | Emulator still errors |
| B | Smart punctuation replacement | ❌ Fails | Cosmetic only |
| C | Sentinel replacement (`⧵` U+29F5) | ❌ Fails | Emulator still errors after SDK re-serialization |
| D | ASCII placeholder (`{{BACKSLASH}}`) | ❌ Fails | Same failure mode |
| E | URL decoding before sanitize | ❌ Fails | No effect on invalid escapes |
| F | Strip content | ❌ Unacceptable | Data loss |
| G | Base64 encode refs.content | ✅ Works | Bypasses parser entirely |

## 4. Final Solution (Active When `GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true`)

Only the `content` field inside each item of the `refs` array is Base64-encoded before persistence and decoded after retrieval.

### 4.1 Encoding (before save)

```python
def _base64_encode_refs_content(refs_list: list) -> list:
    """Base64-encode 'content' fields within refs array items."""
    import base64

    result = []
    for ref in refs_list:
        if isinstance(ref, dict):
            ref_copy = ref.copy()
            if (
                "content" in ref_copy
                and isinstance(ref_copy["content"], str)
                and ref_copy["content"]
                and not ref_copy.get("_contentEncoded")
            ):
                content_bytes = ref_copy["content"].encode("utf-8")
                ref_copy["content"] = base64.b64encode(content_bytes).decode("ascii")
                ref_copy["_contentEncoded"] = True
            result.append(ref_copy)
        else:
            result.append(ref)
    return result
```

### 4.2 Decoding (after read)

```python
def _base64_decode_refs_content(refs_list: list) -> list:
    """Reverse Base64 encoding of 'content' fields in refs array."""
    import base64

    result = []
    for ref in refs_list:
        if isinstance(ref, dict):
            ref_copy = ref.copy()
            if ref_copy.get("_contentEncoded") and "content" in ref_copy:
                try:
                    content_bytes = base64.b64decode(ref_copy["content"])
                    ref_copy["content"] = content_bytes.decode("utf-8")
                    del ref_copy["_contentEncoded"]
                except Exception:
                    pass
            result.append(ref_copy)
        else:
            result.append(ref)
    return result
```

### 4.3 Integration Points

- In `_normalize_unicode_for_cosmos()`: normalize refs first, then apply Base64 encoding to their `content` fields.
- In `_restore_unicode_from_cosmos()`: decode Base64 content first, then recursively restore any sentinel substitutions (legacy compatibility).

## 5. What Still Uses Plain Sanitization?

All other string fields (e.g., questions, answers, `history[].msg`, `refs[].url`, `refs[].keyExcerpt`) still use:

1. NFKC normalization
2. Control character cleanup / zero-width removal
3. Smart punctuation ASCII replacement
4. Invalid escape sequence placeholder substitution (`\\_` → `{{BACKSLASH}}_`) — only in emulator mode

These remain for readability, consistency, and to guard against future emulator edge cases outside `refs.content`.

## 6. Scope & Activation

Base64 encoding applies only when:

```text
GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true
```

And only to:

- `refs[*].content`

Production (where the flag is false) does not perform Base64 encoding and does not rewrite backslashes.

## 7. Trade-offs

| Aspect | Pros | Cons |
|--------|------|------|
| Reliability | Works on all payloads | Adds transform overhead |
| Data fidelity | Perfect round-trip | Content unreadable in emulator DB UI |
| Scope | Minimal (refs.content only) | Slight storage expansion (~33%) |
| Maintainability | Isolated logic | Dual-path (emulator vs prod) |

## 8. Testing Matrix

| Test | Purpose | Status |
|------|---------|--------|
| Round-trip script | Encode → Decode equality | ✅ Pass |
| Actual save script | Emulator persistence | ✅ Pass |
| Unit tests (11) | Sanitization behaviors | ✅ Pass |
| Invalid escapes | Ensure no failure | ✅ Pass |
| Valid escapes | Ensure unchanged | ✅ Pass |

## 9. Alternatives Revisited

| Alternative | Outcome |
|-------------|---------|
| Use prod Cosmos | Works, but requires cloud access for local dev |
| Strip refs.content | Avoids error but loses data |
| Sentinel-only approach | Emulator still errored post SDK serialization |
| URL decoding | No material impact |
| ASCII placeholder only | Same failure mode |

## 10. Operational Guidance

### Local Dev

Enable the flag in your env file:

```bash
GTC_COSMOS_DISABLE_UNICODE_ESCAPE=true
```

### Production

Leave it unset / false. No Base64 logic executes; refs remain plain text.

### Manual Inspection Tip

If inspecting a document in the emulator and you see Base64 blocks in `refs.content`, decode with:

```python
import base64
decoded = base64.b64decode(encoded_value).decode("utf-8")
```

## 11. Removal / Future Sunset Plan

If the emulator fixes its parser:

1. Remove the Base64 encode/decode helpers.
2. Drop `_contentEncoded` marker handling.
3. Keep (or simplify) general string sanitization for other fields (optional).

## 12. FAQ

**Q: Why not encode all strings?**  
A: Limiting scope minimizes bloat and keeps most fields readable/queryable.

**Q: Does this affect querying refs content?**  
A: Yes — emulator queries on raw content won't work. Production queries are unaffected.

**Q: Can we safely remove smart punctuation replacement now?**  
A: Not recommended; it still improves consistency for non-encoded fields.

**Q: What about performance?**  
A: Overhead is negligible relative to network and IO; Base64 only touches `refs.content` strings.

---

## 13. Quick Verification Commands (Optional)

```bash
# Run unit tests
uv run pytest tests/unit/test_unicode_fix.py -v

# Round-trip confirmation
uv run python scripts/test_roundtrip.py

# Emulator save test
uv run python scripts/test_actual_save.py
```

---

## 14. Recommendation

Use Base64 workaround only for local emulator development. Prefer production Cosmos for integration testing when feasible. Keep the flag-driven approach to avoid accidental activation in production.

---

### Consolidation Note

This file supersedes prior `unicode-escape-fix.md`; that approach is deprecated in favor of Base64 encoding.
