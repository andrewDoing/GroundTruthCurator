"""Computed tag plugins for question length classification.

This module provides plugins that tag documents based on the word count
of the question (synthQuestion or editedQuestion).

Word count thresholds:
- short: SHORT_MAX_WORDS words or fewer
- medium: SHORT_MAX_WORDS + 1 to MEDIUM_MAX_WORDS words
- long: more than MEDIUM_MAX_WORDS words
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.base import ComputedTagPlugin

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem

# Word count thresholds for question length classification
SHORT_MAX_WORDS = 10  # Questions with this many words or fewer are "short"
MEDIUM_MAX_WORDS = (
    30  # Questions with this many words or fewer (but > SHORT_MAX_WORDS) are "medium"
)


def _get_question_word_count(doc: GroundTruthItem) -> int:
    """Get the word count for the document's question.

    Uses editedQuestion if available, otherwise synthQuestion.
    Uses .split() to count words as specified in requirements.

    Args:
        doc: The GroundTruthItem to evaluate.

    Returns:
        The number of words in the question.
    """
    question = doc.edited_question or doc.synth_question or ""
    return len(question.split())


class QuestionLengthLongPlugin(ComputedTagPlugin):
    """Tags documents with questions longer than MEDIUM_MAX_WORDS words.

    Applies the 'question_length:long' tag if the question has more than MEDIUM_MAX_WORDS words.
    """

    @property
    def tag_key(self) -> str:
        return "question_length:long"

    def compute(self, doc: GroundTruthItem) -> str | None:
        return self.tag_key if _get_question_word_count(doc) > MEDIUM_MAX_WORDS else None


class QuestionLengthMediumPlugin(ComputedTagPlugin):
    """Tags documents with questions between SHORT_MAX_WORDS + 1 and MEDIUM_MAX_WORDS words.

    Applies the 'question_length:medium' tag if the question has SHORT_MAX_WORDS + 1 to MEDIUM_MAX_WORDS words.
    """

    @property
    def tag_key(self) -> str:
        return "question_length:medium"

    def compute(self, doc: GroundTruthItem) -> str | None:
        count = _get_question_word_count(doc)
        return self.tag_key if SHORT_MAX_WORDS < count <= MEDIUM_MAX_WORDS else None


class QuestionLengthShortPlugin(ComputedTagPlugin):
    """Tags documents with questions of SHORT_MAX_WORDS words or fewer.

    Applies the 'question_length:short' tag if the question has SHORT_MAX_WORDS or fewer words.
    """

    @property
    def tag_key(self) -> str:
        return "question_length:short"

    def compute(self, doc: GroundTruthItem) -> str | None:
        return self.tag_key if _get_question_word_count(doc) <= SHORT_MAX_WORDS else None
