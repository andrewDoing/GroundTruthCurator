import { beforeEach, describe, expect, it } from "vitest";
import {
	invalidateGroundTruthCache,
	useGroundTruthCache,
} from "../../../src/hooks/useGroundTruthCache";
import type { GroundTruthItem } from "../../../src/models/groundTruth";

describe("useGroundTruthCache", () => {
	const mockItem: GroundTruthItem = {
		id: "test-123",
		datasetName: "test-dataset",
		bucket: "bucket-uuid",
		status: "draft",
		question: "Test question?",
		answer: "Test answer",
		references: [],
		manualTags: [],
		computedTags: [],
		providerId: "api",
	};

	beforeEach(() => {
		// Clear cache before each test
		const cache = useGroundTruthCache();
		cache.clear();
	});

	it("should return null for non-existent item", () => {
		const cache = useGroundTruthCache();
		const result = cache.get("test-dataset", "bucket-uuid", "test-123");
		expect(result).toBeNull();
	});

	it("should cache and retrieve item", () => {
		const cache = useGroundTruthCache();
		cache.set("test-dataset", "bucket-uuid", "test-123", mockItem);
		const result = cache.get("test-dataset", "bucket-uuid", "test-123");
		expect(result).toEqual(mockItem);
	});

	it("should invalidate cached item", () => {
		const cache = useGroundTruthCache();
		cache.set("test-dataset", "bucket-uuid", "test-123", mockItem);
		cache.invalidate("test-dataset", "bucket-uuid", "test-123");
		const result = cache.get("test-dataset", "bucket-uuid", "test-123");
		expect(result).toBeNull();
	});

	it("should clear all cached items", () => {
		const cache = useGroundTruthCache();
		cache.set("test-dataset", "bucket-1", "item-1", mockItem);
		cache.set("test-dataset", "bucket-2", "item-2", mockItem);
		cache.clear();
		expect(cache.get("test-dataset", "bucket-1", "item-1")).toBeNull();
		expect(cache.get("test-dataset", "bucket-2", "item-2")).toBeNull();
	});

	it("should use module-level singleton", () => {
		const cache1 = useGroundTruthCache();
		const cache2 = useGroundTruthCache();
		cache1.set("test-dataset", "bucket-uuid", "test-123", mockItem);
		const result = cache2.get("test-dataset", "bucket-uuid", "test-123");
		expect(result).toEqual(mockItem);
	});

	it("should invalidate via global function", () => {
		const cache = useGroundTruthCache();
		cache.set("test-dataset", "bucket-uuid", "test-123", mockItem);
		invalidateGroundTruthCache("test-dataset", "bucket-uuid", "test-123");
		const result = cache.get("test-dataset", "bucket-uuid", "test-123");
		expect(result).toBeNull();
	});
});
