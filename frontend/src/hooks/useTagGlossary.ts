import { useEffect, useSyncExternalStore } from "react";
import type { components } from "../api/generated";

type GlossaryResponse = components["schemas"]["GlossaryResponse"];

export interface TagGlossary {
	[tagKey: string]: string | undefined;
}

// Detect test environment
const isTestEnvironment =
	typeof process !== "undefined" && process.env.NODE_ENV === "test";

// Snapshot type for useSyncExternalStore
interface GlossarySnapshot {
	glossary: TagGlossary;
	rawGlossary: GlossaryResponse | null;
	loading: boolean;
	error: Error | null;
}

// Singleton store for tag glossary
class GlossaryStore {
	private glossary: TagGlossary = {};
	private rawGlossary: GlossaryResponse | null = null;
	private loading = false;
	private error: Error | null = null;
	private fetchPromise: Promise<void> | null = null;
	private listeners = new Set<() => void>();
	// Cached snapshot to satisfy useSyncExternalStore's referential stability requirement
	private cachedSnapshot: GlossarySnapshot;

	constructor() {
		this.cachedSnapshot = this.buildSnapshot();
	}

	private buildSnapshot(): GlossarySnapshot {
		return {
			glossary: this.glossary,
			rawGlossary: this.rawGlossary,
			loading: this.loading,
			error: this.error,
		};
	}

	subscribe = (listener: () => void) => {
		this.listeners.add(listener);
		return () => {
			this.listeners.delete(listener);
		};
	};

	getSnapshot = (): GlossarySnapshot => {
		return this.cachedSnapshot;
	};

	private notify() {
		// Update cached snapshot before notifying listeners
		this.cachedSnapshot = this.buildSnapshot();
		for (const listener of this.listeners) {
			listener();
		}
	}

	async fetch() {
		// Skip fetching in test environment
		if (isTestEnvironment) {
			this.loading = false;
			this.error = null;
			this.notify();
			return;
		}

		if (this.fetchPromise) {
			return this.fetchPromise;
		}

		this.fetchPromise = (async () => {
			try {
				this.loading = true;
				this.notify();

				const response = await fetch("/v1/tags/glossary");
				if (!response.ok) {
					throw new Error("Failed to fetch tag glossary");
				}
				const data: GlossaryResponse = await response.json();

				// Store raw glossary response
				this.rawGlossary = data;

				// Build lookup map: tag key -> description
				const glossaryMap: TagGlossary = {};
				for (const group of data.groups || []) {
					for (const tag of group.tags || []) {
						if (tag.key && tag.description) {
							glossaryMap[tag.key] = tag.description;
						}
					}
				}

				this.glossary = glossaryMap;
				this.error = null;
			} catch (err) {
				this.error = err instanceof Error ? err : new Error(String(err));
			} finally {
				this.loading = false;
				this.notify();
			}
		})();

		return this.fetchPromise;
	}

	clear() {
		this.glossary = {};
		this.rawGlossary = null;
		this.loading = false;
		this.error = null;
		this.fetchPromise = null;
		this.notify();
	}

	refresh() {
		this.fetchPromise = null;
		return this.fetch();
	}

	setGlossary(glossary: TagGlossary) {
		this.glossary = glossary;
		this.loading = false;
		this.error = null;
		this.notify();
	}
}

const glossaryStore = new GlossaryStore();

/**
 * Fetches the tag glossary from the API and transforms it into a lookup map
 * of tag key -> description.
 *
 * Uses a singleton store to prevent duplicate fetches when multiple components
 * mount simultaneously. In test environments, fetching is disabled.
 */
export function useTagGlossary() {
	const state = useSyncExternalStore(
		glossaryStore.subscribe,
		glossaryStore.getSnapshot,
	);

	useEffect(() => {
		glossaryStore.fetch();
	}, []);

	return {
		...state,
		refresh: () => glossaryStore.refresh(),
	};
}

/**
 * Returns the description for a given tag key.
 */
export function useTagDescription(tagKey: string): string | undefined {
	const { glossary } = useTagGlossary();
	return glossary[tagKey];
}

/**
 * Clear the glossary cache - useful for testing.
 */
export function clearGlossaryCache() {
	glossaryStore.clear();
}

/**
 * Set mock glossary data - useful for testing.
 */
export function setMockGlossary(glossary: TagGlossary) {
	glossaryStore.setGlossary(glossary);
}
