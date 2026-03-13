import { describe, expect, it, vi } from "vitest";

import { resolveExplorerAssignSelection } from "../../src/demo";

describe("resolveExplorerAssignSelection", () => {
	it("switches to curate and returns a success toast when selection succeeds", async () => {
		const selectItem = vi.fn().mockResolvedValue(true);

		await expect(
			resolveExplorerAssignSelection("item-123", selectItem),
		).resolves.toEqual({
			switchToCurate: true,
			toastKind: "success",
			toastMessage: "Assigned item-123 for curation",
		});
		expect(selectItem).toHaveBeenCalledWith("item-123");
	});

	it("keeps the user in explorer and returns an info toast when selection is cancelled or fails", async () => {
		const selectItem = vi.fn().mockResolvedValue(false);

		await expect(
			resolveExplorerAssignSelection("item-123", selectItem),
		).resolves.toEqual({
			switchToCurate: false,
			toastKind: "info",
			toastMessage:
				"Assigned item-123, but opening it in curate was cancelled or failed.",
		});
		expect(selectItem).toHaveBeenCalledWith("item-123");
	});
});
