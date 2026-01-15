// Stats service for GET /v1/ground-truths/stats
import { client } from "../api/client";
import type { StatsPayload } from "../components/app/StatsView";

// Runtime guard to coerce unknown API responses into StatsPayload
function coerceStatsPayload(x: unknown): StatsPayload {
	const zero: StatsPayload = {
		total: { approved: 0, draft: 0, deleted: 0 },
		perSprint: [],
	};
	if (!x || typeof x !== "object") return zero;
	const obj = x as Record<string, unknown>;

	// Support both shapes:
	// 1) { total: { approved, draft, deleted }, perSprint?: [...] }
	// 2) { approved, draft, deleted } (backend current shape)
	const hasNestedTotal = obj.total && typeof obj.total === "object";
	const totalSrc = (
		hasNestedTotal ? (obj.total as Record<string, unknown>) : obj
	) as Record<string, unknown>;
	const perSprintRaw = (obj.perSprint as unknown[]) || [];

	const payload: StatsPayload = {
		total: {
			approved: Number(totalSrc.approved ?? 0) || 0,
			draft: Number(totalSrc.draft ?? 0) || 0,
			deleted: Number(totalSrc.deleted ?? 0) || 0,
		},
		perSprint: perSprintRaw
			.map((s) => {
				const r = (s as Record<string, unknown>) || {};
				return {
					sprint: String(r.sprint ?? r.name ?? ""),
					approved: Number(r.approved ?? 0) || 0,
					draft: Number(r.draft ?? 0) || 0,
					deleted: Number(r.deleted ?? 0) || 0,
				};
			})
			.filter((s) => s.sprint),
	};
	return payload;
}

export async function getGroundTruthStats(): Promise<StatsPayload> {
	const { data, error } = await client.GET("/v1/ground-truths/stats");
	if (error) throw error;
	return coerceStatsPayload(data);
}

// Mock for demo mode only
export async function mockGetGroundTruthStats(): Promise<StatsPayload> {
	await new Promise((r) => setTimeout(r, 150));
	return {
		total: { approved: 12, draft: 7, deleted: 2 },
		perSprint: [
			{ sprint: "Sprint 24.7", approved: 3, draft: 1, deleted: 0 },
			{ sprint: "Sprint 24.8", approved: 5, draft: 2, deleted: 1 },
			{ sprint: "Sprint 24.9", approved: 4, draft: 4, deleted: 1 },
		],
	};
}
