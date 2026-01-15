---
title: Tag Glossary
description: Define, store, and display human-readable descriptions for all tag types
jtbd: JTBD-006
author: spec-builder
ms.date: 2026-01-22
status: draft
stories:
  - SA-205
---

# Tag Glossary

Provide human-readable definitions for manual and computed tags through a unified glossary system.

**Parent JTBD:** [JTBD-006: Help teams understand GTC through documentation](../docs/ground-truth-curation-reqs.md)

## Problem Statement

Users encounter tags throughout the Ground Truth Curator interface without understanding their meaning or purpose. The current system stores tags as simple strings with no associated definitions:

- **Manual tags** (6 groups, 20+ values) appear without context about when to apply them
- **Computed tags** (13 plugins) display cryptic keys like `retrieval_behavior:rich` without explanation
- **SME-created tags** have no mechanism to attach definitions at all
- New team members cannot self-serve tag meanings, slowing onboarding

Without accessible definitions, users apply tags inconsistently or avoid using the tagging system altogether.

## Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| TG-01 | Display tag definitions via tooltip on TagChip hover | Must | Shows definition without disrupting workflow |
| TG-02 | Provide glossary view listing all tags with definitions | Must | Full reference for browsing/searching |
| TG-03 | Store system tag definitions in configuration/code | Must | Manual tags in JSON, computed tags in plugin classes |
| TG-04 | Store SME-created tag definitions in database | Must | Hybrid approach: config for system, database for custom |
| TG-05 | API endpoint returns unified glossary from all sources | Must | Single source of truth for frontend |
| TG-06 | Allow SMEs to add/edit definitions for custom tags | Should | Glossary management interface |
| TG-07 | Support group-level descriptions for manual tag groups | Should | Explain purpose of each tag group |
| TG-08 | Display definitions when selecting tags in TagsEditor | Could | Inline guidance during tagging |

## User Stories

### Viewing Tag Definitions

**As a** curation team member reviewing ground truth items,
**I want to** see what each tag means by hovering over it,
**So that** I understand the classification without leaving my current task.

**Acceptance Criteria:**

- Hovering over any TagChip shows a tooltip with the tag definition
- Tooltip appears within 200ms and remains visible while hovering
- Tags without definitions show "No definition available"
- Computed tags include their auto-generation criteria in the definition

### Browsing the Glossary

**As a** new team member onboarding to GTC,
**I want to** browse a complete glossary of all available tags,
**So that** I understand the tagging taxonomy before starting curation work.

**Acceptance Criteria:**

- Glossary view accessible from main navigation or settings
- Tags grouped by type (manual groups, computed, custom)
- Search/filter capability to find specific tags
- Definitions displayed inline with tag names

### Managing Custom Tag Definitions

**As an** SME who creates custom tags,
**I want to** add definitions when creating tags and edit them later,
**So that** other team members understand tags I introduce.

**Acceptance Criteria:**

- Tag creation flow includes optional description field
- Existing custom tags can have definitions added/edited
- Changes persist to database immediately
- Glossary reflects updates without page refresh

## Technical Considerations

### Backend Changes

#### Manual Tag Schema Extension

Extend [backend/app/domain/manual_tags.json](../backend/app/domain/manual_tags.json) schema:

```json
{
  "group": "source",
  "description": "Origin of the ground truth content",
  "mutuallyExclusive": true,
  "tags": [
    { "value": "sme", "description": "Created by subject matter expert" },
    { "value": "synthetic", "description": "AI-generated content" },
    { "value": "sme_curated", "description": "AI-generated, reviewed by SME" }
  ]
}
```

#### Computed Tag Plugin Enhancement

Add `description` property to [backend/app/plugins/base.py](../backend/app/plugins/base.py):

```python
class ComputedTagPlugin(ABC):
    @property
    @abstractmethod
    def tag_key(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the glossary."""
        ...
```

#### Database Storage for SME-Created Tags

Store custom tag definitions in Cosmos DB:

```python
@dataclass
class TagDefinition:
    tag_key: str          # Partition key
    description: str
    created_by: str
    created_at: datetime
    updated_at: datetime
```

Container: `tag_definitions` with partition key `/tag_key`.

#### API Endpoint

`GET /v1/tags/glossary`

Response shape:

```typescript
interface GlossaryResponse {
  version: string;
  groups: Array<{
    name: string;
    description?: string;
    type: "manual" | "computed" | "custom";
    tags: Array<{
      key: string;
      description?: string;
      exclusive?: boolean;
    }>;
  }>;
}
```

The endpoint merges three sources:

1. Manual tag config (JSON file)
2. Computed tag plugins (class properties)
3. Custom tag definitions (database)

### Frontend Changes

#### TagChip Tooltip

Enhance [frontend/src/components/common/TagChip.tsx](../frontend/src/components/common/TagChip.tsx):

- Accept optional `description` prop
- Render Radix UI Tooltip on hover
- Fetch definitions from glossary endpoint and cache in React Query

#### Glossary Management View

New route `/settings/glossary` or modal accessible from settings:

- List all tags organized by group/type
- Inline editing for custom tag definitions
- Read-only display for system tags (manual + computed)
- Search input filtering visible tags

#### TagsEditor Enhancement

Update [frontend/src/components/app/editor/TagsEditor.tsx](../frontend/src/components/app/editor/TagsEditor.tsx):

- Show definition in dropdown when selecting tags
- Consider info icon next to tag groups linking to glossary

## Open Questions

1. **Migration strategy:** Should existing manual_tags.json be migrated in-place, or should a new file structure be introduced?
2. **Localization:** Will tag definitions need translation support in the future?
3. **Versioning:** Should glossary changes be audited for compliance tracking?

## References

- [Computed Tags Design](../docs/computed-tags-design.md)
- [Manual Tags Design](../docs/manual-tags-design.md)
- [backend/app/domain/manual_tags.json](../backend/app/domain/manual_tags.json)
- [backend/app/plugins/base.py](../backend/app/plugins/base.py)
- [frontend/src/components/common/TagChip.tsx](../frontend/src/components/common/TagChip.tsx)
