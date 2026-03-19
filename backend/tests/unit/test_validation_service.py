from app.domain.models import (
    AgenticGroundTruthEntry,
    ExpectedTools,
    ToolCallRecord,
    ToolExpectation,
)
from app.services.validation_service import collect_approval_validation_errors


def test_approval_validation_accepts_legacy_question_answer_payload():
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "item-1",
            "datasetName": "demo",
            "history": [
                {"role": "user", "msg": "What is Ground Truth Curator?"},
                {"role": "assistant", "msg": "It is a curation application."},
            ],
        }
    )

    assert collect_approval_validation_errors(item) == []


def test_approval_validation_accepts_agent_answer_role():
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "item-agent",
            "datasetName": "demo",
            "history": [
                {"role": "user", "msg": "What is Ground Truth Curator?"},
                {"role": "agent", "msg": "It is a curation application."},
            ],
        }
    )

    assert collect_approval_validation_errors(item) == []


def test_approval_validation_accepts_custom_non_user_answer_role():
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "item-planner",
            "datasetName": "demo",
            "history": [
                {"role": "user", "msg": "Plan the rollout."},
                {"role": "planner", "msg": "Step 1: scope. Step 2: validate."},
            ],
        }
    )

    assert collect_approval_validation_errors(item) == []


def test_approval_validation_rejects_all_user_history():
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "item-all-user",
            "datasetName": "demo",
            "history": [
                {"role": "user", "msg": "Question one"},
                {"role": "user", "msg": "Question two"},
            ],
        }
    )

    assert collect_approval_validation_errors(item) == [
        "history must include at least one agent message"
    ]


def test_approval_validation_requires_required_tool_when_tool_calls_exist():
    item = AgenticGroundTruthEntry(
        id="item-2",
        datasetName="demo",
        history=[
            {"role": "user", "msg": "Find the answer."},
            {"role": "assistant", "msg": "I found it."},
        ],
        toolCalls=[ToolCallRecord(name="search")],
    )

    errors = collect_approval_validation_errors(item)

    assert errors == [
        "expectedTools.required must include at least one tool before approval when toolCalls are present"
    ]


def test_approval_validation_requires_required_tool_to_match_tool_calls():
    item = AgenticGroundTruthEntry(
        id="item-3",
        datasetName="demo",
        history=[
            {"role": "user", "msg": "Find the answer."},
            {"role": "assistant", "msg": "I found it."},
        ],
        toolCalls=[ToolCallRecord(name="search")],
        expectedTools=ExpectedTools(required=[ToolExpectation(name="browser")]),
    )

    errors = collect_approval_validation_errors(item)

    assert errors == ["expectedTools.required references toolCalls that do not exist: browser"]
