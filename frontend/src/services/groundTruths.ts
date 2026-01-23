import { client } from "../api/client";
import type { components, operations } from "../api/generated";
import type { GroundTruthItem } from "../models/groundTruth";
import { urlToTitle } from "../models/utils";
import { getApiBaseUrl, withDevUser } from "./http";
import { logEvent } from "./telemetry";

type GroundTruthItemOut = components["schemas"]["GroundTruthItem-Output"];

export type GroundTruthListPagination =
	components["schemas"]["PaginationMetadata"];

export function mapGroundTruthFromApi(
	api: GroundTruthItemOut,
	providerId = "api",
): GroundTruthItem {
	// Map history if present
	let history: GroundTruthItem["history"];
	if (api.history && api.history.length > 0) {
		// History exists - use it as-is (don't overwrite with synthQuestion)
		history = api.history.map((h) => ({
			role: h.role === "assistant" ? "agent" : "user",
			content: h.msg,
			expectedBehavior:
				h.expectedBehavior && h.expectedBehavior.length > 0
					? h.expectedBehavior
					: undefined,
		}));
	} else {
		// ALWAYS convert single-turn items to multi-turn format
		// Legacy single-turn item: create initial history from synthQuestion/editedQuestion
		const initialQuestion = api.editedQuestion || api.synthQuestion || "";
		if (initialQuestion) {
			history = [
				{
					role: "user" as const,
					content: initialQuestion,
				},
				{
					role: "agent" as const,
					content: api.answer || "", // Empty string if no answer
				},
			];
		}
	}

	// For multi-turn items, use first user turn content; for single-turn items, use editedQuestion or synthQuestion
	const question =
		history && history.length > 0 && history[0].role === "user"
			? history[0].content
			: api.editedQuestion || api.synthQuestion || "";

	// Map references from both top-level refs (single-turn) and history refs (multi-turn)
	const refs: GroundTruthItem["references"] = [];

	// Pre-calculate total reference count for better array allocation
	const topLevelRefCount = api.refs?.length || 0;
	const historyRefCount =
		api.history?.reduce((sum, turn) => sum + (turn.refs?.length || 0), 0) || 0;
	const totalRefCount = topLevelRefCount + historyRefCount;

	// Pre-allocate array for better memory performance
	if (totalRefCount > 0) {
		refs.length = totalRefCount;
		let refIndex = 0;

		// Process top-level refs
		if (api.refs?.length) {
			for (let i = 0; i < api.refs.length; i++) {
				const r = api.refs[i];
				refs[refIndex] = {
					id: `ref_${refIndex}`,
					title: r.title || (r.url ? urlToTitle(r.url) : undefined),
					url: r.url,
					snippet: r.content ?? undefined,
					keyParagraph: r.keyExcerpt ?? undefined,
					visitedAt: null,
					bonus: r.bonus === true,
					messageIndex:
						!api.history || api.history.length === 0 ? 1 : undefined,
				};
				refIndex++;
			}
		}

		// Process history refs in single pass
		if (api.history?.length) {
			for (let turnIndex = 0; turnIndex < api.history.length; turnIndex++) {
				const turn = api.history[turnIndex];
				if (turn.refs?.length) {
					for (let i = 0; i < turn.refs.length; i++) {
						const r = turn.refs[i];
						refs[refIndex] = {
							id: `ref_${refIndex}`,
							title: r.title || (r.url ? urlToTitle(r.url) : undefined),
							url: r.url,
							snippet: r.content ?? undefined,
							keyParagraph: r.keyExcerpt ?? undefined,
							visitedAt: null,
							bonus: r.bonus === true,
							messageIndex: turnIndex,
						};
						refIndex++;
					}
				}
			}
		}
	}

	const deleted = api.status === "deleted";
	return {
		id: api.id,
		providerId,
		question,
		answer: api.answer ?? "",
		history,
		comment: api.comment ?? undefined,
		references: refs,
		status:
			(deleted ? "draft" : (api.status as GroundTruthItem["status"])) ||
			"draft",
		deleted,
		tags: api.tags || [],
		manualTags: api.manualTags || [],
		computedTags: api.computedTags || [],
		datasetName: api.datasetName,
		bucket: (api.bucket as string) || "0",
		reviewedAt: api.reviewedAt ?? null,
		totalReferences: api.totalReferences,
		...({
			_etag: api._etag,
		} as Record<string, unknown>),
	};
}

interface ListAllGroundTruthsParams {
	status?: components["schemas"]["GroundTruthStatus"] | string | null;
	dataset?: string | null;
	tags?: string[];
	itemId?: string | null;
	refUrl?: string | null;
	keyword?: string | null;
	sortBy?: string | null;
	sortOrder?: "asc" | "desc" | null;
	page?: number;
	limit?: number;
}

interface ListAllGroundTruthsResult {
	items: GroundTruthItem[];
	pagination?: GroundTruthListPagination;
}

export async function listAllGroundTruths(
	params: ListAllGroundTruthsParams = {},
): Promise<ListAllGroundTruthsResult> {
	const query: operations["list_all_ground_truths_v1_ground_truths_get"]["parameters"]["query"] =
		{};
	if (params.status) query.status = params.status as string;
	if (params.dataset) query.dataset = params.dataset;
	if (params.tags?.length) query.tags = params.tags.join(",");
	if (params.itemId) query.itemId = params.itemId;
	if (params.refUrl) query.refUrl = params.refUrl;
	if (params.keyword) query.keyword = params.keyword;
	if (params.sortBy)
		query.sortBy = params.sortBy as components["schemas"]["SortField"];
	if (params.sortOrder) query.sortOrder = params.sortOrder;
	if (typeof params.page === "number") query.page = params.page;
	if (typeof params.limit === "number") query.limit = params.limit;

	const { data, error } = await client.GET("/v1/ground-truths", {
		params: {
			query: Object.keys(query).length ? query : undefined,
		},
	});
	if (error) throw error;
	const payload = (data as unknown as
		| components["schemas"]["GroundTruthListResponse"]
		| undefined) ?? { items: [], pagination: undefined };
	return {
		items: (payload.items || []).map((item) => {
			return mapGroundTruthFromApi(item);
		}),
		pagination: payload.pagination,
	};
}

export async function getGroundTruth(
	datasetName: string,
	bucket: string,
	id: string,
): Promise<GroundTruthItem> {
	const { data, error } = await client.GET(
		"/v1/ground-truths/{datasetName}/{bucket}/{item_id}",
		{ params: { path: { datasetName, bucket, item_id: id } } },
	);

	if (error) {
		throw error;
	}

	const rawItem = data as unknown as GroundTruthItemOut;
	return mapGroundTruthFromApi(rawItem);
}

export async function getGroundTruthRaw(
	datasetName: string,
	bucket: string,
	id: string,
): Promise<GroundTruthItemOut> {
	const { data, error } = await client.GET(
		"/v1/ground-truths/{datasetName}/{bucket}/{item_id}",
		{ params: { path: { datasetName, bucket, item_id: id } } },
	);

	if (error) {
		throw error;
	}

	return data as unknown as GroundTruthItemOut;
}

export async function deleteGroundTruth(
	datasetName: string,
	bucket: string,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE(
		"/v1/ground-truths/{datasetName}/{bucket}/{item_id}",
		{ params: { path: { datasetName, bucket, item_id: id } } },
	);
	if (error) throw error;
}

export async function restoreGroundTruth(
	datasetName: string,
	bucket: string,
	id: string,
	etag?: string,
): Promise<GroundTruthItemOut> {
	const { data, error } = await client.PUT(
		"/v1/ground-truths/{datasetName}/{bucket}/{item_id}",
		{
			params: { path: { datasetName, bucket, item_id: id } },
			headers: etag ? { "If-Match": etag } : undefined,
			body: { status: "draft" } as Record<string, unknown>,
		},
	);
	if (error) throw error;
	return data as unknown as GroundTruthItemOut;
}

// export async function getStats(): Promise<Stats> {
// 	return fetchJson<Stats>(`/ground-truths/stats`);
// }

/**
 * Fetches the new snapshot JSON payload (approved items) from the backend and returns the Blob and filename.
 * Backend is expected to set Content-Disposition: attachment; filename="ground-truth-snapshot-<ts>.json".
 */
async function fetchSnapshotBlob(): Promise<{
	blob: Blob;
	filename: string;
}> {
	const url = `${getApiBaseUrl()}/ground-truths/snapshot`;
	const res = await fetch(
		url,
		withDevUser({ headers: { Accept: "application/json" } }),
	);
	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(
			`Failed to fetch snapshot: ${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`,
		);
	}
	// Derive filename from Content-Disposition; fall back to a sensible default
	const cd =
		res.headers.get("Content-Disposition") ||
		res.headers.get("content-disposition") ||
		"";
	let filename = "ground-truth-snapshot.json";
	const match = cd.match(/filename\*?=(?:UTF-8''|")?([^";]+)"?/i);
	if (match?.[1]) {
		try {
			filename = decodeURIComponent(match[1]);
		} catch {
			filename = match[1];
		}
	}
	const blob = await res.blob();
	return { blob, filename };
}

/**
 * Triggers a browser download of the current snapshot JSON. Returns the filename used.
 */
export async function downloadSnapshot(): Promise<string> {
	try {
		logEvent("gtc.export_snapshot_start");
	} catch {}
	const { blob, filename } = await fetchSnapshotBlob();
	const href = URL.createObjectURL(blob);
	try {
		const a = document.createElement("a");
		a.href = href;
		a.download = filename;
		a.style.display = "none";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
	} finally {
		// Revoke after a tick to allow navigation to occur
		setTimeout(() => URL.revokeObjectURL(href), 1000);
	}
	try {
		logEvent("gtc.export_snapshot_complete", { filename });
	} catch {}
	return filename;
}
