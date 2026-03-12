from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TypedDict
from uuid import UUID

from app.adapters.trace_export import TraceExportAdapter
from app.domain.enums import GroundTruthStatus
from app.domain.models import (
    AgenticGroundTruthEntry,
    DatasetCurationInstructions,
    ExpectedTools,
    HistoryEntry,
    HistoryItem,
    Reference,
    ToolExpectation,
)

CUSTOMER_FEEDBACK_BUCKET = UUID("11111111-1111-1111-1111-111111111111")
NETWORK_DIAGNOSTICS_BUCKET = UUID("22222222-2222-2222-2222-222222222222")


class DemoTraceConfig(TypedDict, total=False):
    id: str
    dataset: str
    bucket: UUID
    status: GroundTruthStatus
    assigned: bool
    scenario_id: str
    manual_tags: list[str]
    comment: str
    refs: list[Reference]
    required_tools: list[str]
    reviewed_at: datetime
    updated_by: str


def _ts(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _result(payload: dict[str, object]) -> str:
    return json.dumps(payload)


def _reference(url: str, title: str, content: str, *, excerpt: str | None = None) -> Reference:
    return Reference(url=url, title=title, content=content, keyExcerpt=excerpt)


def _trace(
    *,
    trace_id: str,
    conversation_id: str,
    feedback_at: datetime,
    user_query: str,
    chat_response: str,
    rca: str,
    tool_calls: list[dict[str, object]],
    resolution: str,
    additional_feedback: dict[str, int],
    impacted_device: str,
    feedback_type: str = "like",
    comment: str = "",
) -> dict[str, object]:
    return {
        "id": trace_id,
        "cid_list": [conversation_id],
        "uid": "[REDACTED_UID]",
        "impacted_device_type": "MSISDN",
        "impacted_device": impacted_device,
        "metric_name": "user feedback",
        "type": feedback_type,
        "comment": comment,
        "additional_feedback": additional_feedback,
        "resolution": resolution,
        "feedback_date": int(feedback_at.timestamp()),
        "feedback_datetime_utc": feedback_at.isoformat(),
        "chat_history": [
            {
                "user_query": user_query,
                "chat_response": chat_response,
                "rca": rca,
                "context": tool_calls,
            }
        ],
    }


def _tool_call(
    *,
    tool_id: str,
    run_id: str,
    name: str,
    arguments: str,
    result: dict[str, object],
    execution_time: float,
) -> dict[str, object]:
    return {
        "id": tool_id,
        "run_id": run_id,
        "function_name": name,
        "function_arguments": arguments,
        "function_result": _result(result),
        "execution_time": execution_time,
    }


DEMO_TRACE_EXPORTS: list[tuple[dict[str, object], DemoTraceConfig]] = [
    (
        _trace(
            trace_id="a4d42fa7-a99c-47a4-8f04-11e80067b001",
            conversation_id="demo-cid-001",
            feedback_at=_ts(2026, 2, 18, 8, 57),
            user_query="CX IS USING TOO MUCH DATA AND WANTS TO KNOW WHY",
            chat_response=(
                "The analysis shows a sustained increase in mobile data usage over the last week, with the "
                "largest spikes occurring during evening video sessions. The account stayed on cellular data "
                "for several long sessions and did not fall back to Wi-Fi."
            ),
            rca=(
                "### Root Cause\nThe customer exceeded the 50 GB allowance on the Premium Data Plan after "
                "streaming and hotspot usage stayed on cellular data. No provisioning or outage issue was found."
            ),
            resolution="CX WAS NOT ON WIFI AND OVERLY USING DATA",
            impacted_device="[REDACTED_MSISDN_001]",
            additional_feedback={
                "The recommended resolution was correct and appropriate": 2,
                "The explanation and investigation areas were relevant to the issue": 2,
                "The explanation of how the RCA was reached was clear": 2,
                "The RCA included all key information (nothing important was missed)": 2,
            },
            tool_calls=[
                _tool_call(
                    tool_id="tool-001",
                    run_id="run-001",
                    name="get_location",
                    arguments="msisdn='[REDACTED_MSISDN_001]' context=None",
                    result={"response": {"items": [{"valueObject": {"location": {"wifiConnected": False}}}]}},
                    execution_time=2.41,
                ),
                _tool_call(
                    tool_id="tool-002",
                    run_id="run-001",
                    name="get_plan_usage",
                    arguments="msisdn='[REDACTED_MSISDN_001]' context=None",
                    result={"response": {"items": [{"valueObject": {"planLimitGb": 50, "usageGb": 63}}]}},
                    execution_time=1.83,
                ),
                _tool_call(
                    tool_id="tool-003",
                    run_id="run-001",
                    name="Billing_agent",
                    arguments="msisdn='[REDACTED_MSISDN_001]' context=None",
                    result={"response": {"summary": "Overage charges align with plan cap breach."}},
                    execution_time=1.17,
                ),
            ],
        ),
        {
            "id": "demo-data-overage",
            "dataset": "customer-feedback",
            "bucket": CUSTOMER_FEEDBACK_BUCKET,
            "status": GroundTruthStatus.draft,
            "assigned": True,
            "scenario_id": "feedback-data-overage",
            "manual_tags": ["issue:data-usage", "resolution:wifi-education"],
            "comment": "High-signal example that mirrors the redacted RCA flow.",
            "refs": [
                _reference(
                    "https://telco.example.com/help/data-usage/check-usage",
                    "Check mobile data usage",
                    "Use the account usage view to compare current-cycle consumption against the plan cap.",
                    excerpt="Current cycle usage can exceed the allowance before the invoice closes.",
                ),
                _reference(
                    "https://telco.example.com/help/data-usage/wifi-assist",
                    "Reduce cellular usage with Wi-Fi",
                    "Encourage customers to enable Wi-Fi for streaming and hotspot-heavy sessions when available.",
                    excerpt="Streaming over cellular is a common source of overage charges.",
                ),
            ],
            "required_tools": ["get_location", "get_plan_usage", "Billing_agent"],
        },
    ),
    (
        _trace(
            trace_id="b7d42fa7-a99c-47a4-8f04-11e80067b002",
            conversation_id="demo-cid-002",
            feedback_at=_ts(2026, 2, 21, 10, 12),
            user_query="CUSTOMER SAYS HOTSPOT USAGE SPIKED OVER THE WEEKEND",
            chat_response=(
                "Weekend usage was concentrated on tethering sessions from a single handset. The usage pattern "
                "matches a laptop hotspot workflow rather than background network activity."
            ),
            rca=(
                "### Root Cause\nThe line used 18 GB of hotspot traffic across two tethered devices during a "
                "road trip. The usage is expected and does not indicate fraud or a network defect."
            ),
            resolution="HOTSPOT TRAFFIC DROVE THE WEEKEND DATA SPIKE",
            impacted_device="[REDACTED_MSISDN_002]",
            additional_feedback={
                "The recommended resolution was correct and appropriate": 2,
                "The explanation and investigation areas were relevant to the issue": 2,
                "The explanation of how the RCA was reached was clear": 1,
                "The RCA included all key information (nothing important was missed)": 2,
            },
            tool_calls=[
                _tool_call(
                    tool_id="tool-101",
                    run_id="run-002",
                    name="get_device_details",
                    arguments="msisdn='[REDACTED_MSISDN_002]' context=None",
                    result={"response": {"items": [{"valueObject": {"deviceModel": "Phone X", "hotspotCapable": True}}]}},
                    execution_time=1.24,
                ),
                _tool_call(
                    tool_id="tool-102",
                    run_id="run-002",
                    name="get_hotspot_usage",
                    arguments="msisdn='[REDACTED_MSISDN_002]' context=None",
                    result={"response": {"items": [{"valueObject": {"hotspotUsageGb": 18, "window": "48h"}}]}},
                    execution_time=1.76,
                ),
                _tool_call(
                    tool_id="tool-103",
                    run_id="run-002",
                    name="Data_agent",
                    arguments="msisdn='[REDACTED_MSISDN_002]' context=None",
                    result={"response": {"summary": "No anomaly detected beyond tethering usage."}},
                    execution_time=1.09,
                ),
            ],
        ),
        {
            "id": "demo-hotspot-weekend",
            "dataset": "customer-feedback",
            "bucket": CUSTOMER_FEEDBACK_BUCKET,
            "status": GroundTruthStatus.draft,
            "assigned": True,
            "scenario_id": "feedback-hotspot-weekend",
            "manual_tags": ["issue:hotspot-usage", "channel:billing"],
            "comment": "Assigned draft focused on hotspot RCA and customer coaching.",
            "refs": [
                _reference(
                    "https://telco.example.com/help/hotspot/usage-breakdown",
                    "Understand hotspot usage",
                    "Hotspot sessions are billed against the same plan cap and can create sharp short-term spikes.",
                ),
                _reference(
                    "https://telco.example.com/help/hotspot/manage-devices",
                    "Manage tethered devices",
                    "Review device-level tethering behavior before escalating a data spike as suspicious.",
                ),
            ],
            "required_tools": ["get_hotspot_usage", "Data_agent"],
        },
    ),
    (
        _trace(
            trace_id="c8d42fa7-a99c-47a4-8f04-11e80067b003",
            conversation_id="demo-cid-003",
            feedback_at=_ts(2026, 2, 16, 14, 30),
            user_query="CUSTOMER WAS CHARGED ROAMING FEES EVEN THOUGH THEY BOUGHT A PASS",
            chat_response=(
                "The roaming pass was purchased after the first day of travel, so the initial sessions were "
                "billed at standard roaming rates. Later usage correctly applied the travel pass."
            ),
            rca=(
                "### Root Cause\nCharges occurred before the pass activation timestamp. The network and "
                "provisioning states were healthy, and billing aligned with the order timeline."
            ),
            resolution="ROAMING PASS ACTIVATED AFTER THE FIRST CHARGED SESSION",
            impacted_device="[REDACTED_MSISDN_003]",
            additional_feedback={
                "The recommended resolution was correct and appropriate": 2,
                "The explanation and investigation areas were relevant to the issue": 2,
                "The explanation of how the RCA was reached was clear": 2,
                "The RCA included all key information (nothing important was missed)": 2,
            },
            tool_calls=[
                _tool_call(
                    tool_id="tool-201",
                    run_id="run-003",
                    name="get_roaming_usage",
                    arguments="msisdn='[REDACTED_MSISDN_003]' context=None",
                    result={"response": {"items": [{"valueObject": {"chargedSessions": 3, "passCoveredSessions": 9}}]}},
                    execution_time=1.58,
                ),
                _tool_call(
                    tool_id="tool-202",
                    run_id="run-003",
                    name="search_fixit_flows",
                    arguments="query='roaming pass activation timeline'",
                    result={"response": {"items": [{"title": "Roaming pass timing", "score": 0.94}]}}
                    ,
                    execution_time=0.89,
                ),
                _tool_call(
                    tool_id="tool-203",
                    run_id="run-003",
                    name="Billing_agent",
                    arguments="msisdn='[REDACTED_MSISDN_003]' context=None",
                    result={"response": {"summary": "Billing timeline and pass activation are aligned."}},
                    execution_time=1.11,
                ),
            ],
        ),
        {
            "id": "demo-roaming-pass-timing",
            "dataset": "network-diagnostics",
            "bucket": NETWORK_DIAGNOSTICS_BUCKET,
            "status": GroundTruthStatus.approved,
            "assigned": False,
            "scenario_id": "diagnostics-roaming-pass",
            "manual_tags": ["issue:roaming", "status:approved-demo"],
            "comment": "Approved example that demonstrates a clean billing RCA.",
            "refs": [
                _reference(
                    "https://telco.example.com/help/roaming/travel-pass-timing",
                    "Travel pass activation timing",
                    "Travel passes only apply after activation and do not retroactively credit earlier sessions.",
                )
            ],
            "required_tools": ["get_roaming_usage", "Billing_agent"],
            "reviewed_at": _ts(2026, 2, 17, 9, 5),
            "updated_by": "reviewer@example.com",
        },
    ),
    (
        _trace(
            trace_id="d9d42fa7-a99c-47a4-8f04-11e80067b004",
            conversation_id="demo-cid-004",
            feedback_at=_ts(2026, 2, 24, 11, 45),
            user_query="CUSTOMER LOST 5G AFTER A SIM SWAP AND WANTS TO KNOW IF PROVISIONING IS STUCK",
            chat_response=(
                "Provisioning records show the new SIM attached successfully, but the line has not yet completed "
                "the final 5G feature refresh. The issue is recoverable through a backend refresh."
            ),
            rca=(
                "### Root Cause\nThe SIM swap completed, but the 5G entitlement refresh did not run after the "
                "change event. A provisioning retry is appropriate before deeper escalation."
            ),
            resolution="5G ENTITLEMENT REFRESH DID NOT COMPLETE AFTER SIM SWAP",
            impacted_device="[REDACTED_MSISDN_004]",
            additional_feedback={
                "The recommended resolution was correct and appropriate": 1,
                "The explanation and investigation areas were relevant to the issue": 2,
                "The explanation of how the RCA was reached was clear": 1,
                "The RCA included all key information (nothing important was missed)": 1,
            },
            tool_calls=[
                _tool_call(
                    tool_id="tool-301",
                    run_id="run-004",
                    name="get_subscription_status",
                    arguments="msisdn='[REDACTED_MSISDN_004]' context=None",
                    result={"response": {"items": [{"valueObject": {"simState": "active", "featureSet": ["LTE"]}}]}},
                    execution_time=1.42,
                ),
                _tool_call(
                    tool_id="tool-302",
                    run_id="run-004",
                    name="qtm_provisioning_status_daily_query",
                    arguments="msisdn='[REDACTED_MSISDN_004]' days=3",
                    result={"response": {"items": [{"valueObject": {"lastRefresh": "failed", "attempts": 2}}]}},
                    execution_time=2.03,
                ),
                _tool_call(
                    tool_id="tool-303",
                    run_id="run-004",
                    name="Data_agent",
                    arguments="msisdn='[REDACTED_MSISDN_004]' context=None",
                    result={"response": {"summary": "Retry provisioning before opening a network ticket."}},
                    execution_time=1.31,
                ),
            ],
        ),
        {
            "id": "demo-sim-swap-refresh",
            "dataset": "network-diagnostics",
            "bucket": NETWORK_DIAGNOSTICS_BUCKET,
            "status": GroundTruthStatus.skipped,
            "assigned": False,
            "scenario_id": "diagnostics-sim-swap-refresh",
            "manual_tags": ["issue:provisioning", "status:needs-follow-up"],
            "comment": "Skipped item keeps reclaim and retry flows visible in demo mode.",
            "refs": [
                _reference(
                    "https://telco.example.com/help/provisioning/sim-swap-refresh",
                    "Refresh service after SIM swap",
                    "If feature entitlements lag a SIM swap, run a targeted refresh before escalating to network engineering.",
                )
            ],
            "required_tools": ["get_subscription_status", "qtm_provisioning_status_daily_query"],
        },
    ),
    (
        _trace(
            trace_id="ead42fa7-a99c-47a4-8f04-11e80067b005",
            conversation_id="demo-cid-005",
            feedback_at=_ts(2026, 2, 14, 17, 20),
            user_query="CUSTOMER THINKS THERE WAS AN OUTAGE WHEN DATA SLOWED DOWN AT A STADIUM",
            chat_response=(
                "The network view shows a temporary congestion event around the venue with recovery later in the "
                "evening. The account, device, and provisioning checks were otherwise healthy."
            ),
            rca=(
                "### Root Cause\nTemporary cell congestion reduced throughput during a high-density event. "
                "This was not caused by account misconfiguration, and no persistent defect remained afterward."
            ),
            resolution="SHORT-LIVED CELL CONGESTION DURING A HIGH-DENSITY EVENT",
            impacted_device="[REDACTED_MSISDN_005]",
            additional_feedback={
                "The recommended resolution was correct and appropriate": 2,
                "The explanation and investigation areas were relevant to the issue": 1,
                "The explanation of how the RCA was reached was clear": 1,
                "The RCA included all key information (nothing important was missed)": 1,
            },
            tool_calls=[
                _tool_call(
                    tool_id="tool-401",
                    run_id="run-005",
                    name="get_location",
                    arguments="msisdn='[REDACTED_MSISDN_005]' context=None",
                    result={"response": {"items": [{"valueObject": {"cellSector": "STADIUM-12"}}]}},
                    execution_time=1.51,
                ),
                _tool_call(
                    tool_id="tool-402",
                    run_id="run-005",
                    name="qtm_cellsector_ref_query",
                    arguments="sector='STADIUM-12' hours=12",
                    result={"response": {"items": [{"valueObject": {"congestionEvent": True, "peakUsers": 1840}}]}},
                    execution_time=1.92,
                ),
                _tool_call(
                    tool_id="tool-403",
                    run_id="run-005",
                    name="qtm_device_connectivity_kpis_7d_rolling_query",
                    arguments="msisdn='[REDACTED_MSISDN_005]' days=7",
                    result={"response": {"items": [{"valueObject": {"drops": 0, "attachSuccessRate": 0.99}}]}},
                    execution_time=2.27,
                ),
            ],
        ),
        {
            "id": "demo-stadium-congestion",
            "dataset": "network-diagnostics",
            "bucket": NETWORK_DIAGNOSTICS_BUCKET,
            "status": GroundTruthStatus.deleted,
            "assigned": False,
            "scenario_id": "diagnostics-stadium-congestion",
            "manual_tags": ["issue:congestion", "status:archived-demo"],
            "comment": "Deleted sample preserves restore/delete flows with trace-heavy evidence.",
            "refs": [
                _reference(
                    "https://telco.example.com/help/network/event-congestion",
                    "Understand temporary event congestion",
                    "Large venues can saturate nearby sectors briefly without indicating a persistent service problem.",
                )
            ],
            "required_tools": ["get_location", "qtm_cellsector_ref_query"],
        },
    ),
]


def _hydrate_history_with_refs(item: AgenticGroundTruthEntry, refs: list[Reference]) -> None:
    if not item.history:
        return

    enriched_history: list[HistoryEntry] = []
    last_turn_index = len(item.history) - 1
    for index, turn in enumerate(item.history):
        enriched_history.append(
            HistoryItem(
                role=turn.role,
                msg=turn.msg,
                refs=refs if index == last_turn_index and turn.role != "user" else None,
            )
        )
    item.history = enriched_history


def _expected_tools(tool_names: list[str]) -> ExpectedTools:
    return ExpectedTools(required=[ToolExpectation(name=name) for name in tool_names])


def _build_demo_item(
    trace: dict[str, object],
    *,
    item_id: str,
    dataset: str,
    bucket: UUID,
    status: GroundTruthStatus,
    demo_user_id: str,
    assigned: bool,
    scenario_id: str,
    manual_tags: list[str],
    comment: str,
    refs: list[Reference],
    required_tools: list[str],
    reviewed_at: datetime | None = None,
    updated_by: str | None = None,
) -> AgenticGroundTruthEntry:
    adapter = TraceExportAdapter(
        dataset_name=dataset,
        bucket=bucket,
        status=status,
        created_by="demo-seed",
    )
    adapted = adapter.adapt_payload({"trace_count": 1, "traces": [trace]})[0]
    item = AgenticGroundTruthEntry.model_validate(adapted.model_dump(by_alias=True))

    item.id = item_id
    item.scenario_id = scenario_id
    item.comment = comment
    item.manual_tags = sorted(set(item.manual_tags + manual_tags))
    item.metadata = {**item.metadata, "source": "demo-seed"}
    item.trace_ids = {**(item.trace_ids or {}), "demoItemId": item_id}
    item.refs = refs
    _hydrate_history_with_refs(item, refs)
    item.expected_tools = _expected_tools(required_tools)

    if assigned:
        item.assignedTo = demo_user_id
        item.assigned_at = item.created_at

    if reviewed_at is not None:
        item.reviewed_at = reviewed_at
        item.updated_at = reviewed_at
    if updated_by is not None:
        item.updatedBy = updated_by

    return item


def build_demo_items(demo_user_id: str) -> list[AgenticGroundTruthEntry]:
    items: list[AgenticGroundTruthEntry] = []
    for trace, config in DEMO_TRACE_EXPORTS:
        items.append(
            _build_demo_item(
                trace,
                item_id=config["id"],
                dataset=config["dataset"],
                bucket=config["bucket"],
                status=config["status"],
                demo_user_id=demo_user_id,
                assigned=config["assigned"],
                scenario_id=config["scenario_id"],
                manual_tags=config["manual_tags"],
                comment=config["comment"],
                refs=config["refs"],
                required_tools=config["required_tools"],
                reviewed_at=config.get("reviewed_at"),
                updated_by=config.get("updated_by"),
            )
        )
    return items


DEMO_CURATION_INSTRUCTIONS: list[DatasetCurationInstructions] = [
    DatasetCurationInstructions(
        id="curation-customer-feedback",
        datasetName="customer-feedback",
        bucket=UUID("00000000-0000-0000-0000-000000000000"),
        instructions=(
            "### Customer Feedback Demo Instructions\n\n"
            "- Preserve the customer symptom exactly as reported before editing the RCA.\n"
            "- Prefer explanations that tie plan limits, Wi-Fi usage, tethering, or billing timing back to the observed evidence.\n"
            "- If the trace shows no defect, state that clearly and avoid inventing remediation work."
        ),
        updatedAt=_ts(2026, 2, 20, 8, 0),
        updatedBy="demo-seed",
    ),
    DatasetCurationInstructions(
        id="curation-network-diagnostics",
        datasetName="network-diagnostics",
        bucket=UUID("00000000-0000-0000-0000-000000000000"),
        instructions=(
            "### Network Diagnostics Demo Instructions\n\n"
            "- Anchor the answer in the observed tool evidence and distinguish congestion, provisioning, and billing causes.\n"
            "- Call out when a retry or refresh is appropriate before escalation.\n"
            "- Keep RCA sections explicit so curators can quickly verify the reasoning path."
        ),
        updatedAt=_ts(2026, 2, 22, 8, 0),
        updatedBy="demo-seed",
    ),
]
