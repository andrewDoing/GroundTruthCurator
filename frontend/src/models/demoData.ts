import type { GroundTruthItem } from "./groundTruth";
import type { Provider } from "./provider";
import { JsonProvider } from "./provider";

export const DEMO_JSON: GroundTruthItem[] = [
	{
		id: "demo-data-overage",
		providerId: "json",
		question: "CX IS USING TOO MUCH DATA AND WANTS TO KNOW WHY",
		answer:
			"The RCA shows the line exceeded the 50 GB plan cap after extended streaming and hotspot activity stayed on cellular data instead of Wi-Fi.",
		history: [
			{
				role: "user",
				content: "CX IS USING TOO MUCH DATA AND WANTS TO KNOW WHY",
			},
			{
				role: "assistant",
				content:
					"The usage spike came from long streaming sessions and tethering while the handset was off Wi-Fi. No outage or provisioning defect was detected, so the best resolution is to explain the plan cap and coach the customer toward Wi-Fi-heavy usage.",
			},
		],
		contextEntries: [
			{ key: "impacted_device_type", value: "MSISDN" },
			{ key: "metric_name", value: "user feedback" },
			{ key: "resolution", value: "CX WAS NOT ON WIFI AND OVERLY USING DATA" },
		],
		toolCalls: [
			{
				id: "tool-001",
				name: "get_location",
				callType: "tool",
				stepNumber: 1,
				arguments: { msisdn: "[REDACTED_MSISDN_001]", context: null },
				response: {
					result: {
						response: {
							items: [{ valueObject: { location: { wifiConnected: false } } }],
						},
					},
					executionTimeSeconds: 2.41,
				},
			},
			{
				id: "tool-002",
				name: "get_plan_usage",
				callType: "tool",
				stepNumber: 2,
				arguments: { msisdn: "[REDACTED_MSISDN_001]", context: null },
				response: {
					result: {
						response: {
							items: [{ valueObject: { planLimitGb: 50, usageGb: 63 } }],
						},
					},
					executionTimeSeconds: 1.83,
				},
			},
			{
				id: "tool-003",
				name: "Billing_agent",
				callType: "tool",
				stepNumber: 3,
				arguments: { msisdn: "[REDACTED_MSISDN_001]", context: null },
				response: {
					result: {
						response: {
							summary: "Overage charges align with the plan cap breach.",
						},
					},
					executionTimeSeconds: 1.17,
				},
			},
		],
		expectedTools: {
			required: [{ name: "get_plan_usage" }, { name: "Billing_agent" }],
		},
		feedback: [
			{
				source: "trace-export-ratings",
				values: {
					"The recommended resolution was correct and appropriate": 2,
					"The explanation and investigation areas were relevant to the issue": 2,
				},
			},
		],
		metadata: {
			sourceFormat: "trace-export",
			datasetTheme: "customer-feedback",
		},
		traceIds: {
			traceId: "demo-trace-001",
			conversationId: "demo-cid-001",
		},
		tracePayload: {
			resolution: "CX WAS NOT ON WIFI AND OVERLY USING DATA",
			impacted_device_type: "MSISDN",
		},
		plugins: {
			"rag-compat": {
				kind: "rag-compat",
				version: "1.0",
				data: {
					retrievals: {
						"tool-002": {
							candidates: [
								{
									url: "https://telco.example.com/help/data-usage/check-usage",
									title: "Check mobile data usage",
									chunk:
										"Compare the current-cycle data total with the plan cap before treating the usage as anomalous.",
									toolCallId: "tool-002",
								},
							],
						},
						"tool-003": {
							candidates: [
								{
									url: "https://telco.example.com/help/data-usage/wifi-assist",
									title: "Reduce cellular usage with Wi-Fi",
									chunk:
										"Streaming over cellular is a common source of overage charges when Wi-Fi is available.",
									toolCallId: "tool-003",
								},
							],
						},
					},
				},
			},
		},
		status: "draft",
		deleted: false,
		tags: ["data-usage", "billing", "wifi"],
		comment: "Trace-style draft item with tool evidence and curator ratings.",
		curationInstructions: `
### Curation Guidelines (Customer Feedback)

- Keep the customer symptom intact before refining the RCA.
- Tie the answer back to the specific tool evidence.
- If the trace shows no defect, say so clearly.
`,
		datasetName: "customer-feedback",
	},
	{
		id: "demo-roaming-pass-timing",
		providerId: "json",
		question:
			"CUSTOMER WAS CHARGED ROAMING FEES EVEN THOUGH THEY BOUGHT A PASS",
		answer:
			"The travel pass activated after the first charged roaming session, so the early usage billed at standard rates and later usage correctly switched to the pass.",
		history: [
			{
				role: "user",
				content:
					"CUSTOMER WAS CHARGED ROAMING FEES EVEN THOUGH THEY BOUGHT A PASS",
			},
			{
				role: "assistant",
				content:
					"The billing timeline is consistent with the pass order. The pass was not active for the first day of travel, so those sessions remained chargeable, and no network defect was present.",
			},
		],
		contextEntries: [
			{ key: "impacted_device_type", value: "MSISDN" },
			{ key: "metric_name", value: "user feedback" },
			{
				key: "resolution",
				value: "ROAMING PASS ACTIVATED AFTER THE FIRST CHARGED SESSION",
			},
		],
		toolCalls: [
			{
				id: "tool-201",
				name: "get_roaming_usage",
				callType: "tool",
				stepNumber: 1,
				arguments: { msisdn: "[REDACTED_MSISDN_003]", context: null },
				response: {
					result: {
						response: {
							items: [
								{ valueObject: { chargedSessions: 3, passCoveredSessions: 9 } },
							],
						},
					},
					executionTimeSeconds: 1.58,
				},
			},
			{
				id: "tool-203",
				name: "Billing_agent",
				callType: "tool",
				stepNumber: 2,
				arguments: { msisdn: "[REDACTED_MSISDN_003]", context: null },
				response: {
					result: {
						response: {
							summary: "Billing timeline and pass activation are aligned.",
						},
					},
					executionTimeSeconds: 1.11,
				},
			},
		],
		expectedTools: {
			required: [{ name: "get_roaming_usage" }, { name: "Billing_agent" }],
		},
		feedback: [
			{
				source: "trace-export-ratings",
				values: {
					"The recommended resolution was correct and appropriate": 2,
					"The RCA included all key information (nothing important was missed)": 2,
				},
			},
		],
		metadata: {
			sourceFormat: "trace-export",
			datasetTheme: "network-diagnostics",
		},
		traceIds: {
			traceId: "demo-trace-003",
			conversationId: "demo-cid-003",
		},
		plugins: {
			"rag-compat": {
				kind: "rag-compat",
				version: "1.0",
				data: {
					retrievals: {
						"tool-201": {
							candidates: [
								{
									url: "https://telco.example.com/help/roaming/travel-pass-timing",
									title: "Travel pass activation timing",
									chunk:
										"Travel passes only apply after activation and do not retroactively cover earlier roaming sessions.",
									toolCallId: "tool-201",
								},
							],
						},
					},
				},
			},
		},
		status: "approved",
		deleted: false,
		tags: ["roaming", "billing", "approved"],
		comment: "Approved trace-style example for billing RCA review.",
		curationInstructions: `
### Curation Guidelines (Network Diagnostics)

- Distinguish billing timing from device or network faults.
- State when the evidence rules out an outage.
- Keep the root cause specific and checkable.
`,
		datasetName: "network-diagnostics",
	},
	{
		id: "demo-stadium-congestion",
		providerId: "json",
		question:
			"CUSTOMER THINKS THERE WAS AN OUTAGE WHEN DATA SLOWED DOWN AT A STADIUM",
		answer:
			"The slowdown was caused by short-lived cell congestion during a high-density event, not by a persistent account or device problem.",
		history: [
			{
				role: "user",
				content:
					"CUSTOMER THINKS THERE WAS AN OUTAGE WHEN DATA SLOWED DOWN AT A STADIUM",
			},
			{
				role: "assistant",
				content:
					"Nearby cell sectors were saturated during the event window and recovered later the same evening. The line and handset remained healthy, so this is best handled as a temporary congestion explanation rather than a defect ticket.",
			},
		],
		contextEntries: [
			{ key: "impacted_device_type", value: "MSISDN" },
			{ key: "metric_name", value: "user feedback" },
			{
				key: "resolution",
				value: "SHORT-LIVED CELL CONGESTION DURING A HIGH-DENSITY EVENT",
			},
		],
		toolCalls: [
			{
				id: "tool-401",
				name: "get_location",
				callType: "tool",
				stepNumber: 1,
				arguments: { msisdn: "[REDACTED_MSISDN_005]", context: null },
				response: {
					result: {
						response: {
							items: [{ valueObject: { cellSector: "STADIUM-12" } }],
						},
					},
					executionTimeSeconds: 1.51,
				},
			},
			{
				id: "tool-402",
				name: "qtm_cellsector_ref_query",
				callType: "tool",
				stepNumber: 2,
				arguments: { sector: "STADIUM-12", hours: 12 },
				response: {
					result: {
						response: {
							items: [
								{ valueObject: { congestionEvent: true, peakUsers: 1840 } },
							],
						},
					},
					executionTimeSeconds: 1.92,
				},
			},
		],
		feedback: [
			{
				source: "trace-export-ratings",
				values: {
					"The explanation and investigation areas were relevant to the issue": 1,
				},
			},
		],
		metadata: {
			sourceFormat: "trace-export",
			datasetTheme: "network-diagnostics",
		},
		traceIds: {
			traceId: "demo-trace-005",
			conversationId: "demo-cid-005",
		},
		status: "draft",
		deleted: true,
		tags: ["congestion", "event", "deleted"],
		comment:
			"Deleted sample keeps restore flows visible with real trace-like evidence.",
		datasetName: "network-diagnostics",
	},
];

export function createDemoProvider(): Provider {
	return new JsonProvider(DEMO_JSON);
}
