import { useState } from "react";
import type {
	ContextEntry,
	ExpectedTools,
	FeedbackEntry,
	GroundTruthItem,
	PluginPayload,
	Reference,
	ToolCallRecord,
	ToolExpectation,
} from "../../models/groundTruth";
import { getItemReferences, hasEvidenceData } from "../../models/groundTruth";
import { cn } from "../../models/utils";
import { fieldComponentRegistry } from "../../registry/FieldComponentRegistry";
import { RegistryRenderer } from "../../registry/RegistryRenderer";
import type { EditorProps, ViewerProps } from "../../registry/types";
import ContextEntryEditor from "./editors/ContextEntryEditor";
import ToolCallDetailView from "./editors/ToolCallDetailView";

/** Extract executionTimeSeconds from a tool call's response (unknown type). */
function getExecTime(response: unknown): number | null {
	if (response && typeof response === "object") {
		const r = response as Record<string, unknown>;
		if (typeof r.executionTimeSeconds === "number") {
			return r.executionTimeSeconds;
		}
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
				className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left hover:bg-slate-50 select-none"
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

function TraceInfoSection({ item }: { item: GroundTruthItem }) {
	const traceIds = item.traceIds ?? {};
	const contextEntries = item.contextEntries ?? [];
	const tracePayload = item.tracePayload ?? {};

	const entries: [string, string][] = [];
	for (const [k, v] of Object.entries(traceIds)) {
		const display =
			typeof v === "string" && v.length > 20
				? `${v.substring(0, 18)}…`
				: String(v);
		entries.push([k, display]);
	}

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

	const sentiment = deriveSentiment(item.feedback ?? []);
	if (sentiment) {
		entries.push(["feedback", sentiment === "positive" ? "like" : "dislike"]);
	}

	const resolution =
		tracePayload.resolution ?? contextMap.get("resolution")?.value;
	if (resolution) {
		entries.push(["resolution", String(resolution)]);
	}

	if (entries.length === 0) return null;

	const wideKeys = new Set(["resolution"]);
	const normalEntries = entries.filter(([k]) => !wideKeys.has(k));
	const wideEntries = entries.filter(([k]) => wideKeys.has(k));

	return (
		<div className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3">
			<div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
				Trace Info
			</div>
			<div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
				{normalEntries.map(([k, v]) => (
					<div key={k}>
						<span className="font-mono text-slate-500">{k}: </span>
						<span className="font-mono text-slate-700">{v}</span>
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

type ToolCallRenderData = {
	toolCall: ToolCallRecord;
	index: number;
	item: GroundTruthItem;
	expectedTools?: ExpectedTools;
	references: Reference[];
	onAddReferences?: (refs: Reference[]) => void;
	onOpenReference?: (ref: Reference) => void;
	onUpdateReference?: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference?: (refId: string) => void;
};

type PluginRenderData = {
	slot: string;
	payload: PluginPayload;
};

function ToolCallViewer({ data }: ViewerProps) {
	const value = data as ToolCallRenderData;
	return (
		<ToolCallDetailView
			tc={value.toolCall}
			index={value.index}
			item={value.item}
			expectedTools={value.expectedTools}
			references={value.references}
			onAddReferences={value.onAddReferences}
			onOpenReference={value.onOpenReference}
			onUpdateReference={value.onUpdateReference}
			onRemoveReference={value.onRemoveReference}
		/>
	);
}

function ToolCallEditor({ data, onChange }: EditorProps) {
	const value = data as ToolCallRenderData;
	return (
		<ToolCallDetailView
			tc={value.toolCall}
			index={value.index}
			item={value.item}
			expectedTools={value.expectedTools}
			references={value.references}
			onAddReferences={value.onAddReferences}
			onOpenReference={value.onOpenReference}
			onUpdateReference={value.onUpdateReference}
			onRemoveReference={value.onRemoveReference}
			onUpdateExpectedTools={(expectedTools) =>
				onChange({ ...value, expectedTools })
			}
		/>
	);
}

function ContextEntriesViewer({ data }: ViewerProps) {
	const entries = (data as ContextEntry[]) ?? [];
	if (!entries.length) {
		return (
			<div className="text-xs italic text-slate-400">
				No context entries provided.
			</div>
		);
	}
	return (
		<div className="space-y-2">
			{entries.map((entry) => (
				<div
					key={`${entry.key}-${JSON.stringify(entry.value)}`}
					className="rounded-lg border border-slate-200 bg-slate-50 p-3"
				>
					<div className="flex items-start gap-2 text-xs">
						<span className="shrink-0 font-mono text-slate-500">
							{entry.key}:
						</span>
						<span className="break-all text-slate-700">
							{typeof entry.value === "object"
								? JSON.stringify(entry.value)
								: String(entry.value)}
						</span>
					</div>
				</div>
			))}
		</div>
	);
}

function ContextEntriesEditor({ data, onChange }: EditorProps) {
	return (
		<ContextEntryEditor
			entries={(data as ContextEntry[]) ?? []}
			onUpdate={(entries) => onChange(entries)}
		/>
	);
}

function FeedbackViewer({ data }: ViewerProps) {
	const feedback = (data as FeedbackEntry[]) ?? [];
	const allValues: [string, number][] = [];
	for (const entry of feedback) {
		for (const [k, v] of Object.entries(entry.values ?? {})) {
			if (typeof v === "number") allValues.push([k, v]);
		}
	}
	if (!allValues.length) return null;
	return (
		<div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
			<div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
				Feedback Scores
			</div>
			{allValues.map(([question, score]) => (
				<div
					key={question}
					className="flex items-center justify-between py-0.5 text-xs"
				>
					<span className="mr-2 text-slate-600">{question}</span>
					<span className={cn("font-medium", scoreColor(score))}>{score}</span>
				</div>
			))}
			<p className="mt-1 text-xs italic text-slate-400">
				Scale: 1 = Strongly Agree, 5 = Strongly Disagree
			</p>
		</div>
	);
}

const EXPECTED_TOOL_GROUPS = [
	{ key: "required", label: "Required" },
	{ key: "optional", label: "Optional" },
	{ key: "notNeeded", label: "Not Needed" },
] as const;

function formatToolExpectationArguments(
	argumentsValue: ToolExpectation["arguments"],
): string | null {
	if (argumentsValue == null) return null;
	if (typeof argumentsValue === "string") return argumentsValue;
	return JSON.stringify(argumentsValue, null, 2);
}

function ExpectedToolsSection({
	expectedTools,
}: {
	expectedTools: ExpectedTools;
}) {
	const groups = EXPECTED_TOOL_GROUPS.map(({ key, label }) => ({
		key,
		label,
		tools: expectedTools[key] ?? [],
	})).filter((group) => group.tools.length > 0);

	if (!groups.length) return null;

	return (
		<div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
			<div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
				Expected Tools
			</div>
			<div className="space-y-3">
				{groups.map((group) => (
					<div key={group.key}>
						<div className="mb-2 text-xs font-medium text-slate-600">
							{group.label}
						</div>
						<div className="space-y-2">
							{group.tools.map((tool) => {
								const formattedArguments = formatToolExpectationArguments(
									tool.arguments,
								);
								return (
									<div
										key={`${group.key}-${tool.name}-${JSON.stringify(tool.arguments ?? null)}`}
										className="rounded-lg border border-slate-200 bg-white p-3"
									>
										<div className="text-sm font-medium text-slate-800">
											{tool.name}
										</div>
										{formattedArguments && (
											<pre className="mt-2 overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 whitespace-pre-wrap break-all">
												{formattedArguments}
											</pre>
										)}
									</div>
								);
							})}
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

function PluginPayloadViewer({ data }: ViewerProps) {
	const { slot, payload } = data as PluginRenderData;
	const hasData = Object.keys(payload.data ?? {}).length > 0;
	return (
		<div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
			<div className="flex flex-wrap items-center gap-2">
				<span className="text-sm font-medium text-slate-800">{slot}</span>
				<span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800">
					{payload.kind}
				</span>
				<span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">
					v{payload.version}
				</span>
			</div>
			{hasData ? (
				<pre className="overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700">
					{JSON.stringify(payload.data, null, 2)}
				</pre>
			) : (
				<div className="text-xs italic text-slate-400">
					No plugin-owned fields provided.
				</div>
			)}
		</div>
	);
}

function JsonBlockViewer({ data }: ViewerProps) {
	return (
		<pre className="max-h-64 overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700">
			{JSON.stringify(data, null, 2)}
		</pre>
	);
}

fieldComponentRegistry.registerIfAbsent({
	discriminator: "toolCall",
	viewer: ToolCallViewer,
	editor: ToolCallEditor,
	displayName: "Tool Call",
});
fieldComponentRegistry.registerIfAbsent({
	discriminator: "contextEntries",
	viewer: ContextEntriesViewer,
	editor: ContextEntriesEditor,
	displayName: "Context Entries",
});
fieldComponentRegistry.registerIfAbsent({
	discriminator: "feedback",
	viewer: FeedbackViewer,
	displayName: "Feedback Scores",
});
fieldComponentRegistry.registerIfAbsent({
	discriminator: "pluginPayload",
	viewer: PluginPayloadViewer,
	displayName: "Plugin Payload",
});
fieldComponentRegistry.registerIfAbsent({
	discriminator: "tracePayload",
	viewer: JsonBlockViewer,
	displayName: "Trace Payload",
});
fieldComponentRegistry.registerIfAbsent({
	discriminator: "metadata",
	viewer: JsonBlockViewer,
	displayName: "Metadata",
});

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
	item?: GroundTruthItem | null;
	className?: string;
	onUpdateContextEntries?: (entries: ContextEntry[]) => void;
	onUpdateExpectedTools?: (tools: ExpectedTools) => void;
	onAddReferences?: (refs: Reference[]) => void;
	onOpenReference?: (ref: Reference) => void;
	onUpdateReference?: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference?: (refId: string) => void;
}) {
	const [expanded, setExpanded] = useState(true);
	const hasEvidence = !!item && hasEvidenceData(item);
	const toolCalls = item?.toolCalls ?? [];
	const references = item ? getItemReferences(item) : [];
	const contextEntries = item?.contextEntries ?? [];
	const metadata = item?.metadata ?? {};
	const plugins = item?.plugins ?? {};
	const feedback = item?.feedback ?? [];
	const tracePayload = item?.tracePayload ?? {};
	const sentiment = deriveSentiment(feedback);
	const hasMoreDetails =
		contextEntries.length > 0 ||
		!!onUpdateContextEntries ||
		Object.keys(metadata).length > 0 ||
		Object.entries(plugins).length > 0 ||
		Object.keys(tracePayload).length > 0;

	return (
		<div className={cn("rounded-2xl border bg-white shadow-sm", className)}>
			<button
				type="button"
				className="flex w-full items-center justify-between rounded-2xl p-4 cursor-pointer hover:bg-slate-50 select-none"
				onClick={() => setExpanded((v) => !v)}
				aria-expanded={expanded}
			>
				<div className="flex flex-wrap items-center gap-2">
					<span className="text-sm font-medium text-slate-700">
						Evidence & Review ({toolCalls.length} tool call
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

			{expanded && (
				<div className="space-y-3 border-t px-4 pb-4">
					{hasEvidence && item ? (
						<>
							<div className="mt-3">
								<TraceInfoSection item={item} />
							</div>

							<RegistryRenderer
								discriminator="feedback:scores"
								data={feedback}
								context={{
									itemId: item.id,
									fieldPath: "feedback",
									readOnly: true,
								}}
								mode="viewer"
							/>

							{item.expectedTools && (
								<ExpectedToolsSection expectedTools={item.expectedTools} />
							)}

							{toolCalls.length > 0 && (
								<>
									<div className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
										Tool Calls ({toolCalls.length})
									</div>
									{toolCalls.map((tc, i) => (
										<RegistryRenderer
											key={tc.id || String(i)}
											discriminator={`toolCall:${tc.name}`}
											data={{
												toolCall: tc,
												index: i,
												item,
												expectedTools: item.expectedTools,
												references,
												onAddReferences,
												onOpenReference,
												onUpdateReference,
												onRemoveReference,
											}}
											context={{
												itemId: item.id,
												fieldPath: `toolCalls.${i}`,
												readOnly: !onUpdateExpectedTools,
											}}
											mode={onUpdateExpectedTools ? "editor" : "viewer"}
											onChange={(next) => {
												if (!onUpdateExpectedTools) return;
												onUpdateExpectedTools(
													(next as ToolCallRenderData).expectedTools ?? {
														required: [],
													},
												);
											}}
										/>
									))}
								</>
							)}

							{hasMoreDetails && (
								<CollapsibleSection title="More Details">
									<div className="space-y-3">
										{(contextEntries.length > 0 || onUpdateContextEntries) && (
											<CollapsibleSection
												title="Context Entries"
												badge={contextEntries.length}
												defaultOpen
											>
												<RegistryRenderer
													discriminator="contextEntries:batch"
													data={contextEntries}
													context={{
														itemId: item.id,
														fieldPath: "contextEntries",
														readOnly: !onUpdateContextEntries,
													}}
													mode={onUpdateContextEntries ? "editor" : "viewer"}
													onChange={(next) =>
														onUpdateContextEntries?.(next as ContextEntry[])
													}
												/>
											</CollapsibleSection>
										)}

										{Object.keys(metadata).length > 0 && (
											<CollapsibleSection title="Metadata">
												<RegistryRenderer
													discriminator="metadata"
													data={metadata}
													context={{
														itemId: item.id,
														fieldPath: "metadata",
														readOnly: true,
													}}
													mode="viewer"
												/>
											</CollapsibleSection>
										)}

										{Object.entries(plugins).length > 0 && (
											<CollapsibleSection
												title="Plugin Details"
												badge={Object.keys(plugins).length}
											>
												<div className="space-y-2">
													{Object.entries(plugins).map(([slot, payload]) => (
														<RegistryRenderer
															key={slot}
															discriminator={`pluginPayload:${payload.kind}`}
															data={{ slot, payload }}
															context={{
																itemId: item.id,
																fieldPath: `plugins.${slot}`,
																pluginKind: payload.kind,
																readOnly: true,
															}}
															mode="viewer"
														/>
													))}
												</div>
											</CollapsibleSection>
										)}

										{Object.keys(tracePayload).length > 0 && (
											<CollapsibleSection title="Trace Payload">
												<RegistryRenderer
													discriminator="tracePayload"
													data={tracePayload}
													context={{
														itemId: item.id,
														fieldPath: "tracePayload",
														readOnly: true,
													}}
													mode="viewer"
												/>
											</CollapsibleSection>
										)}
									</div>
								</CollapsibleSection>
							)}
						</>
					) : (
						<div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
							No trace or evidence data available yet.
						</div>
					)}
				</div>
			)}
		</div>
	);
}
