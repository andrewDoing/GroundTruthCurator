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

describe("useGroundTruth duplicateCurrent", () => {
	it("duplicates current item, inserts at top, and selects it", async () => {
		const { result } = renderHook(() => useGroundTruth());
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});
		const initialSelected = result.current.current;
		expect(initialSelected).toBeTruthy();
		const initialLen = result.current.items.length;

		// Perform duplicate
		await act(async () => {
			const res = await result.current.duplicateCurrent();
			expect(res.ok).toBe(true);
		});

		// The list length increases by 1
		expect(result.current.items.length).toBe(initialLen + 1);
		// The new selection is the newly created item (top of list)
		const newCurrent = result.current.current;
		expect(newCurrent).toBeTruthy();
		expect(newCurrent?.id).not.toBe(initialSelected?.id);
		expect(result.current.items[0].id).toBe(newCurrent?.id);
		// Has rephrase tag
		const tag = `rephrase:${initialSelected?.id}`;
		expect(newCurrent?.tags?.includes(tag)).toBe(true);
	});
});
