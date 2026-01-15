import { act, renderHook, waitFor } from "@testing-library/react";
import type { ConversationTurn } from "../../../src/models/groundTruth";

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

describe("useGroundTruth deleteTurn", () => {
	it("should delete a middle turn and re-index references correctly", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		// Wait for initial list load
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		// Setup multi-turn conversation with references
		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
			{ role: "user", content: "Second question" },
			{ role: "agent", content: "Second answer" },
			{ role: "user", content: "Third question" },
			{ role: "agent", content: "Third answer" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		// Clear existing references first, then add test references
		await act(async () => {
			if (result.current.current) {
				result.current.current.references = [];
			}
		});

		// Add references for different turns
		await act(async () => {
			result.current.addReferences([
				{ id: "ref1", url: "http://example.com/1", messageIndex: 1 },
				{ id: "ref2", url: "http://example.com/2", messageIndex: 3 },
				{ id: "ref3", url: "http://example.com/3", messageIndex: 5 },
			]);
		});

		expect(result.current.current?.history?.length).toBe(6);
		expect(result.current.current?.references?.length).toBe(3);

		// Delete turn at index 2 (second user turn)
		await act(async () => {
			result.current.deleteTurn(2);
		});

		// Verify turn was deleted
		expect(result.current.current?.history?.length).toBe(5);
		expect(result.current.current?.history?.[2].content).toBe("Second answer");

		// Verify references were re-indexed
		// When we delete turn 2, references are NOT deleted for turn 2,
		// they are deleted if they HAVE messageIndex === 2
		// In our case: ref1 has messageIndex 1, ref2 has messageIndex 3, ref3 has messageIndex 5
		// None have messageIndex === 2, so all 3 should remain, just shifted down
		const refs = result.current.current?.references || [];
		expect(refs.length).toBe(3); // All refs remain, just re-indexed
		
		const ref1 = refs.find((r) => r.id === "ref1");
		const ref2 = refs.find((r) => r.id === "ref2");
		const ref3 = refs.find((r) => r.id === "ref3");
		
		expect(ref1?.messageIndex).toBe(1); // Unchanged (before deleted turn)
		expect(ref2?.messageIndex).toBe(2); // Shifted down from 3 to 2
		expect(ref3?.messageIndex).toBe(4); // Shifted down from 5 to 4
	});

	it("should delete the first turn", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
			{ role: "user", content: "Second question" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		// Clear existing references first
		await act(async () => {
			if (result.current.current) {
				result.current.current.references = [];
			}
		});

		await act(async () => {
			result.current.addReferences([
				{ id: "ref1", url: "http://example.com/1", messageIndex: 1 },
				{ id: "ref2", url: "http://example.com/2", messageIndex: 2 },
			]);
		});

		// Delete first turn
		await act(async () => {
			result.current.deleteTurn(0);
		});

		expect(result.current.current?.history?.length).toBe(2);
		expect(result.current.current?.history?.[0].content).toBe("First answer");

		// All references should be shifted down
		const refs = result.current.current?.references || [];
		expect(refs.find((r) => r.id === "ref1")?.messageIndex).toBe(0);
		expect(refs.find((r) => r.id === "ref2")?.messageIndex).toBe(1);
	});

	it("should delete the last turn", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
			{ role: "user", content: "Second question" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		// Clear existing references first
		await act(async () => {
			if (result.current.current) {
				result.current.current.references = [];
			}
		});

		await act(async () => {
			result.current.addReferences([
				{ id: "ref1", url: "http://example.com/1", messageIndex: 1 },
				{ id: "ref2", url: "http://example.com/2", messageIndex: 2 },
			]);
		});

		// Delete last turn
		await act(async () => {
			result.current.deleteTurn(2);
		});

		expect(result.current.current?.history?.length).toBe(2);
		expect(result.current.current?.history?.[1].content).toBe("First answer");

		// Reference for deleted turn should be removed
		const refs = result.current.current?.references || [];
		expect(refs.length).toBe(1);
		expect(refs.find((r) => r.id === "ref2")).toBeUndefined();
		expect(refs.find((r) => r.id === "ref1")?.messageIndex).toBe(1);
	});

	it("should sync question/answer fields after deletion", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
			{ role: "user", content: "Second question" },
			{ role: "agent", content: "Second answer" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		expect(result.current.current?.question).toBe("Second question");
		expect(result.current.current?.answer).toBe("Second answer");

		// Delete last two turns
		await act(async () => {
			result.current.deleteTurn(3); // Delete last agent turn
		});

		await act(async () => {
			result.current.deleteTurn(2); // Delete last user turn
		});

		// Question and answer should sync to remaining turns
		expect(result.current.current?.question).toBe("First question");
		expect(result.current.current?.answer).toBe("First answer");
	});

	it("should handle deletion with no references", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		// Clear existing references
		await act(async () => {
			if (result.current.current) {
				result.current.current.references = [];
			}
		});

		// Delete turn without any references
		await act(async () => {
			result.current.deleteTurn(0);
		});

		expect(result.current.current?.history?.length).toBe(1);
		expect(result.current.current?.references?.length).toBe(0);
	});

	it("should delete all turns leaving empty history", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "Only question" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		await act(async () => {
			result.current.deleteTurn(0);
		});

		expect(result.current.current?.history?.length).toBe(0);
		expect(result.current.current?.question).toBe("");
		expect(result.current.current?.answer).toBe("");
	});

	it("should handle out-of-range index gracefully", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		const beforeLength = result.current.current?.history?.length;

		// Try to delete with invalid index
		await act(async () => {
			result.current.deleteTurn(10);
		});

		// History should remain unchanged
		expect(result.current.current?.history?.length).toBe(beforeLength);
	});

	it("should remove references for deleted turn while preserving others", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
			{ role: "user", content: "Second question" },
			{ role: "agent", content: "Second answer" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		// Clear existing references first
		await act(async () => {
			if (result.current.current) {
				result.current.current.references = [];
			}
		});

		// Add multiple references for the same turn
		await act(async () => {
			result.current.addReferences([
				{ id: "ref1-turn1", url: "http://example.com/1", messageIndex: 1 },
				{ id: "ref2-turn1", url: "http://example.com/2", messageIndex: 1 },
				{ id: "ref3-turn1", url: "http://example.com/3", messageIndex: 1 },
				{ id: "ref1-turn3", url: "http://example.com/4", messageIndex: 3 },
			]);
		});

		expect(result.current.current?.references?.length).toBe(4);

		// Delete turn at index 1 (first agent turn)
		await act(async () => {
			result.current.deleteTurn(1);
		});

		// All references for turn 1 should be removed
		const refs = result.current.current?.references || [];
		expect(refs.length).toBe(1);
		expect(refs.find((r) => r.id.includes("turn1"))).toBeUndefined();
		
		// Reference for turn 3 should remain but re-indexed to turn 2
		const ref = refs.find((r) => r.id === "ref1-turn3");
		expect(ref).toBeDefined();
		expect(ref?.messageIndex).toBe(2); // Shifted from 3 to 2
	});

	it("should preserve references without messageIndex", async () => {
		const { result } = renderHook(() => useGroundTruth());
		
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const history: ConversationTurn[] = [
			{ role: "user", content: "First question" },
			{ role: "agent", content: "First answer" },
		];

		await act(async () => {
			result.current.updateHistory(history);
		});

		// Clear existing references first
		await act(async () => {
			if (result.current.current) {
				result.current.current.references = [];
			}
		});

		// Add references with and without messageIndex
		await act(async () => {
			result.current.addReferences([
				{ id: "ref-with-index", url: "http://example.com/1", messageIndex: 1 },
				{ id: "ref-without-index", url: "http://example.com/2" }, // No messageIndex
			]);
		});

		expect(result.current.current?.references?.length).toBe(2);

		// Delete turn
		await act(async () => {
			result.current.deleteTurn(1);
		});

		// Reference without messageIndex should be preserved
		const refs = result.current.current?.references || [];
		expect(refs.length).toBe(1);
		expect(refs.find((r) => r.id === "ref-without-index")).toBeDefined();
		expect(refs.find((r) => r.id === "ref-with-index")).toBeUndefined();
	});
});
