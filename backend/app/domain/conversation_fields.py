from __future__ import annotations

from app.domain.models import AgenticGroundTruthEntry


def _normalize_role(role: str) -> str:
    return role.strip().lower()


def is_user_role(role: str) -> bool:
    return _normalize_role(role) == "user"


def is_non_user_role(role: str) -> bool:
    return not is_user_role(role)


def question_text_from_item(item: AgenticGroundTruthEntry) -> str:
    for turn in reversed(item.history or []):
        if is_user_role(turn.role) and turn.msg.strip():
            return turn.msg.strip()
    return ""


def answer_text_from_item(item: AgenticGroundTruthEntry) -> str:
    for turn in reversed(item.history or []):
        if is_non_user_role(turn.role) and turn.msg.strip():
            return turn.msg.strip()
    return ""
