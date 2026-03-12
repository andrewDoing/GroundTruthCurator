/**
 * ToolCallDetailView -- compact grid-based tool call card aligned with wireframe v2.2.
 *
 * Header: 6-column CSS grid
 *   Col 1: Order badge (#1)
 *   Col 2: Function name in dark bar
 *   Col 3: Parallel group badge (if any)
 *   Col 4: Execution time
 *   Col 5: Decision badge (Required / Optional / Not needed)
 *   Col 6: Expand/collapse toggle
 *
 * Expanded:
 *   - "Was this call needed?" segmented toggle (when onUpdateExpectedTools provided)
 *   - Arguments + Result in dark code blocks
 */

import { useState } from "react";
import type {
	ExpectedTools,
	ToolCallRecord,
} from "../../../models/groundTruth";
import { getExecTime } from "../TracePanel";

// ---------------------------------------------------------------------------
// Decision segments -- mirrors wireframe DECISION_SEGMENTS
// ---------------------------------------------------------------------------

type NecessityState = "required" | "optional" | "not-needed";

const DECISION_SEGMENTS: {
	value: NecessityState;
	symbol: string;
	label: string;
	title: string;
	activeClasses: string;
	dotClasses: string;
}[] = [
	{
		value: "required",
		symbol: "\u2605",
		label: "\u2605 Required",
		title: "Needed to reach the correct answer",
		activeClasses: "bg-emerald-600 text-white shadow-sm",
		dotClasses: "bg-emerald-600 text-white",
	},
	{
		value: "optional",
		symbol: "\u25CB",
		label: "\u25CB Optional",
		title: "Fine to call but not essential",
		activeClasses: "bg-sky-600 text-white shadow-sm",
		dotClasses: "bg-sky-600 text-white",
	},
	{
		value: "not-needed",
		symbol: "\u2715",
		label: "\u2715 Not needed",
		title: "Should not have been called",
		activeClasses: "bg-rose-600 text-white shadow-sm",
		dotClasses: "bg-rose-600 text-white",
	},
];

/** Derive the current necessity state for a tool name from expectedTools. */
function getToolState(
	name: string,
	et: ExpectedTools | undefined,
): NecessityState {
	if (et?.required?.some((t) => t.name === name)) return "required";
	if (et?.optional?.some((t) => t.name === name)) return "optional";
	if (et?.notNeeded?.some((t) => t.name === name)) return "not-needed";
	return "optional";
}

/** Build a new ExpectedTools by placing toolName into targetBucket. */
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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ToolCallDetailView({
	tc,
	index,
	expectedTools,
	onUpdateExpectedTools,
}: {
	tc: ToolCallRecord;
	index: number;
	itemId: string;
	expectedTools?: ExpectedTools;
	onUpdateExpectedTools?: (tools: ExpectedTools) => void;
}) {
	const [expanded, setExpanded] = useState(false);

	const hasArgs = tc.arguments != null && Object.keys(tc.arguments).length > 0;
	const hasResponse = tc.response !== undefined && tc.response !== null;
	const execTime = getExecTime(tc.response);

	const decision = getToolState(tc.name, expectedTools);
	const seg =
		DECISION_SEGMENTS.find((s) => s.value === decision) ?? DECISION_SEGMENTS[1];

	return (
		<div className="mt-2 rounded-xl border border-slate-200 bg-white">
			{/* Header */}
			<button
				type="button"
				className="grid w-full items-center p-3 cursor-pointer hover:bg-slate-50/50 rounded-xl gap-x-2 text-left"
				style={{
					gridTemplateColumns: "2rem minmax(0,1fr) 3.5rem 4rem 1.25rem 0.75rem",
				}}
				onClick={() => setExpanded((v) => !v)}
				aria-expanded={expanded}
			>
				{/* Col 1: Order */}
				<span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-800 text-center">
					#{tc.stepNumber ?? index + 1}
				</span>

				{/* Col 2: Function name */}
				<span
					className="rounded-lg bg-slate-700 px-2 py-0.5 text-xs font-mono text-white truncate"
					title={tc.name}
				>
					{tc.name}
				</span>

				{/* Col 3: Parallel group */}
				{tc.parallelGroup ? (
					<span className="text-xs font-medium text-amber-600 text-center whitespace-nowrap">
						{"\u2016"} {tc.parallelGroup}
					</span>
				) : (
					<span />
				)}

				{/* Col 4: Execution time */}
				<span className="text-xs text-slate-400 text-right whitespace-nowrap tabular-nums">
					{execTime !== null ? `${execTime.toFixed(2)}s` : "\u2014"}
				</span>

				{/* Col 5: Decision badge */}
				<span
					className={`inline-flex items-center justify-center rounded-full w-5 h-5 text-xs font-bold ${seg.dotClasses}`}
					title={seg.title}
				>
					{seg.symbol}
				</span>

				{/* Col 6: Expand/collapse */}
				<span className="text-xs text-slate-400 text-center">
					{expanded ? "\u25BE" : "\u25B8"}
				</span>
			</button>

			{/* Expanded detail */}
			{expanded && (
				<>
					{/* Decision toggle */}
					{onUpdateExpectedTools && (
						<div className="border-t border-slate-100 px-3 py-3 text-xs text-slate-700">
							<div className="mb-2 font-semibold uppercase tracking-wide text-slate-500">
								Was this call needed for the correct answer?
							</div>
							<div
								className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5"
								role="radiogroup"
								aria-label="Tool call relevance"
							>
								{DECISION_SEGMENTS.map((s) => (
									<button
										key={s.value}
										type="button"
										className={`relative select-none rounded-md px-3 py-1.5 text-xs font-semibold transition-all duration-150 ${
											decision === s.value
												? s.activeClasses
												: "text-slate-500 hover:text-slate-700"
										}`}
										aria-pressed={decision === s.value}
										title={s.title}
										onClick={() =>
											onUpdateExpectedTools(
												setToolNecessity(tc.name, s.value, expectedTools),
											)
										}
									>
										{s.label}
									</button>
								))}
							</div>
						</div>
					)}

					{/* Arguments + Result */}
					<div className="border-t p-3 space-y-2">
						{hasArgs && (
							<>
								<div className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
									Arguments
								</div>
								<pre className="rounded-lg bg-slate-800 p-3 text-xs text-green-400 overflow-x-auto whitespace-pre-wrap">
									{JSON.stringify(tc.arguments, null, 2)}
								</pre>
							</>
						)}

						{hasResponse && (
							<>
								<div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mt-2">
									Result
								</div>
								<pre className="rounded-lg bg-slate-800 p-3 text-xs text-green-400 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">
									{typeof tc.response === "object"
										? JSON.stringify(tc.response, null, 2)
										: String(tc.response)}
								</pre>
							</>
						)}
					</div>
				</>
			)}
		</div>
	);
}
