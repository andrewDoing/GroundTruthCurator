/// <reference types="node" />

import type { IntegrationState, SeededItem } from "./integration-helpers";
import { apiDelete, apiGet, apiPost } from "./integration-helpers";
import {
	createQuestionsExplorerTestData,
	extractPayloads,
	type QuestionsExplorerBlueprint,
} from "./test-data";

interface ImportBulkResponse {
	imported: number;
	errors: string[];
	uuids: string[];
}

interface GroundTruthListResponse {
	items: Array<{
		id: string;
		datasetName: string;
		bucket?: string;
		status: string;
		tags?: string[];
		reviewedAt?: string | null;
		references?: unknown[];
	}>;
	pagination?: {
		total: number;
	};
}

export interface SeedResult {
	blueprint: QuestionsExplorerBlueprint;
	seeded: SeededItem[];
}

export async function seedQuestionsExplorerData(
	backendUrl: string,
	devUserId: string,
	runId: string,
): Promise<SeedResult> {
	const apiBase = `${backendUrl}/v1`;
	const blueprint = createQuestionsExplorerTestData(runId);
	const payloads = extractPayloads(blueprint);

	if (blueprint.tags.length) {
		await apiPost(apiBase, "/tags", { tags: blueprint.tags }, devUserId).catch(
			() => {},
		);
	}

	const importRes = (await apiPost<ImportBulkResponse>(
		apiBase,
		"/ground-truths",
		payloads,
		devUserId,
	)) as ImportBulkResponse;
	if (importRes.errors?.length) {
		throw new Error(
			`Failed to import ${importRes.errors.length} item(s): ${importRes.errors.join(", ")}`,
		);
	}

	const seeded: SeededItem[] = [];
	for (const datasetName of blueprint.datasets) {
		const search = new URLSearchParams({
			dataset: datasetName,
			limit: String(Math.min(blueprint.items.length, 100)),
		});
		const res = (await apiGet<GroundTruthListResponse>(
			apiBase,
			`/ground-truths?${search.toString()}`,
			devUserId,
		)) as GroundTruthListResponse;
		for (const item of res.items ?? []) {
			seeded.push({
				id: item.id,
				datasetName,
				bucket: String(item.bucket ?? ""),
				status: item.status,
				tags: [...(item.tags ?? [])],
				references: Array.isArray(item.references) ? item.references.length : 0,
				reviewedAt: item.reviewedAt ?? null,
			});
		}
	}

	return { blueprint, seeded };
}

export async function cleanupSeededData(
	state: IntegrationState,
	backendUrl: string,
	devUserId: string,
): Promise<void> {
	const apiBase = `${backendUrl}/v1`;
	const datasets = new Map<string, SeededItem[]>();
	for (const item of state.seeded) {
		if (!item.bucket) continue;
		datasets.set(item.datasetName, [
			...(datasets.get(item.datasetName) ?? []),
			item,
		]);
	}
	for (const [dataset, items] of datasets.entries()) {
		for (const item of items) {
			try {
				await apiDelete(
					apiBase,
					`/ground-truths/${encodeURIComponent(dataset)}/${encodeURIComponent(item.bucket)}/${encodeURIComponent(item.id)}`,
					devUserId,
				);
			} catch (err) {
				console.warn(
					`Failed to delete ${dataset}/${item.bucket}/${item.id}: ${String(err)}`,
				);
			}
		}
	}
}
