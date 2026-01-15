import type { GroundTruthItem } from "../models/groundTruth";
import type { Provider } from "../models/provider";
import {
	duplicateItem as apiDuplicateItem,
	getMyAssignments,
	updateAssignedGroundTruth,
} from "../services/assignments";
import { deleteGroundTruth, getGroundTruthRaw } from "../services/groundTruths";
import { groundTruthFromApi, groundTruthToPatch, type ApiGroundTruth } from "./apiMapper";

export class ApiProvider implements Provider {
	id = "api";

	private cache: Record<
		string,
		{
			api: ApiGroundTruth;
			meta: { dataset: string; bucket: string; etag?: string | null };
		}
	> = {};
	private orderedIds: string[] = [];

	async list(): Promise<{ items: GroundTruthItem[] }> {
		const apiItems = await getMyAssignments();

		const nextCache: typeof this.cache = {};
		const nextOrderedIds: string[] = [];

		for (const a of apiItems) {
			nextCache[a.id] = {
				api: a,
				meta: {
					dataset: a.datasetName,
					bucket: (a.bucket as string) || "0",
					etag: a._etag || undefined,
				},
			};
			nextOrderedIds.push(a.id);
		}

		// Preserve locally-created/known items (e.g., after duplicate()) that may not
		// show up in the next list() call immediately due to eventual consistency.
		for (const id of this.orderedIds) {
			if (id in nextCache) continue;
			const existing = this.cache[id];
			if (!existing) continue;
			nextCache[id] = existing;
			nextOrderedIds.push(id);
		}

		this.cache = nextCache;
		this.orderedIds = nextOrderedIds;

		return {
			items: this.orderedIds
				.map((id) => this.cache[id]?.api)
				.filter(Boolean)
				.map((api) => groundTruthFromApi(api)),
		};
	}

	async get(itemId: string): Promise<GroundTruthItem | null> {
		const entry = this.cache[itemId];
		if (!entry) return null;
		return groundTruthFromApi(entry.api);
	}

	async save(item: GroundTruthItem): Promise<GroundTruthItem> {
		const entry = this.cache[item.id];
		if (!entry) {
			await this.list();
		}
		const e = this.cache[item.id];
		if (!e) throw new Error("Item metadata not found");

		const { dataset, bucket, etag } = e.meta;
		let updatedApi: ApiGroundTruth | null = null;

		if (item.deleted) {
			await deleteGroundTruth(dataset, bucket, item.id);
			const fresh = await getGroundTruthRaw(dataset, bucket, item.id);
			updatedApi = fresh;
		} else {
			const patch = groundTruthToPatch({ item, originalApi: e.api });
			const doUpdate = async (nextEtag?: string | null) =>
				updateAssignedGroundTruth(
					dataset,
					bucket,
					item.id,
					patch as Partial<ApiGroundTruth>,
					nextEtag || undefined,
				);

			try {
				updatedApi = await doUpdate(etag);
			} catch (err: unknown) {
				const maybeResp = err as {
					status?: number;
					response?: { status?: number };
				};
				const status = maybeResp.status ?? maybeResp.response?.status;
				if (status === 412) {
					const fresh = await getGroundTruthRaw(dataset, bucket, item.id);
					this.cache[item.id] = {
						api: fresh,
						meta: { dataset, bucket, etag: fresh?._etag || undefined },
					};
					updatedApi = await doUpdate(fresh?._etag || undefined);
				} else {
					throw err;
				}
			}
		}

		if (!updatedApi) {
			throw new Error("Failed to get updated API response");
		}

		this.cache[item.id] = {
			api: updatedApi,
			meta: {
				dataset,
				bucket,
				etag: updatedApi._etag || undefined,
			},
		};

		return groundTruthFromApi(updatedApi);
	}

	async duplicate(item: GroundTruthItem): Promise<GroundTruthItem> {
		const entry = this.cache[item.id];
		if (!entry) throw new Error("Item metadata not found");
		const { dataset, bucket } = entry.meta;
		const created = await apiDuplicateItem(dataset, bucket, item.id);

		this.cache[created.id] = {
			api: created,
			meta: {
				dataset: created.datasetName,
				bucket: (created.bucket as string) || "0",
				etag: created._etag || undefined,
			},
		};
		this.orderedIds = [
			created.id,
			...this.orderedIds.filter((id) => id !== created.id),
		];

		return groundTruthFromApi(created);
	}

	async export(ids?: string[]): Promise<string> {
		if (!this.orderedIds.length) await this.list();
		const chosen = (ids?.length ? ids : this.orderedIds)
			.map((id) => this.cache[id]?.api)
			.filter(Boolean) as ApiGroundTruth[];
		return JSON.stringify(chosen, null, 2);
	}
}
