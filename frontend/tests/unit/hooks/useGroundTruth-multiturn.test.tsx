import { act, renderHook, waitFor } from "@testing-library/react";
import type { ConversationTurn } from "../../../src/models/groundTruth";
import { getItemReferences } from "../../../src/models/groundTruth";

vi.mock("../../../src/config/demo", () => ({
	default: true,
	DEMO_MODE: true,
	shouldUseDemoProvider: () => true,
	isDemoModeIgnored: () => false,
}));

vi.mock("../../../src/services/telemetry", () => ({
	logEvent: vi.fn(),
	logException: vi.fn(),
	logTrace: vi.fn(),
}));

let useGroundTruth: typeof import("../../../src/hooks/useGroundTruth").default;

beforeAll(async () => {
	vi.resetModules();
	({ default: useGroundTruth } = await import(
		"../../../src/hooks/useGroundTruth"
	));
});

async function setupHook() {
	const utils = renderHook(() => useGroundTruth());
	await waitFor(() => {
		expect(utils.result.current.current).toBeTruthy();
	});
	return utils;
}

describe("useGroundTruth multi-turn flows", () => {
	it("updateHistory syncs latest user and agent to question/answer", async () => {
		const { result } = await setupHook();
		const history: ConversationTurn[] = [
			{ role: "user", content: "New question" },
			{ role: "agent", content: "Fresh answer" },
		];
		await act(async () => {
			result.current.updateHistory(history);
		});
		expect(result.current.current?.history).toHaveLength(2);
		expect(result.current.current?.history?.[0]).toMatchObject({
			role: "user",
			content: "New question",
		});
		expect(result.current.current?.history?.[1]).toMatchObject({
			role: "agent",
			content: "Fresh answer",
		});
		expect(
			result.current.current?.history?.every((turn) => !!turn.turnId),
		).toBe(true);
		expect(result.current.current?.question).toBe("New question");
		expect(result.current.current?.answer).toBe("Fresh answer");
	});

	it("addTurn appends to history and keeps question/answer in sync", async () => {
		const { result } = await setupHook();
		const initialHistoryLength = result.current.current?.history?.length ?? 0;
		await act(async () => {
			result.current.addTurn("user", "Follow-up question");
		});
		expect(result.current.current?.history?.length).toBe(
			initialHistoryLength + 1,
		);
		expect(result.current.current?.question).toBe("Follow-up question");
		await act(async () => {
			result.current.addTurn("agent", "Agent reply");
		});
		expect(result.current.current?.history?.at(-1)).toMatchObject({
			role: "agent",
			content: "Agent reply",
		});
		expect(result.current.current?.answer).toBe("Agent reply");
	});

	it("stateSignature ignores visitedAt mutations for hasUnsaved", async () => {
		const { result } = await setupHook();
		const before = result.current.hasUnsaved;
		const current = result.current.current;
		expect(current).toBeTruthy();
		if (!current) {
			throw new Error("Expected current item");
		}
		const firstRef = getItemReferences(current)[0];
		expect(firstRef).toBeTruthy();
		await act(async () => {
			if (firstRef) {
				result.current.openReference(firstRef);
			}
		});
		expect(result.current.hasUnsaved).toBe(before);
	});

	it("stateSignature changes when reference messageIndex updates", async () => {
		const { result } = await setupHook();
		const current = result.current.current;
		expect(current).toBeTruthy();
		if (!current) {
			throw new Error("Expected current item");
		}
		const ref = getItemReferences(current)[0];
		expect(ref).toBeTruthy();
		await act(async () => {
			if (ref) {
				result.current.updateReference(ref.id, { messageIndex: 0 });
			}
		});
		expect(result.current.hasUnsaved).toBe(true);
	});

	it("marks unsaved when history changes", async () => {
		const { result } = await setupHook();
		await act(async () => {
			result.current.addTurn("user", "New turn");
		});
		expect(result.current.hasUnsaved).toBe(true);
	});
});
