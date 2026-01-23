<!-- markdownlint-disable-file -->
# Release Changes: has_answer Sort Field Documentation

**Related Plan**: IMPLEMENTATION_PLAN.md (Code Quality)
**Implementation Date**: 2026-01-23

## Summary

Resolved TODO comment in `cosmos_repo.py` by documenting the design rationale for the `has_answer` sort field mapping. The TODO suggested revisiting why `has_answer` maps to `c.reviewedAt` in Cosmos DB queries. After investigation, this is the correct implementation given Cosmos DB limitations.

The changes add comprehensive documentation explaining:
1. Why `has_answer` uses `c.reviewedAt` as a placeholder in the ORDER BY clause
2. That actual sorting happens in-memory where `has_answer` is computed as a boolean
3. This design works around Cosmos DB's inability to sort by computed/derived fields

## Changes

### Modified

* `backend/app/adapters/repos/cosmos_repo.py` - Replaced TODO with detailed documentation
  * Line ~760: Added multi-line comment explaining the `has_answer` mapping rationale in `_build_secure_sort_clause`
  * Line ~700: Added cross-reference comment in `_sort_key` method explaining in-memory sort implementation
  * Both comments clarify that this is a deliberate design decision, not a bug or incomplete implementation

## Technical Details

**The Design Pattern:**

Cosmos DB SQL doesn't support sorting by computed expressions like:
```sql
ORDER BY (c.answer IS NOT NULL AND LENGTH(c.answer) > 0)
```

**The Solution:**

1. **Cosmos Query Level**: Use `c.reviewedAt` as a syntactically valid placeholder in ORDER BY
2. **Python Level**: Perform actual sorting in `_sort_key` method using:
   - Primary sort key: `has_answer` (1 if answer exists and non-empty, else 0)
   - Secondary sort key: `reviewed_at` (or `updated_at` fallback)
   - Tertiary sort key: `id` (for stable sorting)

**Why This Works:**

- Cosmos DB requires a valid ORDER BY clause for pagination/consistency
- The placeholder doesn't affect correctness because Python re-sorts the results
- This pattern is consistent with how `tag_count` sorting works (also in-memory)

## Testing

* All 26 cosmos_repo unit tests pass
* Type checking clean with `ty check`
* No functional changes, only documentation improvements

## Release Summary

Resolved code clarity issue by documenting existing correct implementation. No behavior changes.

**Files affected**: 1 file modified
**Tests**: All 267 backend unit tests passing
**Type checking**: Zero errors
