---
title: Manual Tags Design
description: Manual tag configuration, validation, and UX rules for Ground Truth Curator
author: Ground Truth Curator Team
ms.date: 2026-01-20
ms.topic: concept
keywords:
  - tags
  - validation
  - configuration
estimated_reading_time: 6
---

## Scope and goals

Manual tags capture user intent and remain authoritative. Computed tags are system generated and stored separately.

Key goals:

* Keep manual tags as the source of truth in `manualTags`
* Prevent users from writing to computed tags
* Make default manual tags configurable per environment
* Enforce tag rules consistently via validators

For computed-tag derivation and the overall tagging model, see [Computed Tags Design](computed-tags-design.md).

## Data model

Manual tags are represented as `group:tag` strings (for example, `priority:high`).

Ground truth items store manual tags separately from computed tags:

```json
{
  "id": "gt_123",
  "datasetName": "dataset_1",
  "bucket": "uuid-string",
  "manualTags": ["priority:high", "review:needs-review"],
  "computedTags": ["length:long"]
}
```

Read and export paths may expose a merged `tags` view, but that merged field is constructed dynamically and is not authoritative.

## Manual tag provider

Manual tag providers define the source of default manual tags. Defaults power UX experiences like tag pickers and suggestions. They do not restrict what users can enter, since more tags can and will be created by users over time.

Manual tags remain writeable and are not validated against a fixed allowlist. The only hard rule is that users cannot write computed tags.

Interface:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ManualTagGroup:
  group: str
  tags: List[str]
  mutually_exclusive: bool

class ManualTagProvider(ABC):
    @abstractmethod
  def get_default_tag_groups(self) -> List[ManualTagGroup]:
    """Returns default/suggested manual tags for UX defaults, organized by group."""
        raise NotImplementedError
```

Default implementation (JSON file):

```python
import json
from pathlib import Path
from typing import List

class JsonFileManualTagProvider(ManualTagProvider):
  def __init__(self, json_path: Path) -> None:
    self._json_path = json_path

  def get_default_tag_groups(self) -> List[ManualTagGroup]:
    data = json.loads(self._json_path.read_text(encoding="utf-8"))
    groups = data.get("manualTagGroups", [])
    result: List[ManualTagGroup] = []
    for g in groups:
      if not isinstance(g, dict):
        continue
      group = g.get("group")
      tags = g.get("tags", [])
      mutually_exclusive = bool(g.get("mutuallyExclusive", False))

      if not isinstance(group, str):
        continue
      group = group.strip()
      if not group:
        continue

      if not isinstance(tags, list):
        tags = []
      normalized_tags = [t.strip() for t in tags if isinstance(t, str) and t.strip()]

      result.append(
        ManualTagGroup(
          group=group,
          tags=normalized_tags,
          mutually_exclusive=mutually_exclusive,
        )
      )
    return result
```

Recommended JSON format:

```json
{
  "manualTagGroups": [
  {
    "group": "priority",
    "mutuallyExclusive": true,
    "tags": ["low", "medium", "high"]
  },
  {
    "group": "review",
    "mutuallyExclusive": false,
    "tags": ["needs-review", "approved"]
  }
  ]
}
```

Client behavior:

* The UI can render tags grouped by `group`
* When a user selects a group tag value, the stored `manualTags` entry is `group:tag`

Implementation notes:

* Normalize values when ingesting configuration (trim whitespace, drop empty strings)
* Defaults are for UX only. Do not treat them as an allowlist
* Prevent computed tags from being present in defaults

## Tag validation plugins

Validators enforce tag rules on a ground truth item. Validation remains class-based because it is logic-heavy (mutual exclusion, required tags, rule composition).

Interface:

```python
from abc import ABC, abstractmethod
from typing import List

class TagValidator(ABC):
    @abstractmethod
    def validate(self, manual_tags: List[str], computed_tags: List[str]) -> List[str]:
        """Returns a list of error messages if validation fails."""
        raise NotImplementedError
```

Configuration:

* Configure the active `ManualTagProvider` and the list of `TagValidator` implementations via environment variables or a configuration file
* Run validation on write paths (save/update) so the database remains consistent
* Avoid validators that attempt to enforce an allowlist based on the default tag set

## Write-path rules

On save:

* The API accepts updates to `manualTags`
* The API rejects writes to `computedTags`
* The API recomputes `computedTags` from the current derivation rules
* The API strips any computed tag keys that appear in the incoming `manualTags`

## UX rules

* Manual tags are editable
* Computed tags are read-only
* The UI can present computed tags as visually distinct chips with a tooltip such as "Automatically assigned"

## Configuration cleanup and safety checks

To avoid users manually selecting tags that are now computed:

* Remove computed tags from the manual default-tag configuration
* Verify on startup that configured default tags (expanded as `group:tag`) and the computed-tag registry keys are disjoint
* If a legacy `tags` container exists, delete tag documents that represent computed tags so they disappear from the UI tag picker
