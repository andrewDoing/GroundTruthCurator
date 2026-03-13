import type {
	ExpectedTools,
	ToolExpectation,
} from "../../../models/groundTruth";

export type NecessityState = "required" | "optional" | "not-needed";

const EXPECTED_TOOL_BUCKETS = ["required", "optional", "notNeeded"] as const;

function findToolExpectation(
	toolName: string,
	current: ExpectedTools | undefined,
): ToolExpectation | undefined {
	for (const bucket of EXPECTED_TOOL_BUCKETS) {
		const match = current?.[bucket]?.find((tool) => tool.name === toolName);
		if (match) {
			return match;
		}
	}

	return undefined;
}

function removeFromBucket(
	entries: ToolExpectation[] | undefined,
	toolName: string,
): ToolExpectation[] {
	return (entries ?? []).filter((tool) => tool.name !== toolName);
}

export function getToolState(
	name: string,
	expectedTools: ExpectedTools | undefined,
): NecessityState {
	if (expectedTools?.required?.some((tool) => tool.name === name)) {
		return "required";
	}
	if (expectedTools?.optional?.some((tool) => tool.name === name)) {
		return "optional";
	}
	if (expectedTools?.notNeeded?.some((tool) => tool.name === name)) {
		return "not-needed";
	}

	return "optional";
}

export function setToolNecessity(
	toolName: string,
	target: NecessityState,
	current: ExpectedTools | undefined,
): ExpectedTools {
	const entry = findToolExpectation(toolName, current) ?? { name: toolName };
	const required = removeFromBucket(current?.required, toolName);
	const optional = removeFromBucket(current?.optional, toolName);
	const notNeeded = removeFromBucket(current?.notNeeded, toolName);

	switch (target) {
		case "required":
			required.push(entry);
			break;
		case "optional":
			optional.push(entry);
			break;
		case "not-needed":
			notNeeded.push(entry);
			break;
	}

	return {
		required,
		optional,
		notNeeded,
	};
}
