/**
 * ToolNecessityEditor — tri-state toggle per tool name for classifying
 * tool calls as required / optional / not-needed.
 *
 * Derives the set of tool names from the union of toolCalls and
 * existing expectedTools entries. Each toggle updates the parent
 * ExpectedTools state via onUpdate.
 *
 * Phase 4 Step 4.2.
 */

import { useCallback, useMemo } from "react";
import type {
	ExpectedTools,
	ToolCallRecord,
} from "../../../models/groundTruth";
import { cn } from "../../../models/utils";

type NecessityState = "required" | "optional" | "not-needed";

type ToolRow = {
	name: string;
	state: NecessityState;
};

/** Derive the current necessity state for a tool name from expectedTools. */
function getToolState(
	name: string,
	et: ExpectedTools | undefined,
): NecessityState {
	if (et?.required?.some((t) => t.name === name)) return "required";
	if (et?.optional?.some((t) => t.name === name)) return "optional";
	if (et?.notNeeded?.some((t) => t.name === name)) return "not-needed";
	// Default: unclassified tools start as optional
	return "optional";
}

/** Build a new ExpectedTools by placing `toolName` into `targetBucket`. */
function setToolNecessity(
	toolName: string,
	target: NecessityState,
	current: ExpectedTools | undefined,
): ExpectedTools {
	const removeFrom = (arr: ExpectedTools["required"]) =>
		(arr ?? []).filter((t) => t.name !== toolName);

	const base: ExpectedTools = {
		required: removeFrom(current?.required),
		optional: removeFrom(current?.optional),
		notNeeded: removeFrom(current?.notNeeded),
	};

	const entry = { name: toolName };
	switch (target) {
		case "required":
			base.required = [...(base.required ?? []), entry];
			break;
		case "optional":
			base.optional = [...(base.optional ?? []), entry];
			break;
		case "not-needed":
			base.notNeeded = [...(base.notNeeded ?? []), entry];
			break;
	}

	return base;
}

const STATES: {
	value: NecessityState;
	label: string;
	color: string;
	activeColor: string;
}[] = [
	{
		value: "required",
		label: "Required",
		color: "text-slate-500",
		activeColor: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300",
	},
	{
		value: "optional",
		label: "Optional",
		color: "text-slate-500",
		activeColor: "bg-amber-100 text-amber-800 ring-1 ring-amber-300",
	},
	{
		value: "not-needed",
		label: "Not needed",
		color: "text-slate-500",
		activeColor: "bg-rose-100 text-rose-800 ring-1 ring-rose-300",
	},
];

export default function ToolNecessityEditor({
	toolCalls,
	expectedTools,
	onUpdate,
}: {
	toolCalls: ToolCallRecord[];
	expectedTools: ExpectedTools | undefined;
	onUpdate: (next: ExpectedTools) => void;
}) {
	// Collect all unique tool names from toolCalls + expectedTools
	const rows: ToolRow[] = useMemo(() => {
		const names = new Set<string>();
		for (const tc of toolCalls) names.add(tc.name);
		for (const t of expectedTools?.required ?? []) names.add(t.name);
		for (const t of expectedTools?.optional ?? []) names.add(t.name);
		for (const t of expectedTools?.notNeeded ?? []) names.add(t.name);
		return [...names].sort().map((name) => ({
			name,
			state: getToolState(name, expectedTools),
		}));
	}, [toolCalls, expectedTools]);

	const handleToggle = useCallback(
		(toolName: string, target: NecessityState) => {
			onUpdate(setToolNecessity(toolName, target, expectedTools));
		},
		[expectedTools, onUpdate],
	);

	if (rows.length === 0) {
		return (
			<div className="text-xs italic text-slate-400">
				No tool calls to classify.
			</div>
		);
	}

	return (
		<div className="space-y-2">
			{rows.map((row) => (
				<div
					key={row.name}
					className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
				>
					<span className="text-sm font-mono text-slate-800 flex-1 truncate">
						{row.name}
					</span>
					<div className="flex gap-1">
						{STATES.map((s) => (
							<button
								key={s.value}
								type="button"
								className={cn(
									"rounded-md px-2 py-1 text-xs font-medium transition-colors",
									row.state === s.value
										? s.activeColor
										: "bg-slate-100 hover:bg-slate-200",
									row.state !== s.value && s.color,
								)}
								onClick={() => handleToggle(row.name, s.value)}
								aria-pressed={row.state === s.value}
								aria-label={`Set ${row.name} to ${s.label}`}
							>
								{s.label}
							</button>
						))}
					</div>
				</div>
			))}
		</div>
	);
}
