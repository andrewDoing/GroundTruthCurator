import type { ApiGroundTruth, ApiHistoryEntry } from "../adapters/apiMapper";
import { groundTruthFromApi } from "../adapters/apiMapper";
import { client } from "../api/client";
import type { components, operations } from "../api/generated";
import type { GroundTruthItem } from "../models/groundTruth";
import { getApiBaseUrl, withDevUser } from "./http";
import { logEvent } from "./telemetry";

type GroundTruthItemOut = Omit<
	components["schemas"]["AgenticGroundTruthEntry-Output"],
	"history"
> & {
	tags?: string[];
	comment?: string | null;
	history?: ApiHistoryEntry[];
};

export type GroundTruthListPagination =
	components["schemas"]["PaginationMetadata"];

/**
 * Maps an API ground truth payload to a domain GroundTruthItem.
 * Delegates to the canonical groundTruthFromApi adapter to ensure
 * both the provider path and the explorer/service path produce
 * identical GroundTruthItem output for the same payload.
 */
export function mapGroundTruthFromApi(
	api: GroundTruthItemOut,
	providerId = "api",
): GroundTruthItem {
	return groundTruthFromApi(api as ApiGroundTruth, providerId);
}

interface ListAllGroundTruthsParams {
	status?: components["schemas"]["GroundTruthStatus"] | string | null;
	dataset?: string | null;
	tags?: string[];
	excludeTags?: string[];
	itemId?: string | null;
	pluginFilter?: string[];
	keyword?: string | null;
	sortBy?: string | null;
	pluginSort?: string | null;
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
	signal?: AbortSignal,
): Promise<ListAllGroundTruthsResult> {
	const query: operations["list_all_ground_truths_v1_ground_truths_get"]["parameters"]["query"] =
		{};
	if (params.status) query.status = params.status as string;
	if (params.dataset) query.dataset = params.dataset;
	if (params.tags?.length) query.tags = params.tags.join(",");
	if (params.excludeTags?.length)
		query.excludeTags = params.excludeTags.join(",");
	if (params.itemId) query.itemId = params.itemId;
	if (params.pluginFilter?.length) query.pluginFilter = params.pluginFilter;
	if (params.keyword) query.keyword = params.keyword;
	if (params.sortBy)
		query.sortBy = params.sortBy as components["schemas"]["SortField"];
	if (params.pluginSort) query.pluginSort = params.pluginSort;
	if (params.sortOrder) query.sortOrder = params.sortOrder;
	if (typeof params.page === "number") query.page = params.page;
	if (typeof params.limit === "number") query.limit = params.limit;

	const { data, error } = await client.GET("/v1/ground-truths", {
		params: {
			query: Object.keys(query).length ? query : undefined,
		},
		signal,
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
	signal?: AbortSignal,
): Promise<GroundTruthItem> {
	const { data, error } = await client.GET(
		"/v1/ground-truths/{datasetName}/{bucket}/{item_id}",
		{ params: { path: { datasetName, bucket, item_id: id } }, signal },
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
