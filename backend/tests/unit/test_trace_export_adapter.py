from __future__ import annotations

from app.plugins.adapters.trace_export import TraceExportAdapter


def test_trace_export_adapter_maps_trace_into_agentic_ground_truth() -> None:
    payload = {
        "trace_count": 1,
        "traces": [
            {
                "id": "trace-123",
                "cid_list": ["conversation-456"],
                "uid": "user-789",
                "impacted_device_type": "MSISDN",
                "impacted_device": "[REDACTED_MSISDN]",
                "metric_name": "user feedback",
                "type": "like",
                "comment": "",
                "additional_feedback": {
                    "The recommended resolution was correct and appropriate": 2,
                },
                "resolution": "CUSTOMER WAS ON CELLULAR DATA INSTEAD OF WIFI",
                "feedback_date": 1771405033,
                "feedback_datetime_utc": "2026-02-18T08:57:13+00:00",
                "chat_history": [
                    {
                        "user_query": "CX IS USING TOO MUCH DATA AND WANTS TO KNOW WHY",
                        "chat_response": "Analysis shows the account remained on cellular data.",
                        "rca": "### Root Cause\nThe plan cap was exceeded after streaming on mobile data.",
                        "context": [
                            {
                                "id": "tool-1",
                                "run_id": "run-1",
                                "function_name": "get_plan_usage",
                                "function_arguments": "msisdn='[REDACTED_MSISDN]' context=None",
                                "function_result": '{"response":{"items":[{"valueObject":{"planLimitGb":50,"usageGb":63}}]}}',
                                "execution_time": 1.83,
                            }
                        ],
                    }
                ],
            }
        ],
    }

    adapter = TraceExportAdapter(dataset_name="customer-feedback")
    [item] = adapter.adapt_payload(payload)

    assert item.id == "trace-trace-123"
    assert item.datasetName == "customer-feedback"
    assert item.scenario_id == "trace-export:trace-123"
    assert item.synth_question == "CX IS USING TOO MUCH DATA AND WANTS TO KNOW WHY"
    assert item.answer is not None
    assert "Root Cause" in item.answer
    assert item.comment == "CUSTOMER WAS ON CELLULAR DATA INSTEAD OF WIFI"
    assert item.trace_ids == {
        "traceId": "trace-123",
        "conversationId": "conversation-456",
        "userId": "user-789",
    }

    assert len(item.context_entries) >= 1
    assert item.metadata["sourceFormat"] == "trace-export"
    assert item.metadata["toolCallCount"] == 1
    assert item.trace_payload["resolution"] == "CUSTOMER WAS ON CELLULAR DATA INSTEAD OF WIFI"

    [tool_call] = item.tool_calls
    assert tool_call.name == "get_plan_usage"
    assert tool_call.arguments == {
        "msisdn": "[REDACTED_MSISDN]",
        "context": None,
    }
    assert tool_call.response == {
        "result": {
            "response": {
                "items": [{"valueObject": {"planLimitGb": 50, "usageGb": 63}}],
            }
        },
        "executionTimeSeconds": 1.83,
        "runId": "run-1",
    }

    assert [entry.source for entry in item.feedback] == [
        "trace-export-summary",
        "trace-export-ratings",
    ]
    assert item.feedback[1].values["The recommended resolution was correct and appropriate"] == 2
