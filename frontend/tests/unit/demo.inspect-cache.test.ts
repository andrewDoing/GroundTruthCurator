import { beforeEach, describe, expect, it, vi } from "vitest";

const cacheMocks = vi.hoisted(() => ({
	invalidateGroundTruthCache: vi.fn(),
}));

vi.mock("../../src/hooks/useGroundTruthCache", () => ({
	invalidateGroundTruthCache: cacheMocks.invalidateGroundTruthCache,
}));

import { invalidateInspectCacheForExplorerItem } from "../../src/demo";

describe("invalidateInspectCacheForExplorerItem", () => {
	beforeEach(() => {
		cacheMocks.invalidateGroundTruthCache.mockClear();
	});

	it("invalidates the inspect cache when explorer items have full identifiers", () => {
		invalidateInspectCacheForExplorerItem({
			id: "item-123",
			datasetName: "dataset-a",
			bucket: "bucket-a",
		});

		expect(cacheMocks.invalidateGroundTruthCache).toHaveBeenCalledWith(
			"dataset-a",
			"bucket-a",
			"item-123",
		);
	});

	it("skips invalidation when explorer item metadata is incomplete", () => {
		invalidateInspectCacheForExplorerItem({
			id: "item-123",
			datasetName: undefined,
			bucket: "bucket-a",
		});

		expect(cacheMocks.invalidateGroundTruthCache).not.toHaveBeenCalled();
	});
});
