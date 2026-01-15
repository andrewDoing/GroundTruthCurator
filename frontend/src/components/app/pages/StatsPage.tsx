import { useEffect, useState } from "react";
import type { GroundTruthItem } from "../../../models/groundTruth";
import {
	getGroundTruthStats,
	mockGetGroundTruthStats,
} from "../../../services/stats";
import StatsView, { type StatsPayload } from "../StatsView";

export default function StatsPage({
	demoMode,
	items,
	onBack,
}: {
	demoMode: boolean;
	items: GroundTruthItem[];
	onBack: () => void;
}) {
	const [stats, setStats] = useState<StatsPayload | null>(null);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			if (demoMode) {
				const data = await mockGetGroundTruthStats();
				if (!cancelled) setStats(data);
			} else {
				try {
					const data = await getGroundTruthStats();
					if (!cancelled) setStats(data);
				} catch {
					const zero: StatsPayload = {
						total: { approved: 0, draft: 0, deleted: 0 },
						perSprint: [],
					};
					if (!cancelled) setStats(zero);
				}
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [demoMode]);

	return (
		<section className="rounded-2xl border bg-white p-4 shadow-sm">
			<div className="mb-3 flex items-center justify-between">
				<div className="text-sm font-medium">Stats</div>
				<button
					type="button"
					onClick={onBack}
					className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
				>
					Back
				</button>
			</div>
			{stats ? (
				<StatsView items={items} data={stats} />
			) : (
				<div className="text-sm text-slate-600">Loading stats…</div>
			)}
		</section>
	);
}
