import { client } from "../api/client";
import type { components } from "../api/generated";

type DatasetCurationInstructions =
	components["schemas"]["DatasetCurationInstructions"];

// Cache for available datasets (5 minute TTL)
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
let datasetsCache: { data: string[] | null; timestamp: number } = {
	data: null,
	timestamp: 0,
};

/**
 * Fetch dataset-level curation instructions markdown for a dataset.
 * Returns the server object; caller can read `instructions`.
 */
export async function getDatasetCurationInstructions(
	datasetName: string,
): Promise<DatasetCurationInstructions | undefined> {
	if (!datasetName) return undefined;
	const { data, error } = await client.GET(
		"/v1/datasets/{datasetName}/curation-instructions",
		{ params: { path: { datasetName } } },
	);
	if (error) throw error;
	return data as unknown as DatasetCurationInstructions;
}

/**
 * Return a sorted list of dataset names from the dedicated datasets endpoint.
 * Results are cached for 5 minutes to reduce API calls.
 */
export async function fetchAvailableDatasets(
	forceRefresh = false,
): Promise<string[]> {
	const now = Date.now();

	// Return cached data if available and not expired
	if (
		!forceRefresh &&
		datasetsCache.data !== null &&
		now - datasetsCache.timestamp < CACHE_TTL_MS
	) {
		return datasetsCache.data;
	}

	try {
		const { data, error } = await client.GET("/v1/datasets", {});
		if (error) throw error;
		const raw = Array.isArray(data) ? data : [];
		const names = new Set<string>();
		for (const value of raw) {
			if (typeof value !== "string") continue;
			const trimmed = value.trim();
			if (trimmed) names.add(trimmed);
		}
		const datasets = Array.from(names).sort((a, b) => a.localeCompare(b));

		// Update cache
		datasetsCache = {
			data: datasets,
			timestamp: now,
		};

		return datasets;
	} catch {
		// On error, return cached data if available, otherwise empty array
		return datasetsCache.data ?? [];
	}
}
