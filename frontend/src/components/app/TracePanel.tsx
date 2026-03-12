/**
 * TracePanel — evidence panel aligned with wireframe v2.2.
 *
 * Layout (top to bottom):
 *   1. Header — "📋 Trace Data (N tool calls)" + sentiment badge + collapse toggle
 *   2. Trace Info — flat 2-column grid of key identifiers
 *   3. Feedback Scores — justified rows with color-coded numeric scores
 *   4. Tool Calls — compact grid-based cards with expand/collapse
 *   5. More Details — collapsible section for remaining data
 */

import { useState } from "react";
import type {
	ContextEntry,
	ExpectedTools,
	FeedbackEntry,
	GroundTruthItem,
	PluginPayload,
	Reference,
} from "../../models/groundTruth";
import { getItemReferences, hasEvidenceData } from "../../models/groundTruth";
import { cn } from "../../models/utils";
import ContextEntryEditor from "./editors/ContextEntryEditor";
import ToolCallDetailView from "./editors/ToolCallDetailView";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract executionTimeSeconds from a tool call's response (unknown type). */
function getExecTime(response: unknown): number | null {
	if (response && typeof response === "object") {
		const r = response as Record<string, unknown>;
		if (typeof r.executionTimeSeconds === "number")
			return r.executionTimeSeconds;
	}
	return null;
}

/** Derive overall sentiment from feedback values (lower = more positive). */
function deriveSentiment(
	feedback: FeedbackEntry[],
): "positive" | "negative" | null {
	const numericValues: number[] = [];
	for (const f of feedback) {
		for (const v of Object.values(f.values ?? {})) {
			if (typeof v === "number") numericValues.push(v);
		}
	}
	if (numericValues.length === 0) return null;
	const avg = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
	return avg <= 2.5 ? "positive" : "negative";
}

/** Score color: 1=green, 2=amber, 3+=red. */
function scoreColor(score: number): string {
	if (score <= 1) return "text-emerald-700";
	if (score <= 2) return "text-amber-700";
	return "text-rose-700";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Collapsible section used for "More Details" and individual sub-areas. */
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

// ── Trace Info ──────────────────────────────────────────────────────────────

function TraceInfoSection({ item }: { item: GroundTruthItem }) {
	const traceIds = item.traceIds ?? {};
	const contextEntries = item.contextEntries ?? [];
	const tracePayload = item.tracePayload ?? {};

	const entries: [string, string][] = [];

	// Trace IDs
	for (const [k, v] of Object.entries(traceIds)) {
		const display =
			typeof v === "string" && v.length > 20
				? `${v.substring(0, 18)}…`
				: String(v);
		entries.push([k, display]);
	}

	// Key context entries
	const contextMap = new Map(contextEntries.map((e) => [e.key, e]));
	if (contextMap.has("impacted_device_type")) {
		const deviceType = String(
			contextMap.get("impacted_device_type")?.value ?? "",
		);
		const device = contextMap.has("impacted_device")
			? String(contextMap.get("impacted_device")?.value ?? "")
			: "";
		entries.push(["device", `${deviceType} ${device}`.trim()]);
	}

	// Feedback type from metadata or derive from feedback
	const sentiment = deriveSentiment(item.feedback ?? []);
	if (sentiment) {
		entries.push(["feedback", sentiment === "positive" ? "like" : "dislike"]);
	}

	// Resolution from tracePayload or contextEntries
	const resolution =
		tracePayload.resolution ?? contextMap.get("resolution")?.value;
	if (resolution) {
		entries.push(["resolution", String(resolution)]);
	}

	if (entries.length === 0) return null;

	// Separate normal entries from wide ones (resolution spans full width)
	const wideKeys = new Set(["resolution"]);
	const normalEntries = entries.filter(([k]) => !wideKeys.has(k));
	const wideEntries = entries.filter(([k]) => wideKeys.has(k));

	return (
		<div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-1">
			<div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
				Trace Info
			</div>
			<div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
				{normalEntries.map(([k, v]) => (
					<div key={k}>
						<span className="font-mono text-slate-500">{k}: </span>
						<span className="text-slate-700 font-mono">{v}</span>
					</div>
				))}
				{wideEntries.map(([k, v]) => (
					<div key={k} className="col-span-2">
						<span className="font-mono text-slate-500">{k}: </span>
						<span className="text-slate-700">{v}</span>
					</div>
				))}
			</div>
		</div>
	);
}

// ── Feedback Scores ─────────────────────────────────────────────────────────

function FeedbackScoresSection({ feedback }: { feedback: FeedbackEntry[] }) {
	const allValues: [string, number][] = [];
	for (const f of feedback) {
		for (const [k, v] of Object.entries(f.values ?? {})) {
			if (typeof v === "number") allValues.push([k, v]);
		}
	}
	if (allValues.length === 0) return null;

	return (
		<div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
			<div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
				Feedback Scores
			</div>
			{allValues.map(([question, score]) => (
				<div
					key={question}
					className="flex items-center justify-between text-xs py-0.5"
				>
					<span className="text-slate-600 mr-2">{question}</span>
					<span className={cn("font-medium", scoreColor(score))}>{score}</span>
				</div>
			))}
			<p className="mt-1 text-xs text-slate-400 italic">
				Scale: 1 = Strongly Agree, 5 = Strongly Disagree
			</p>
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

// ── Plugin Details ────────────────────────────────────────────────────────────

function PluginPayloadCard({
	slot,
	payload,
}: {
	slot: string;
	payload: PluginPayload;
}) {
	const hasData = Object.keys(payload.data ?? {}).length > 0;
	return (
		<div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
			<div className="flex items-center gap-2 flex-wrap">
				<span className="text-sm font-medium text-slate-800">{slot}</span>
				<span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800">
					{payload.kind}
				</span>
				<span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">
					v{payload.version}
				</span>
			</div>
			{hasData ? (
				<KVDict data={payload.data ?? {}} />
			) : (
				<div className="text-xs italic text-slate-400">
					No plugin-owned fields provided.
				</div>
			)}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Main TracePanel
// ---------------------------------------------------------------------------

export { getExecTime };

export default function TracePanel({
	item,
	className,
	onUpdateContextEntries,
	onUpdateExpectedTools,
	onAddReferences,
	onOpenReference,
	onUpdateReference,
	onRemoveReference,
}: {
	item: GroundTruthItem;
	className?: string;
	onUpdateContextEntries?: (entries: ContextEntry[]) => void;
	onUpdateExpectedTools?: (tools: ExpectedTools) => void;
	onAddReferences?: (refs: Reference[]) => void;
	onOpenReference?: (ref: Reference) => void;
	onUpdateReference?: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference?: (refId: string) => void;
}) {
	const [expanded, setExpanded] = useState(true);

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
	const references = getItemReferences(item);
	const contextEntries = item.contextEntries ?? [];
	const metadata = item.metadata ?? {};
	const plugins = item.plugins ?? {};
	const feedback = item.feedback ?? [];
	const tracePayload = item.tracePayload ?? {};
	const sentiment = deriveSentiment(feedback);

	// Determine if "More Details" has content (expected tools are now inline)
	const hasMoreDetails =
		contextEntries.length > 0 ||
		onUpdateContextEntries ||
		Object.keys(metadata).length > 0 ||
		Object.entries(plugins).length > 0 ||
		Object.keys(tracePayload).length > 0;

	return (
		<div className={cn("rounded-2xl border bg-white shadow-sm", className)}>
			{/* ── Header ── */}
			<button
				type="button"
				className="flex w-full items-center justify-between p-4 cursor-pointer hover:bg-slate-50 rounded-2xl select-none"
				onClick={() => setExpanded((v) => !v)}
				aria-expanded={expanded}
			>
				<div className="flex items-center gap-2 flex-wrap">
					<span className="text-sm font-medium text-slate-700">
						📋 Trace Data ({toolCalls.length} tool call
						{toolCalls.length !== 1 ? "s" : ""})
					</span>
					{sentiment && (
						<span
							className={cn(
								"rounded-full px-2 py-0.5 text-xs font-medium",
								sentiment === "positive"
									? "bg-emerald-100 text-emerald-800"
									: "bg-rose-100 text-rose-800",
							)}
						>
							{sentiment === "positive" ? "👍 Positive" : "👎 Negative"}
						</span>
					)}
				</div>
				<span className="text-xs text-slate-500">
					{expanded ? "▾ Collapse" : "▸ Expand"}
				</span>
			</button>

			{/* ── Expanded content ── */}
			{expanded && (
				<div className="border-t px-4 pb-4 space-y-3">
					{/* Trace Info */}
					<div className="mt-3">
						<TraceInfoSection item={item} />
					</div>

					{/* Feedback Scores */}
					<FeedbackScoresSection feedback={feedback} />

					{/* Tool Calls */}
					{toolCalls.length > 0 && (
						<>
							<div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mt-2">
								Tool Calls ({toolCalls.length})
							</div>
							{toolCalls.map((tc, i) => (
								<ToolCallDetailView
									key={tc.id || String(i)}
									tc={tc}
									index={i}
									item={item}
									expectedTools={item.expectedTools}
									onUpdateExpectedTools={onUpdateExpectedTools}
									references={references}
									onAddReferences={onAddReferences}
									onOpenReference={onOpenReference}
									onUpdateReference={onUpdateReference}
									onRemoveReference={onRemoveReference}
								/>
							))}
						</>
					)}

					{/* More Details — collapsible for remaining data */}
					{hasMoreDetails && (
						<CollapsibleSection title="More Details">
							<div className="space-y-3">
								{(contextEntries.length > 0 || onUpdateContextEntries) && (
									<CollapsibleSection
										title="Context Entries"
										badge={contextEntries.length}
										defaultOpen
									>
										{onUpdateContextEntries ? (
											<ContextEntryEditor
												entries={contextEntries}
												onUpdate={onUpdateContextEntries}
											/>
										) : (
											<div className="space-y-2">
												{contextEntries.map((entry) => (
													<div
														key={`${entry.key}-${JSON.stringify(entry.value)}`}
														className="rounded-lg border border-slate-200 bg-slate-50 p-3"
													>
														<div className="flex items-start gap-2 text-xs">
															<span className="font-mono text-slate-500 shrink-0">
																{entry.key}:
															</span>
															<span className="text-slate-700 break-all">
																{typeof entry.value === "object"
																	? JSON.stringify(entry.value)
																	: String(entry.value)}
															</span>
														</div>
													</div>
												))}
											</div>
										)}
									</CollapsibleSection>
								)}

								{Object.keys(metadata).length > 0 && (
									<CollapsibleSection title="Metadata">
										<KVDict data={metadata} />
									</CollapsibleSection>
								)}

								{Object.entries(plugins).length > 0 && (
									<CollapsibleSection
										title="Plugin Details"
										badge={Object.keys(plugins).length}
									>
										<div className="space-y-2">
											{Object.entries(plugins).map(([slot, payload]) => (
												<PluginPayloadCard
													key={slot}
													slot={slot}
													payload={payload}
												/>
											))}
										</div>
									</CollapsibleSection>
								)}

								{Object.keys(tracePayload).length > 0 && (
									<CollapsibleSection title="Trace Payload">
										<pre className="overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-64">
											{JSON.stringify(tracePayload, null, 2)}
										</pre>
									</CollapsibleSection>
								)}
							</div>
						</CollapsibleSection>
					)}
				</div>
			)}
		</div>
	);
}
