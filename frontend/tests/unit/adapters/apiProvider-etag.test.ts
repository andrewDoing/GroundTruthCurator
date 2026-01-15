import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProvider } from "../../../src/adapters/apiProvider";
import type { components } from "../../../src/api/generated";
import type { GroundTruthItem } from "../../../src/models/groundTruth";

type ApiItem = components["schemas"]["GroundTruthItem-Output"];

const {
	mockGetMyAssignments,
	mockUpdateAssignedGroundTruth,
	mockDeleteGroundTruth,
	mockGetGroundTruthRaw,
} = vi.hoisted(() => ({
	mockGetMyAssignments: vi.fn(),
	mockUpdateAssignedGroundTruth: vi.fn(),
	mockDeleteGroundTruth: vi.fn(),
	mockGetGroundTruthRaw: vi.fn(),
}));

vi.mock("../../../src/services/assignments", () => ({
	getMyAssignments: mockGetMyAssignments,
	updateAssignedGroundTruth: mockUpdateAssignedGroundTruth,
	duplicateItem: vi.fn(),
}));

vi.mock("../../../src/services/groundTruths", () => ({
	deleteGroundTruth: mockDeleteGroundTruth,
	getGroundTruthRaw: mockGetGroundTruthRaw,
}));

function makeApiItem(overrides: Partial<ApiItem> = {}): ApiItem {
	return {
		id: "gt-1",
		status: "draft",
		answer: "Original answer",
		synthQuestion: "Synth question",
		editedQuestion: "Edited question",
		history: [],
		refs: [],
		tags: [],
		comment: null,
		datasetName: "dataset-1",
		bucket: "bucket-1" as ApiItem["bucket"],
		_etag: "etag-1",
		...overrides,
	} as ApiItem;
}

beforeEach(() => {
	mockGetMyAssignments.mockReset();
	mockUpdateAssignedGroundTruth.mockReset();
	mockDeleteGroundTruth.mockReset();
	mockGetGroundTruthRaw.mockReset();
});

describe("ApiProvider ETag 412 retry behavior", () => {
	it("retries with fresh ETag when 412 is returned", async () => {
		const originalItem = makeApiItem({ _etag: "etag-original" });
		const freshItem = makeApiItem({ _etag: "etag-fresh" });
		const updatedItem = makeApiItem({
			_etag: "etag-after-update",
			answer: "Updated answer",
		});

		mockGetMyAssignments.mockResolvedValue([originalItem]);

		// First call throws 412, second call succeeds
		mockUpdateAssignedGroundTruth
			.mockRejectedValueOnce({ status: 412 })
			.mockResolvedValueOnce(updatedItem);

		// Fresh fetch returns item with new etag
		mockGetGroundTruthRaw.mockResolvedValue(freshItem);

		const provider = new ApiProvider();
		const { items } = await provider.list();

		const domainItem: GroundTruthItem = {
			...items[0],
			answer: "Updated answer",
		};

		const result = await provider.save(domainItem);

		// Verify retry flow
		expect(mockUpdateAssignedGroundTruth).toHaveBeenCalledTimes(2);
		expect(mockGetGroundTruthRaw).toHaveBeenCalledTimes(1);
		expect(mockGetGroundTruthRaw).toHaveBeenCalledWith(
			"dataset-1",
			"bucket-1",
			"gt-1",
		);

		// First call used original etag
		expect(mockUpdateAssignedGroundTruth.mock.calls[0][4]).toBe("etag-original");

		// Second call used fresh etag
		expect(mockUpdateAssignedGroundTruth.mock.calls[1][4]).toBe("etag-fresh");

		// Result should be the updated item
		expect(result.answer).toBe("Updated answer");
	});

	it("updates cache with fresh ETag after 412 retry", async () => {
		const originalItem = makeApiItem({ _etag: "etag-original" });
		const freshItem = makeApiItem({ _etag: "etag-fresh" });
		const updatedItem = makeApiItem({ _etag: "etag-after-update" });

		mockGetMyAssignments.mockResolvedValue([originalItem]);
		mockUpdateAssignedGroundTruth
			.mockRejectedValueOnce({ status: 412 })
			.mockResolvedValueOnce(updatedItem);
		mockGetGroundTruthRaw.mockResolvedValue(freshItem);

		const provider = new ApiProvider();
		const { items } = await provider.list();

		await provider.save(items[0]);

		// Save again - should use the updated etag, not the original
		mockUpdateAssignedGroundTruth.mockResolvedValueOnce(updatedItem);

		await provider.save(items[0]);

		// Third call (second save) should use the etag from updatedItem
		expect(mockUpdateAssignedGroundTruth).toHaveBeenCalledTimes(3);
		expect(mockUpdateAssignedGroundTruth.mock.calls[2][4]).toBe(
			"etag-after-update",
		);
	});

	it("throws non-412 errors without retry", async () => {
		const originalItem = makeApiItem();
		mockGetMyAssignments.mockResolvedValue([originalItem]);

		const serverError = { status: 500, message: "Internal Server Error" };
		mockUpdateAssignedGroundTruth.mockRejectedValue(serverError);

		const provider = new ApiProvider();
		const { items } = await provider.list();

		await expect(provider.save(items[0])).rejects.toEqual(serverError);

		// Should not have called getGroundTruthRaw
		expect(mockGetGroundTruthRaw).not.toHaveBeenCalled();

		// Should only have tried once
		expect(mockUpdateAssignedGroundTruth).toHaveBeenCalledTimes(1);
	});

	it("handles 412 from response.status property (alternative error shape)", async () => {
		const originalItem = makeApiItem({ _etag: "etag-original" });
		const freshItem = makeApiItem({ _etag: "etag-fresh" });
		const updatedItem = makeApiItem({ _etag: "etag-after-update" });

		mockGetMyAssignments.mockResolvedValue([originalItem]);

		// Error with response.status instead of status
		mockUpdateAssignedGroundTruth
			.mockRejectedValueOnce({ response: { status: 412 } })
			.mockResolvedValueOnce(updatedItem);

		mockGetGroundTruthRaw.mockResolvedValue(freshItem);

		const provider = new ApiProvider();
		const { items } = await provider.list();

		const result = await provider.save(items[0]);

		// Should have retried
		expect(mockUpdateAssignedGroundTruth).toHaveBeenCalledTimes(2);
		expect(mockGetGroundTruthRaw).toHaveBeenCalledTimes(1);
		expect(result).toBeTruthy();
	});

	it("handles 400 error without retry", async () => {
		const originalItem = makeApiItem();
		mockGetMyAssignments.mockResolvedValue([originalItem]);

		const badRequestError = { status: 400, message: "Bad Request" };
		mockUpdateAssignedGroundTruth.mockRejectedValue(badRequestError);

		const provider = new ApiProvider();
		const { items } = await provider.list();

		await expect(provider.save(items[0])).rejects.toEqual(badRequestError);

		expect(mockGetGroundTruthRaw).not.toHaveBeenCalled();
		expect(mockUpdateAssignedGroundTruth).toHaveBeenCalledTimes(1);
	});

	it("uses fresh etag even when original etag is undefined", async () => {
		const originalItem = makeApiItem({ _etag: undefined });
		const freshItem = makeApiItem({ _etag: "etag-fresh" });
		const updatedItem = makeApiItem({ _etag: "etag-after-update" });

		mockGetMyAssignments.mockResolvedValue([originalItem]);
		mockUpdateAssignedGroundTruth
			.mockRejectedValueOnce({ status: 412 })
			.mockResolvedValueOnce(updatedItem);
		mockGetGroundTruthRaw.mockResolvedValue(freshItem);

		const provider = new ApiProvider();
		const { items } = await provider.list();

		await provider.save(items[0]);

		// First call with undefined etag
		expect(mockUpdateAssignedGroundTruth.mock.calls[0][4]).toBeUndefined();

		// Second call with fresh etag
		expect(mockUpdateAssignedGroundTruth.mock.calls[1][4]).toBe("etag-fresh");
	});
});
