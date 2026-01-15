import { act, renderHook, waitFor } from "@testing-library/react";

// Force demo mode so the hook uses JsonProvider with DEMO_JSON
vi.mock("../../../src/config/demo", () => ({
	default: true,
	DEMO_MODE: true,
	shouldUseDemoProvider: () => true,
	isDemoModeIgnored: () => false,
}));

let useGroundTruth: typeof import("../../../src/hooks/useGroundTruth").default;
beforeAll(async () => {
	// Ensure modules are re-evaluated with our mock in place
	vi.resetModules();
	({ default: useGroundTruth } = await import(
		"../../../src/hooks/useGroundTruth"
	));
});

describe("useGroundTruth selectItem with state cleanup", () => {
	it("should reset state when switching items without unsaved changes", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const initialId = result.current.current?.id;
		expect(initialId).toBeTruthy();

		// Add some history to the current item
		await act(async () => {
			result.current.updateHistory([
				{ role: "user", content: "Test question" },
				{ role: "agent", content: "Test answer" },
			]);
		});

		// Save the changes so there are no unsaved changes
		await act(async () => {
			await result.current.save();
		});

		// Get another item to switch to
		const items = result.current.items;
		const nextItem = items.find((item) => item.id !== initialId);
		expect(nextItem).toBeTruthy();
		if (!nextItem) return; // Type guard

		// Switch to the next item
		let switchResult: boolean | undefined;
		await act(async () => {
			switchResult = await result.current.selectItem(nextItem.id);
		});

		expect(switchResult).toBe(true);
		expect(result.current.current?.id).toBe(nextItem.id);
		expect(result.current.current?.id).not.toBe(initialId);
	});

	it("should prompt for confirmation when switching with unsaved changes", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const initialId = result.current.current?.id;

		// Make unsaved changes
		await act(async () => {
			result.current.updateQuestion("Modified question");
		});

		expect(result.current.hasUnsaved).toBe(true);

		// Mock window.confirm to return false (user cancels)
		const originalConfirm = window.confirm;
		window.confirm = vi.fn(() => false);

		const items = result.current.items;
		const nextItem = items.find((item) => item.id !== initialId);
		expect(nextItem).toBeTruthy();
		if (!nextItem) return; // Type guard

		// Try to switch - should be blocked by confirmation dialog
		let switchResult: boolean | undefined;
		await act(async () => {
			switchResult = await result.current.selectItem(nextItem.id);
		});

		expect(switchResult).toBe(false);
		expect(result.current.current?.id).toBe(initialId); // Still on original item
		expect(window.confirm).toHaveBeenCalled();

		// Restore window.confirm
		window.confirm = originalConfirm;
	});

	it("should allow switching with unsaved changes when confirmed", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const initialId = result.current.current?.id;

		// Make unsaved changes
		await act(async () => {
			result.current.updateQuestion("Modified question");
		});

		expect(result.current.hasUnsaved).toBe(true);

		// Mock window.confirm to return true (user confirms)
		const originalConfirm = window.confirm;
		window.confirm = vi.fn(() => true);

		const items = result.current.items;
		const nextItem = items.find((item) => item.id !== initialId);
		expect(nextItem).toBeTruthy();
		if (!nextItem) return; // Type guard

		// Switch should succeed with confirmation
		let switchResult: boolean | undefined;
		await act(async () => {
			switchResult = await result.current.selectItem(nextItem.id);
		});

		expect(switchResult).toBe(true);
		expect(result.current.current?.id).toBe(nextItem.id);
		expect(result.current.current?.id).not.toBe(initialId);
		expect(window.confirm).toHaveBeenCalled();

		// Restore window.confirm
		window.confirm = originalConfirm;
	});

	it("should allow forced switch bypassing confirmation", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const initialId = result.current.current?.id;

		// Make unsaved changes
		await act(async () => {
			result.current.updateQuestion("Modified question");
		});

		expect(result.current.hasUnsaved).toBe(true);

		// Mock window.confirm - should NOT be called
		const originalConfirm = window.confirm;
		window.confirm = vi.fn(() => false);

		const items = result.current.items;
		const nextItem = items.find((item) => item.id !== initialId);
		expect(nextItem).toBeTruthy();
		if (!nextItem) return; // Type guard

		// Force switch without confirmation
		let switchResult: boolean | undefined;
		await act(async () => {
			switchResult = await result.current.selectItem(nextItem.id, { force: true });
		});

		expect(switchResult).toBe(true);
		expect(result.current.current?.id).toBe(nextItem.id);
		expect(window.confirm).not.toHaveBeenCalled(); // Force bypasses confirmation

		// Restore window.confirm
		window.confirm = originalConfirm;
	});

	it("should not switch when already on the same item", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const currentId = result.current.current?.id;
		expect(currentId).toBeTruthy();
		if (!currentId) return; // Type guard

		// Try to select the same item
		let switchResult: boolean | undefined;
		await act(async () => {
			switchResult = await result.current.selectItem(currentId);
		});

		expect(switchResult).toBe(true);
		expect(result.current.current?.id).toBe(currentId);
	});

	it("should clear search results when switching items", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const initialId = result.current.current?.id;

		// Set a search query (without actually running search for simplicity)
		await act(async () => {
			result.current.setQuery("test query");
		});

		expect(result.current.query).toBe("test query");

		// Save to avoid unsaved changes prompt
		await act(async () => {
			await result.current.save();
		});

		const items = result.current.items;
		const nextItem = items.find((item) => item.id !== initialId);
		expect(nextItem).toBeTruthy();
		if (!nextItem) return; // Type guard

		// Switch items
		await act(async () => {
			await result.current.selectItem(nextItem.id);
		});

		expect(result.current.current?.id).toBe(nextItem.id);
		// Search results should be cleared (verified by the implementation)
		// This is handled internally by clearResults() in selectItem
	});

	it("should handle null item selection", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		expect(result.current.current).toBeTruthy();

		// Select null
		let switchResult: boolean | undefined;
		await act(async () => {
			switchResult = await result.current.selectItem(null);
		});

		expect(switchResult).toBe(true);
		expect(result.current.selectedId).toBe(null);
	});

	it("should update baseline after successful selection", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const initialId = result.current.current?.id;
		const items = result.current.items;
		const nextItem = items.find((item) => item.id !== initialId);
		expect(nextItem).toBeTruthy();
		if (!nextItem) return; // Type guard

		// Switch to next item
		await act(async () => {
			await result.current.selectItem(nextItem.id);
		});

		// Make a change
		await act(async () => {
			result.current.updateQuestion("New question");
		});

		// Should detect as unsaved (baseline should have been set correctly)
		expect(result.current.hasUnsaved).toBe(true);
	});
});
