from __future__ import annotations

from app.domain.models import AgenticGroundTruthEntry

_ANSWER_ROLES = {"assistant", "output-agent", "orchestrator-agent"}


def question_text_from_item(item: AgenticGroundTruthEntry) -> str:
    for turn in item.history or []:
        if turn.role.strip().lower() == "user" and turn.msg.strip():
            return turn.msg.strip()
    return ""


def answer_text_from_item(item: AgenticGroundTruthEntry) -> str:
    for turn in reversed(item.history or []):
        if turn.role.strip().lower() in _ANSWER_ROLES and turn.msg.strip():
            return turn.msg.strip()
    return ""
