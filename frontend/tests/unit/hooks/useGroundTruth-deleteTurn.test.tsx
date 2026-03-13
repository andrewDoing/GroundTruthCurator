import { act, renderHook, waitFor } from "@testing-library/react";
import type { ConversationTurn } from "../../../src/models/groundTruth";
import { getItemReferences } from "../../../src/models/groundTruth";

vi.mock("../../../src/config/demo", () => ({
	default: true,
	DEMO_MODE: true,
	shouldUseDemoProvider: () => true,
	isDemoModeIgnored: () => false,
}));

let useGroundTruth: typeof import("../../../src/hooks/useGroundTruth").default;
beforeAll(async () => {
	vi.resetModules();
	({ default: useGroundTruth } = await import(
		"../../../src/hooks/useGroundTruth"
	));
});

function requireCurrent<T>(current: T | null | undefined): T {
	expect(current).toBeTruthy();
	if (!current) {
		throw new Error("Expected current item to be loaded");
	}
	return current;
}

async function loadHook() {
	const hook = renderHook(() => useGroundTruth());
	await waitFor(() => {
		expect(hook.result.current.current).toBeTruthy();
	});
	return hook;
}

async function seedHistory(
	result: { current: ReturnType<typeof useGroundTruth> },
	history: ConversationTurn[],
) {
	await act(async () => {
		result.current.updateHistory(history);
	});
	await act(async () => {
		if (result.current.current) {
			result.current.current.plugins = {};
		}
	});
}

describe("useGroundTruth deleteTurn", () => {
	it("preserves stable turn ownership when deleting a middle turn", async () => {
		const { result } = await loadHook();
		const history: ConversationTurn[] = [
			{ role: "user", content: "First question", turnId: "turn-user-1" },
			{ role: "agent", content: "First answer", turnId: "turn-agent-1" },
			{ role: "user", content: "Second question", turnId: "turn-user-2" },
			{ role: "agent", content: "Second answer", turnId: "turn-agent-2" },
			{ role: "user", content: "Third question", turnId: "turn-user-3" },
			{ role: "agent", content: "Third answer", turnId: "turn-agent-3" },
		];
		await seedHistory(result, history);
		await act(async () => {
			result.current.addReferences([
				{ id: "ref1", url: "http://example.com/1", turnId: "turn-agent-1" },
				{ id: "ref2", url: "http://example.com/2", turnId: "turn-agent-2" },
				{ id: "ref3", url: "http://example.com/3", turnId: "turn-agent-3" },
			]);
		});
		await act(async () => {
			result.current.deleteTurn(2);
		});
		const refs = getItemReferences(requireCurrent(result.current.current));
		expect(result.current.current?.history?.length).toBe(5);
		expect(result.current.current?.history?.[2].turnId).toBe("turn-agent-2");
		expect(refs).toHaveLength(3);
		expect(
			refs.find((ref) => ref.url === "http://example.com/1"),
		).toMatchObject({
			turnId: "turn-agent-1",
		});
		expect(
			refs.find((ref) => ref.url === "http://example.com/2"),
		).toMatchObject({
			turnId: "turn-agent-2",
		});
		expect(
			refs.find((ref) => ref.url === "http://example.com/3"),
		).toMatchObject({
			turnId: "turn-agent-3",
		});
	});

	it("removes references owned by the deleted turn while preserving later turn ids", async () => {
		const { result } = await loadHook();
		const history: ConversationTurn[] = [
			{ role: "user", content: "First question", turnId: "turn-user-1" },
			{ role: "agent", content: "First answer", turnId: "turn-agent-1" },
			{ role: "user", content: "Second question", turnId: "turn-user-2" },
			{ role: "agent", content: "Second answer", turnId: "turn-agent-2" },
		];
		await seedHistory(result, history);
		await act(async () => {
			result.current.addReferences([
				{
					id: "ref1-turn1",
					url: "http://example.com/1",
					turnId: "turn-agent-1",
				},
				{
					id: "ref2-turn1",
					url: "http://example.com/2",
					turnId: "turn-agent-1",
				},
				{
					id: "ref1-turn2",
					url: "http://example.com/3",
					turnId: "turn-agent-2",
				},
			]);
		});
		await act(async () => {
			result.current.deleteTurn(1);
		});
		const refs = getItemReferences(requireCurrent(result.current.current));
		expect(refs).toHaveLength(1);
		expect(refs[0]).toMatchObject({
			url: "http://example.com/3",
			turnId: "turn-agent-2",
		});
		expect(result.current.current?.history?.[2].turnId).toBe("turn-agent-2");
	});

	it("recomputes fallback messageIndex only for references without stable turn ownership", async () => {
		const { result } = await loadHook();
		const history: ConversationTurn[] = [
			{ role: "user", content: "First question", turnId: "turn-user-1" },
			{ role: "agent", content: "First answer", turnId: "turn-agent-1" },
			{ role: "user", content: "Second question", turnId: "turn-user-2" },
		];
		await seedHistory(result, history);
		await act(async () => {
			result.current.addReferences([
				{
					id: "stable",
					url: "http://example.com/stable",
					turnId: "turn-agent-1",
				},
				{ id: "fallback", url: "http://example.com/fallback", messageIndex: 2 },
				{ id: "global", url: "http://example.com/global" },
			]);
		});
		await act(async () => {
			result.current.deleteTurn(0);
		});
		const refs = getItemReferences(requireCurrent(result.current.current));
		expect(
			refs.find((ref) => ref.url === "http://example.com/stable"),
		).toMatchObject({
			turnId: "turn-agent-1",
		});
		expect(
			refs.find((ref) => ref.url === "http://example.com/fallback"),
		).toMatchObject({
			messageIndex: 1,
		});
		expect(
			refs.find((ref) => ref.url === "http://example.com/global"),
		).toBeDefined();
	});

	it("syncs question and answer projections after deletion", async () => {
		const { result } = await loadHook();
		const history: ConversationTurn[] = [
			{ role: "user", content: "First question", turnId: "turn-user-1" },
			{ role: "agent", content: "First answer", turnId: "turn-agent-1" },
			{ role: "user", content: "Second question", turnId: "turn-user-2" },
			{
				role: "orchestrator-agent",
				content: "Second answer",
				turnId: "turn-agent-2",
			},
		];
		await seedHistory(result, history);
		expect(result.current.current?.question).toBe("Second question");
		expect(result.current.current?.answer).toBe("Second answer");
		await act(async () => {
			result.current.deleteTurn(3);
		});
		expect(result.current.current?.question).toBe("Second question");
		expect(result.current.current?.answer).toBe("First answer");
		await act(async () => {
			result.current.deleteTurn(2);
		});
		expect(result.current.current?.question).toBe("First question");
		expect(result.current.current?.answer).toBe("First answer");
	});

	it("handles empty or out-of-range deletions without breaking canonical state", async () => {
		const { result } = await loadHook();
		await seedHistory(result, [
			{ role: "user", content: "Only question", turnId: "turn-user-1" },
		]);
		await act(async () => {
			result.current.deleteTurn(10);
		});
		expect(result.current.current?.history).toHaveLength(1);
		await act(async () => {
			result.current.deleteTurn(0);
		});
		expect(result.current.current?.history).toHaveLength(0);
		expect(result.current.current?.question).toBe("");
		expect(result.current.current?.answer).toBe("");
	});
});
