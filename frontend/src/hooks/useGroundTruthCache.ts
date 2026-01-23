import type { GroundTruthItem } from "../models/groundTruth";

type CacheKey = string; // Format: `${dataset}/${bucket}/${itemId}`

interface CacheEntry {
	item: GroundTruthItem;
	timestamp: number;
}

/**
 * In-memory session cache for ground truth items (FR-001).
 * Reduces redundant network requests when inspecting the same item multiple times.
 * Cache is per browser session and shared across all components.
 *
 * This is a module-level singleton to enable cache invalidation (FR-002)
 * from anywhere in the app (e.g., after save operations).
 */
class GroundTruthCache {
	private cache = new Map<CacheKey, CacheEntry>();

	private getCacheKey(
		dataset: string,
		bucket: string,
		itemId: string,
	): CacheKey {
		return `${dataset}/${bucket}/${itemId}`;
	}

	get(dataset: string, bucket: string, itemId: string): GroundTruthItem | null {
		const key = this.getCacheKey(dataset, bucket, itemId);
		const entry = this.cache.get(key);
		return entry?.item ?? null;
	}

	set(
		dataset: string,
		bucket: string,
		itemId: string,
		item: GroundTruthItem,
	): void {
		const key = this.getCacheKey(dataset, bucket, itemId);
		this.cache.set(key, {
			item,
			timestamp: Date.now(),
		});
	}

	invalidate(dataset: string, bucket: string, itemId: string): void {
		const key = this.getCacheKey(dataset, bucket, itemId);
		this.cache.delete(key);
	}

	clear(): void {
		this.cache.clear();
	}
}

// Singleton instance
const groundTruthCache = new GroundTruthCache();

/**
 * Hook to access the ground truth cache.
 * Returns the singleton cache instance.
 */
export function useGroundTruthCache() {
	return groundTruthCache;
}

/**
 * Invalidate a ground truth item in the cache (FR-002).
 * Call this after saving/updating an item to ensure the next inspection shows fresh data.
 */
export function invalidateGroundTruthCache(
	dataset: string,
	bucket: string,
	itemId: string,
): void {
	groundTruthCache.invalidate(dataset, bucket, itemId);
}
