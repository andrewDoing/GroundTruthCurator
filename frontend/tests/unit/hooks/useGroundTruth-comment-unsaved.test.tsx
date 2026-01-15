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

describe("useGroundTruth comment unsaved detection", () => {
	it("marks unsaved when comment changes", async () => {
		const { result } = renderHook(() => useGroundTruth());
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});
		expect(result.current.current).toBeTruthy();
		const before = result.current.hasUnsaved;
		await act(async () => {
			result.current.updateComment("note");
		});
		expect(result.current.hasUnsaved).toBe(true);
		expect(before).toBe(false);
	});
});
