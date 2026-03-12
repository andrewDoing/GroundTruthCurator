/**
 * ToolCallDetailView — expanded view of a single tool call with
 * collapsible arguments and response sections.
 *
 * Uses CodeBlockFallback from the registry for formatted rendering.
 * Phase 4 Step 4.1.
 */

import { useState } from "react";
import type { ToolCallRecord } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import CodeBlockFallback from "../../../registry/fallbacks/CodeBlockFallback";
import type { RenderContext } from "../../../registry/types";

/** Minimal viewer context for inline tool-call rendering. */
function viewerContext(itemId: string, fieldPath: string): RenderContext {
	return { itemId, fieldPath, readOnly: true };
}

export default function ToolCallDetailView({
	tc,
	index,
	itemId,
}: {
	tc: ToolCallRecord;
	index: number;
	itemId: string;
}) {
	const [argsExpanded, setArgsExpanded] = useState(false);
	const [responseExpanded, setResponseExpanded] = useState(false);

	const hasArgs = tc.arguments != null && Object.keys(tc.arguments).length > 0;
	const hasResponse = tc.response !== undefined && tc.response !== null;

	return (
		<div
			className={cn(
				"rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1",
				tc.parallelGroup && "border-l-4 border-l-violet-300",
			)}
		>
			{/* Header row */}
			<div className="flex items-start justify-between gap-2">
				<div className="flex items-center gap-2 flex-wrap">
					<span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
						{tc.callType}
					</span>
					<span className="text-sm font-mono text-slate-800">{tc.name}</span>
					{tc.stepNumber != null && (
						<span className="text-xs text-slate-500">step {tc.stepNumber}</span>
					)}
					{tc.agent && (
						<span className="text-xs text-slate-500">agent: {tc.agent}</span>
					)}
					{tc.parallelGroup && (
						<span className="rounded-full bg-violet-50 px-2 py-0.5 text-xs text-violet-600">
							∥ {tc.parallelGroup}
						</span>
					)}
				</div>
				<span className="text-xs text-slate-400 flex-none">#{index + 1}</span>
			</div>

			{/* ID */}
			{tc.id && (
				<div className="text-xs font-mono text-slate-400 truncate">
					id: {tc.id}
				</div>
			)}

			{/* Arguments (expandable) */}
			{hasArgs && (
				<div>
					<button
						type="button"
						className="mt-1 text-xs text-violet-600 hover:underline"
						onClick={() => setArgsExpanded((v) => !v)}
					>
						{argsExpanded ? "▾ Hide arguments" : "▸ Show arguments"}
					</button>
					{argsExpanded && (
						<div className="mt-1">
							<CodeBlockFallback
								data={tc.arguments}
								context={viewerContext(itemId, `toolCalls[${index}].arguments`)}
							/>
						</div>
					)}
				</div>
			)}

			{/* Response (expandable) */}
			{hasResponse && (
				<div>
					<button
						type="button"
						className="mt-1 text-xs text-violet-600 hover:underline"
						onClick={() => setResponseExpanded((v) => !v)}
					>
						{responseExpanded ? "▾ Hide response" : "▸ Show response"}
					</button>
					{responseExpanded && (
						<div className="mt-1">
							<CodeBlockFallback
								data={tc.response}
								context={viewerContext(itemId, `toolCalls[${index}].response`)}
							/>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
