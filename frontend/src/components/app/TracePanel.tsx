/**
 * TracePanel — evidence panel with editable context entries.
 *
 * Displays generic agentic-schema data attached to a GroundTruthItem:
 *   - Expected tools review (expectedTools vs toolCalls)
 *   - Tool calls (toolCalls)
 *   - Context entries (contextEntries) — editable when onUpdateContextEntries is provided
 *   - Trace IDs (traceIds)
 *   - Metadata dictionary (metadata)
 *   - Plugin-owned details (plugins)
 *   - Feedback entries (feedback)
 *   - Raw trace payload (tracePayload)
 *
 * Aligned with the evidence/trace panel in wireframes/agent-curation-wireframe-v2.2.html.
 * Each section is collapsible and renders nothing when empty.
 */

import { useState } from "react";
import type {
	ContextEntry,
	FeedbackEntry,
	GroundTruthItem,
	PluginPayload,
	ToolCallRecord,
	ToolExpectation,
} from "../../models/groundTruth";
import { hasEvidenceData } from "../../models/groundTruth";
import { cn } from "../../models/utils";
import ContextEntryEditor from "./editors/ContextEntryEditor";

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

// ── Expected Tools Review ───────────────────────────────────────────────────

type ToolExpectationStatus = {
	expectation: ToolExpectation;
	called: boolean;
};

function ExpectedToolsSection({ item }: { item: GroundTruthItem }) {
	const expected = item.expectedTools;
	if (
		!expected ||
		(!expected.required?.length &&
			!expected.optional?.length &&
			!expected.notNeeded?.length)
	) {
		return null;
	}

	const calledNames = new Set((item.toolCalls ?? []).map((tc) => tc.name));

	const requiredStatus: ToolExpectationStatus[] = (expected.required ?? []).map(
		(te) => ({ expectation: te, called: calledNames.has(te.name) }),
	);
	const optionalStatus: ToolExpectationStatus[] = (expected.optional ?? []).map(
		(te) => ({ expectation: te, called: calledNames.has(te.name) }),
	);
	const notNeededStatus: ToolExpectationStatus[] = (
		expected.notNeeded ?? []
	).map((te) => ({ expectation: te, called: calledNames.has(te.name) }));

	const allRequiredMet = requiredStatus.every((s) => s.called);

	return (
		<CollapsibleSection
			title="Expected Tools"
			badge={
				allRequiredMet
					? "✓"
					: `${requiredStatus.filter((s) => !s.called).length} missing`
			}
			defaultOpen={!allRequiredMet}
		>
			<div className="space-y-2">
				{requiredStatus.length > 0 && (
					<div>
						<div className="mb-1 text-xs font-semibold text-slate-500 uppercase tracking-wide">
							Required
						</div>
						{requiredStatus.map(({ expectation, called }) => (
							<div
								key={expectation.name}
								className={cn(
									"flex items-center gap-2 rounded-md px-2 py-1 text-xs",
									called
										? "bg-emerald-50 text-emerald-800"
										: "bg-rose-50 text-rose-800",
								)}
							>
								<span>{called ? "✓" : "✗"}</span>
								<span className="font-mono">{expectation.name}</span>
							</div>
						))}
					</div>
				)}
				{optionalStatus.length > 0 && (
					<div>
						<div className="mb-1 text-xs font-semibold text-slate-500 uppercase tracking-wide">
							Optional
						</div>
						{optionalStatus.map(({ expectation, called }) => (
							<div
								key={expectation.name}
								className={cn(
									"flex items-center gap-2 rounded-md px-2 py-1 text-xs",
									called
										? "bg-violet-50 text-violet-800"
										: "bg-slate-50 text-slate-600",
								)}
							>
								<span>{called ? "✓" : "–"}</span>
								<span className="font-mono">{expectation.name}</span>
							</div>
						))}
					</div>
				)}
				{notNeededStatus.length > 0 && (
					<div>
						<div className="mb-1 text-xs font-semibold text-slate-500 uppercase tracking-wide">
							Not Needed
						</div>
						{notNeededStatus.map(({ expectation, called }) => (
							<div
								key={expectation.name}
								className={cn(
									"flex items-center gap-2 rounded-md px-2 py-1 text-xs",
									called
										? "bg-amber-50 text-amber-800"
										: "bg-slate-50 text-slate-500",
								)}
							>
								<span>{called ? "⚠" : "–"}</span>
								<span className="font-mono">{expectation.name}</span>
								{called && (
									<span className="text-amber-700 italic">
										(called but not expected)
									</span>
								)}
							</div>
						))}
					</div>
				)}
			</div>
		</CollapsibleSection>
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

// ── Context Entries ───────────────────────────────────────────────────────────

function ContextEntryRow({ entry }: { entry: ContextEntry }) {
	return (
		<div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
			<div className="flex items-start gap-2 text-xs">
				<span className="font-mono text-slate-500 shrink-0">{entry.key}:</span>
				<span className="text-slate-700 break-all">
					{typeof entry.value === "object"
						? JSON.stringify(entry.value)
						: String(entry.value)}
				</span>
			</div>
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

export default function TracePanel({
	item,
	className,
	onUpdateContextEntries,
}: {
	item: GroundTruthItem;
	className?: string;
	onUpdateContextEntries?: (entries: ContextEntry[]) => void;
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
	const contextEntries = item.contextEntries ?? [];
	const traceIds = item.traceIds ?? {};
	const metadata = item.metadata ?? {};
	const plugins = item.plugins ?? {};
	const feedback = item.feedback ?? [];
	const tracePayload = item.tracePayload ?? {};

	return (
		<div className={cn("space-y-3", className)}>
			<div className="text-sm font-semibold text-slate-700 px-1">
				Evidence &amp; Trace
			</div>

			{/* Expected Tools review – always show when present */}
			<ExpectedToolsSection item={item} />

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

			{/* Context Entries — editable when handler is provided */}
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
								<ContextEntryRow
									key={`${entry.key}-${JSON.stringify(entry.value)}`}
									entry={entry}
								/>
							))}
						</div>
					)}
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

			{/* Plugin-owned Details */}
			{Object.entries(plugins).length > 0 && (
				<CollapsibleSection
					title="Plugin Details"
					badge={Object.keys(plugins).length}
					defaultOpen
				>
					<div className="space-y-2">
						{Object.entries(plugins).map(([slot, payload]) => (
							<PluginPayloadCard key={slot} slot={slot} payload={payload} />
						))}
					</div>
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
