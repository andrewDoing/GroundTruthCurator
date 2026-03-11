/**
 * TracePanel — read-only right-pane evidence panel.
 *
 * Displays generic agentic-schema data attached to a GroundTruthItem:
 *   - Tool calls (toolCalls)
 *   - Trace IDs (traceIds)
 *   - Metadata dictionary (metadata)
 *   - Feedback entries (feedback)
 *   - Raw trace payload (tracePayload)
 *
 * Aligned with the evidence/trace panel in wireframes/agent-curation-wireframe-v2.2.html.
 * Each section is collapsible and renders nothing when empty.
 */

import { useState } from "react";
import type {
	FeedbackEntry,
	GroundTruthItem,
	ToolCallRecord,
} from "../../models/groundTruth";
import { hasEvidenceData } from "../../models/groundTruth";
import { cn } from "../../models/utils";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CollapsibleSection({
	title,
	badge,
	defaultOpen = false,
	children,
}: {
	title: string;
	badge?: string | number;
	defaultOpen?: boolean;
	children: React.ReactNode;
}) {
	const [open, setOpen] = useState(defaultOpen);
	return (
		<div className="rounded-xl border border-slate-200 bg-white shadow-sm">
			<button
				type="button"
				className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50 rounded-xl select-none"
				onClick={() => setOpen((v) => !v)}
				aria-expanded={open}
			>
				<span className="flex items-center gap-2 text-sm font-medium text-slate-700">
					{title}
					{badge !== undefined && (
						<span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
							{badge}
						</span>
					)}
				</span>
				<span className="text-xs text-slate-400">{open ? "▾" : "▸"}</span>
			</button>
			{open && <div className="border-t px-4 pb-4 pt-3">{children}</div>}
		</div>
	);
}

// ── Tool Calls ──────────────────────────────────────────────────────────────

function ToolCallEntry({ tc, index }: { tc: ToolCallRecord; index: number }) {
	const [expanded, setExpanded] = useState(false);
	const hasResponse = tc.response !== undefined && tc.response !== null;
	return (
		<div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
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
				</div>
				<span className="text-xs text-slate-400 flex-none">#{index + 1}</span>
			</div>
			{tc.id && (
				<div className="text-xs font-mono text-slate-400 truncate">
					id: {tc.id}
				</div>
			)}
			{hasResponse && (
				<button
					type="button"
					className="mt-1 text-xs text-violet-600 hover:underline"
					onClick={() => setExpanded((v) => !v)}
				>
					{expanded ? "▾ Hide response" : "▸ Show response"}
				</button>
			)}
			{expanded && hasResponse && (
				<pre className="mt-1 overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-48">
					{typeof tc.response === "string"
						? tc.response
						: JSON.stringify(tc.response, null, 2)}
				</pre>
			)}
		</div>
	);
}

// ── Feedback ───────────────────────────────────────────────────────────────

function FeedbackEntryRow({ entry }: { entry: FeedbackEntry }) {
	const hasValues = entry.values && Object.keys(entry.values).length > 0;
	return (
		<div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
			{entry.source && (
				<div className="text-xs font-semibold text-slate-600">
					{entry.source}
				</div>
			)}
			{hasValues && (
				<div className="space-y-0.5">
					{Object.entries(entry.values ?? {}).map(([k, v]) => (
						<div key={k} className="flex items-start gap-2 text-xs">
							<span className="font-mono text-slate-500 shrink-0">{k}:</span>
							<span className="text-slate-700">
								{typeof v === "object" ? JSON.stringify(v) : String(v)}
							</span>
						</div>
					))}
				</div>
			)}
			{!entry.source && !hasValues && (
				<span className="text-xs text-slate-400 italic">(empty entry)</span>
			)}
		</div>
	);
}

// ── Metadata / KV dict ─────────────────────────────────────────────────────

function KVDict({ data }: { data: Record<string, unknown> }) {
	return (
		<div className="space-y-0.5">
			{Object.entries(data).map(([k, v]) => (
				<div key={k} className="flex items-start gap-2 text-xs">
					<span className="font-mono text-slate-500 shrink-0">{k}:</span>
					<span className="text-slate-700 break-all">
						{typeof v === "object" ? JSON.stringify(v) : String(v)}
					</span>
				</div>
			))}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Main TracePanel
// ---------------------------------------------------------------------------

export default function TracePanel({
	item,
	className,
}: {
	item: GroundTruthItem;
	className?: string;
}) {
	if (!hasEvidenceData(item)) {
		return (
			<div
				className={cn(
					"rounded-2xl border border-slate-200 bg-slate-50 p-4 text-center text-sm text-slate-400",
					className,
				)}
			>
				No trace or evidence data available for this item.
			</div>
		);
	}

	const toolCalls = item.toolCalls ?? [];
	const traceIds = item.traceIds ?? {};
	const metadata = item.metadata ?? {};
	const feedback = item.feedback ?? [];
	const tracePayload = item.tracePayload ?? {};

	return (
		<div className={cn("space-y-3", className)}>
			<div className="text-sm font-semibold text-slate-700 px-1">
				Evidence &amp; Trace
			</div>

			{/* Trace IDs */}
			{Object.keys(traceIds).length > 0 && (
				<CollapsibleSection title="Trace IDs" defaultOpen>
					<KVDict data={traceIds as Record<string, unknown>} />
				</CollapsibleSection>
			)}

			{/* Tool Calls */}
			{toolCalls.length > 0 && (
				<CollapsibleSection
					title="Tool Calls"
					badge={toolCalls.length}
					defaultOpen
				>
					<div className="space-y-2">
						{toolCalls.map((tc, i) => (
							<ToolCallEntry key={tc.id || String(i)} tc={tc} index={i} />
						))}
					</div>
				</CollapsibleSection>
			)}

			{/* Feedback */}
			{feedback.length > 0 && (
				<CollapsibleSection
					title="Feedback"
					badge={feedback.length}
					defaultOpen
				>
					<div className="space-y-2">
						{feedback.map((f, i) => (
							// biome-ignore lint/suspicious/noArrayIndexKey: feedback entries have no stable id
							<FeedbackEntryRow key={i} entry={f} />
						))}
					</div>
				</CollapsibleSection>
			)}

			{/* Metadata */}
			{Object.keys(metadata).length > 0 && (
				<CollapsibleSection title="Metadata">
					<KVDict data={metadata} />
				</CollapsibleSection>
			)}

			{/* Trace Payload (raw) */}
			{Object.keys(tracePayload).length > 0 && (
				<CollapsibleSection title="Trace Payload">
					<pre className="overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-64">
						{JSON.stringify(tracePayload, null, 2)}
					</pre>
				</CollapsibleSection>
			)}
		</div>
	);
}
