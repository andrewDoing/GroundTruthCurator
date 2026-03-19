from enum import Enum


class GroundTruthStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    deleted = "deleted"
    skipped = "skipped"


class SortField(str, Enum):
    reviewed_at = "reviewedAt"
    updated_at = "updatedAt"
    id = "id"
    has_answer = "hasAnswer"
    tag_count = "tagCount"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class DocType(str, Enum):
    url = "url"
    file = "file"


class HistoryItemRole(str, Enum):
    """Legacy RAG compatibility enum.

    The generic host model accepts arbitrary role strings; this enum remains only for
    compatibility helpers, older tests, and the future RAG pack.
    """

    user = "user"
    assistant = "assistant"


class ExpectedBehavior(str, Enum):
    """Legacy RAG compatibility enum for history annotations.

    The generic host model uses `expectedTools` plus plugin-owned data instead of fixed
    top-level expected-behavior assumptions. This enum remains only for compatibility
    helpers, older tests, and the future RAG pack.
    """

    tool_search = "tool:search"
    generation_answer = "generation:answer"
    generation_need_context = "generation:need-context"
    generation_clarification = "generation:clarification"
    generation_out_of_domain = "generation:out-of-domain"
