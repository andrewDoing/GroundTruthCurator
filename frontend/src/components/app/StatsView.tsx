import type { GroundTruthItem } from "../../models/groundTruth";
import { hasEvidenceData } from "../../models/groundTruth";

type SprintStats = {
	sprint: string;
	approved: number;
	draft: number;
	deleted: number;
};

/**
 * Generic plugin-contributed metrics that can be extended by plugin packs.
 * Each key is a metric name and each value is a displayable number.
 */
export type PluginMetrics = Record<string, number>;

export type StatsPayload = {
	total: { approved: number; draft: number; deleted: number };
	perSprint: SprintStats[];
	/** Optional plugin-contributed metrics to display alongside core stats. */
	pluginMetrics?: PluginMetrics;
};

export default function StatsView({
	items,
	data,
}: {
	items: GroundTruthItem[];
	data: StatsPayload;
}) {
	// Compute live totals from current items as a sanity check alongside provided data
	const live = items.reduce(
		(acc, it) => {
			if (it.status === "approved") acc.approved++;
			if (it.status === "draft") acc.draft++;
			if (it.deleted) acc.deleted++;
			return acc;
		},
		{ approved: 0, draft: 0, deleted: 0 },
	);

	// Compute generic agentic metrics from current items
	const agenticMetrics = items.reduce(
		(acc, it) => {
			if (it.toolCalls && it.toolCalls.length > 0) {
				acc.itemsWithToolCalls++;
				acc.totalToolCalls += it.toolCalls.length;
			}
			if (it.contextEntries && it.contextEntries.length > 0) {
				acc.itemsWithContext++;
			}
			if (hasEvidenceData(it)) {
				acc.itemsWithEvidence++;
			}
			if (it.expectedTools) {
				acc.itemsWithExpectedTools++;
			}
			return acc;
		},
		{
			itemsWithToolCalls: 0,
			totalToolCalls: 0,
			itemsWithContext: 0,
			itemsWithEvidence: 0,
			itemsWithExpectedTools: 0,
		},
	);

	return (
		<section className="rounded-2xl border bg-white p-4 shadow-sm">
			<div className="mb-4">
				<h2 className="text-lg font-semibold">Ground Truth – Stats</h2>
				<p className="text-sm text-slate-600">
					Dummy data for API GET /v1/ground-truths/stats. Totals below are
					computed live from the current demo items for convenience.
				</p>
			</div>

			<div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
				<div className="rounded-xl border bg-violet-50 p-4">
					<div className="text-xs uppercase tracking-wide text-slate-600">
						Approved
					</div>
					<div className="mt-1 text-2xl font-bold text-violet-800">
						{data.total.approved}
					</div>
					<div className="mt-1 text-xs text-slate-500">
						Live: {live.approved}
					</div>
				</div>
				<div className="rounded-xl border bg-amber-50 p-4">
					<div className="text-xs uppercase tracking-wide text-slate-600">
						Draft
					</div>
					<div className="mt-1 text-2xl font-bold text-amber-800">
						{data.total.draft}
					</div>
					<div className="mt-1 text-xs text-slate-500">Live: {live.draft}</div>
				</div>
				<div className="rounded-xl border bg-rose-50 p-4">
					<div className="text-xs uppercase tracking-wide text-slate-600">
						Deleted
					</div>
					<div className="mt-1 text-2xl font-bold text-rose-800">
						{data.total.deleted}
					</div>
					<div className="mt-1 text-xs text-slate-500">
						Live: {live.deleted}
					</div>
				</div>
			</div>

			<div className="mt-6">
				<div className="mb-2 text-sm font-medium">Per sprint</div>
				<div className="divide-y rounded-xl border">
					{data.perSprint.map((s) => (
						<div
							key={s.sprint}
							className="grid grid-cols-4 items-center gap-2 p-3 text-sm"
						>
							<div className="font-medium">{s.sprint}</div>
							<div className="text-violet-800">Approved: {s.approved}</div>
							<div className="text-amber-800">Draft: {s.draft}</div>
							<div className="text-rose-800">Deleted: {s.deleted}</div>
						</div>
					))}
				</div>
			</div>

			{/* Generic agentic evidence metrics – derived from current items */}
			{items.length > 0 && (
				<div className="mt-6">
					<div className="mb-2 text-sm font-medium">
						Generic Evidence Metrics
					</div>
					<p className="mb-3 text-xs text-slate-500">
						Computed from {items.length} loaded item
						{items.length !== 1 ? "s" : ""}.
					</p>
					<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
						<div className="rounded-xl border bg-slate-50 p-3">
							<div className="text-xs text-slate-500">Items w/ Trace</div>
							<div className="mt-1 text-xl font-bold text-slate-800">
								{agenticMetrics.itemsWithEvidence}
							</div>
						</div>
						<div className="rounded-xl border bg-violet-50 p-3">
							<div className="text-xs text-slate-500">Total Tool Calls</div>
							<div className="mt-1 text-xl font-bold text-violet-800">
								{agenticMetrics.totalToolCalls}
							</div>
							<div className="mt-0.5 text-xs text-slate-400">
								{agenticMetrics.itemsWithToolCalls} items
							</div>
						</div>
						<div className="rounded-xl border bg-blue-50 p-3">
							<div className="text-xs text-slate-500">Items w/ Context</div>
							<div className="mt-1 text-xl font-bold text-blue-800">
								{agenticMetrics.itemsWithContext}
							</div>
						</div>
						<div className="rounded-xl border bg-amber-50 p-3">
							<div className="text-xs text-slate-500">
								Items w/ Expected Tools
							</div>
							<div className="mt-1 text-xl font-bold text-amber-800">
								{agenticMetrics.itemsWithExpectedTools}
							</div>
						</div>
					</div>
				</div>
			)}

			{/* Plugin-contributed metrics (extensible per plugin pack) */}
			{data.pluginMetrics && Object.keys(data.pluginMetrics).length > 0 && (
				<div className="mt-6">
					<div className="mb-2 text-sm font-medium">Plugin Metrics</div>
					<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
						{Object.entries(data.pluginMetrics).map(([key, value]) => (
							<div key={key} className="rounded-xl border bg-slate-50 p-3">
								<div className="text-xs text-slate-500">{key}</div>
								<div className="mt-1 text-xl font-bold text-slate-800">
									{value}
								</div>
							</div>
						))}
					</div>
				</div>
			)}
		</section>
	);
}
