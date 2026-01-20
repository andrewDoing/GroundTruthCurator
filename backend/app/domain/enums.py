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
    totalReferences = "totalReferences"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class DocType(str, Enum):
    url = "url"
    file = "file"


class HistoryItemRole(str, Enum):
    user = "user"
    assistant = "assistant"


class ExpectedBehavior(str, Enum):
    """Expected behavior tags for history items in ground truth evaluation.

    These tags describe what the agent should do at each turn of a conversation:
    - tool:search: Agent should perform a search/retrieval operation
    - generation:answer: Agent should generate a direct answer
    - generation:need-context: Agent should ask for more context
    - generation:clarification: Agent should ask for clarification
    - generation:out-of-domain: Agent should indicate the query is out of domain
    """

    tool_search = "tool:search"
    generation_answer = "generation:answer"
    generation_need_context = "generation:need-context"
    generation_clarification = "generation:clarification"
    generation_out_of_domain = "generation:out-of-domain"
