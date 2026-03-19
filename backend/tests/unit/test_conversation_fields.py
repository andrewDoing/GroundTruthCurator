from app.domain.conversation_fields import (
    answer_text_from_item,
    is_non_user_role,
    is_user_role,
    question_text_from_item,
)
from app.domain.models import AgenticGroundTruthEntry


def test_role_helpers_use_strict_user_semantics():
    assert is_user_role("user")
    assert is_user_role(" User ")
    assert not is_user_role("assistant")
    assert not is_user_role("planner")

    assert not is_non_user_role("user")
    assert is_non_user_role("assistant")
    assert is_non_user_role("planner")


def test_question_and_answer_derivation_follow_user_vs_non_user_contract():
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "item-role-derivation",
            "datasetName": "demo",
            "history": [
                {"role": "user", "msg": "Initial question"},
                {"role": "planner", "msg": "Draft answer"},
                {"role": "user", "msg": "Follow-up"},
                {"role": "assistant", "msg": "Final answer"},
            ],
        }
    )

    assert question_text_from_item(item) == "Follow-up"
    assert answer_text_from_item(item) == "Final answer"
