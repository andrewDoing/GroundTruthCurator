import type { GroundTruthItem } from "./groundTruth";

export interface Provider {
	id: string;
	list(): Promise<{ items: GroundTruthItem[] }>; // paging omitted for demo
	get(itemId: string): Promise<GroundTruthItem | null>;
	save(item: GroundTruthItem): Promise<GroundTruthItem>; // bumps only if content changed
	duplicate(item: GroundTruthItem): Promise<GroundTruthItem>; // create rephrase copy
	export(ids?: string[]): Promise<string>; // JSON array string
}

export class JsonProvider implements Provider {
	id = "json";
	private items: GroundTruthItem[] = [];

	constructor(initialJson: GroundTruthItem[]) {
		// Copy to avoid mutating shared constants across tests and callers
		this.items = [...initialJson];
	}

	async list() {
		return { items: this.items };
	}

	async get(itemId: string) {
		return this.items.find((i) => i.id === itemId) ?? null;
	}

	async save(item: GroundTruthItem) {
		const idx = this.items.findIndex((i) => i.id === item.id);
		if (idx >= 0) {
			const prev = this.items[idx];
			const next = {
				...prev,
				...item,
			};
			this.items[idx] = next;
			return next;
		} else {
			const next = { ...item };
			this.items.push(next);
			return next;
		}
	}

	async duplicate(item: GroundTruthItem): Promise<GroundTruthItem> {
		// Demo-only: clone and assign a temporary client-local id.
		// Persistent IDs are assigned by the backend; in API mode we use the server response.
		const uid =
			(
				globalThis as unknown as { crypto?: { randomUUID?: () => string } }
			)?.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
		const newId = `temp-${uid}`;
		const reTag = `rephrase:${item.id}`;
		const next: GroundTruthItem = {
			...item,
			id: newId,
			status: "draft",
			deleted: false,
			tags: Array.from(new Set([...(item.tags || []), reTag])),
		};
		this.items = [next, ...this.items.filter((i) => i.id !== next.id)];
		return next;
	}

	async export(ids?: string[]) {
		const list = ids?.length
			? this.items.filter((i) => ids.includes(i.id))
			: this.items;
		return JSON.stringify(list, null, 2);
	}
}
