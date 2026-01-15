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


# Tag group enums (values used to populate the tag schema)


class SourceTag(str, Enum):
    # mutually exclusive
    sme = "sme"
    sa = "sa"  # support assistant
    synthetic = "synthetic"
    sme_curated = "sme_curated"
    user = "user"
    other = "other"


class AnswerabilityTag(str, Enum):
    # mutually exclusive
    answerable = "answerable"
    not_answerable = "not_answerable"
    should_not_answer = "should_not_answer"


# application specific tags should move to configuration


class TopicTag(str, Enum):
    # multi-select allowed
    # set to topics that apply to all products only
    general = "general"
    compatibility = "compatibility"
    install = "install"
    license = "license"
    performance = "performance"
    security = "security"


class IntentTypeTag(str, Enum):
    # multi-select allowed
    informational = "informational"
    action = "action"
    feedback = "feedback"
    clarification = "clarification"
    other = "other"


class QueryExpertiseVariationTag(str, Enum):
    # mutually exclusive
    expert = "expert"
    novice = "novice"


class DifficultyTag(str, Enum):
    # mutually exclusive
    easy = "easy"
    medium = "medium"
    hard = "hard"


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
