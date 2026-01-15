# XSS Sanitization Research - SA-565

**Date:** 2025-01-22  
**Component:** TurnReferencesModal.tsx and related components  
**Story:** SA-565  

## Executive Summary

The frontend codebase **does NOT use `dangerouslySetInnerHTML`**, which is the primary XSS attack vector in React. The "key paragraph" fields in `TurnReferencesModal.tsx` are rendered via controlled `<textarea>` elements, which are safe by design. However, there are other user-generated content patterns that warrant review.

## Question 1: Vulnerable Code Location in TurnReferencesModal.tsx

### Location
- File: [frontend/src/components/app/editor/TurnReferencesModal.tsx](frontend/src/components/app/editor/TurnReferencesModal.tsx#L320-L370)

### Key Paragraph Rendering (Lines 320-370)

The key paragraph section uses a controlled `<textarea>`:

```tsx
<textarea
    className={cn(...)}
    placeholder={readOnly ? "" : "Summarize the most relevant..."}
    value={r.keyParagraph || ""}
    onChange={
        readOnly
            ? undefined
            : (e) => onUpdateReference(r.id, { keyParagraph: e.target.value })
    }
    readOnly={readOnly}
    rows={...}
/>
```

**Assessment:** This is **SAFE**. React `<textarea>` with `value` prop escapes all content automatically. There is no XSS vulnerability here.

### Reference Title/URL Rendering (Lines 244-268)

```tsx
<div className="break-words text-sm font-medium">
    [{index + 1}] {r.title || urlToTitle(r.url)}
</div>
<a
    className="inline-flex max-w-full items-center gap-1 truncate text-xs text-violet-700 underline"
    onClick={(e) => { e.preventDefault(); onOpenReference(r); }}
    href={normalizeUrl(r.url)}
    target="_blank"
    rel="noreferrer"
>
    <ExternalLink className="h-3.5 w-3.5" /> {normalizeUrl(r.url)}
</a>
```

**Assessment:** **SAFE** - React's JSX automatically escapes text content in curly braces.

## Question 2: Existing Sanitization Libraries

### package.json Dependencies

```json
{
    "dependencies": {
        "react-markdown": "^9.0.3",
        "remark-gfm": "^4.0.0"
    }
}
```

### Findings

| Library | Purpose | XSS Protection |
|---------|---------|----------------|
| `react-markdown` | Markdown rendering | ✅ Built-in HTML sanitization by default |
| `remark-gfm` | GitHub Flavored Markdown | Plugin only, inherits react-markdown's safety |

**No explicit sanitization libraries** like `DOMPurify` or `xss` are installed. The codebase relies on:
1. React's automatic escaping of JSX expressions
2. react-markdown's built-in sanitization

## Question 3: Components Rendering User-Generated Content

### Components Analyzed

| Component | User Content Rendered | Method | Risk Level |
|-----------|----------------------|--------|------------|
| [TurnReferencesModal.tsx](frontend/src/components/app/editor/TurnReferencesModal.tsx) | `keyParagraph`, `title`, `url` | `<textarea>`, JSX interpolation | ✅ Low |
| [SelectedTab.tsx](frontend/src/components/app/ReferencesPanel/SelectedTab.tsx) | `keyParagraph`, `title`, `url` | `<textarea>`, JSX interpolation | ✅ Low |
| [ConversationTurn.tsx](frontend/src/components/app/editor/ConversationTurn.tsx) | `turn.content` | `MarkdownRenderer` component | ✅ Low |
| [MarkdownRenderer.tsx](frontend/src/components/common/MarkdownRenderer.tsx) | Markdown content | `ReactMarkdown` | ✅ Low |
| [InspectItemModal.tsx](frontend/src/components/modals/InspectItemModal.tsx) | Item data, references | JSX, `MultiTurnEditor` | ✅ Low |

### URL Handling in InspectItemModal.tsx

Found a comprehensive URL validation utility at [InspectItemModal.tsx#L28-L54](frontend/src/components/modals/InspectItemModal.tsx#L28-L54):

```tsx
const validateReferenceUrl = (url: string): boolean => {
    try {
        const parsedUrl = new URL(url);
        
        // Only allow safe protocols
        const allowedProtocols = ["http:", "https:"];
        if (!allowedProtocols.includes(parsedUrl.protocol)) {
            return false;
        }
        
        // Block known malicious patterns
        const maliciousPatterns = [
            /javascript:/i, /data:/i, /vbscript:/i, /about:/i, /blob:/i
        ];
        
        if (maliciousPatterns.some(pattern => pattern.test(url))) {
            return false;
        }
        return true;
    } catch (_error) {
        return false;
    }
};
```

**This validation is only used in `InspectItemModal`**, not in `TurnReferencesModal`.

## Question 4: React Best Practices for User Content

### Current State

React provides automatic XSS protection through:
1. **JSX Expression Escaping:** All `{value}` expressions are automatically escaped
2. **No `dangerouslySetInnerHTML`:** Confirmed - zero instances in the codebase
3. **react-markdown:** Uses allowlist approach, disables raw HTML by default

### Best Practice Recommendations

1. **DOMPurify** - Only needed if using `dangerouslySetInnerHTML` (not applicable here)
2. **URL Validation** - The `validateReferenceUrl` pattern in `InspectItemModal` should be applied consistently to all reference URL opening

## Vulnerable Patterns Found

### Pattern 1: Inconsistent URL Validation

**Issue:** The URL validation in `InspectItemModal` is not applied in `TurnReferencesModal.tsx`.

**Location:** [TurnReferencesModal.tsx#L262-L270](frontend/src/components/app/editor/TurnReferencesModal.tsx#L262-L270)

```tsx
<a
    onClick={(e) => { e.preventDefault(); onOpenReference(r); }}
    href={normalizeUrl(r.url)}
    target="_blank"
    rel="noreferrer"
>
```

**Risk:** The `onOpenReference` callback may open malicious URLs if the parent component doesn't validate.

### Pattern 2: Missing `noopener` on External Links

**Issue:** While `rel="noreferrer"` provides some protection, best practice is to include `noopener,noreferrer`.

**Locations:**
- [TurnReferencesModal.tsx#L268](frontend/src/components/app/editor/TurnReferencesModal.tsx#L268)
- [SelectedTab.tsx#L64](frontend/src/components/app/ReferencesPanel/SelectedTab.tsx#L64)

## Existing Mitigations

1. **No `dangerouslySetInnerHTML`** - Primary XSS vector is absent
2. **react-markdown sanitization** - Markdown content is sanitized
3. **URL validation in InspectItemModal** - Partial protection for that component
4. **External link confirmation** in InspectItemModal for untrusted domains

## Recommendations

### High Priority
1. Extract `validateReferenceUrl` to a shared utility and use it consistently in:
   - `TurnReferencesModal.tsx` `onOpenReference` handler
   - `SelectedTab.tsx` `onOpenReference` handler
   - Any component that opens reference URLs

### Medium Priority
2. Add `noopener` to all external link `rel` attributes
3. Consider adding domain allowlisting for reference URLs at the application level

### Low Priority
4. No need to add DOMPurify unless `dangerouslySetInnerHTML` is introduced in the future

## Conclusion

**SA-565's concern about XSS in key paragraph rendering is a false positive.** The `<textarea>` element with React's controlled component pattern is inherently safe against XSS.

However, the research uncovered an **inconsistent URL validation pattern** that should be addressed:
- `InspectItemModal` has robust URL validation
- `TurnReferencesModal` and `SelectedTab` do not validate URLs before opening

The real vulnerability is **not XSS injection via content** but **potential for malicious URL schemes** if a compromised backend sends `javascript:` or `data:` URLs in reference data.
