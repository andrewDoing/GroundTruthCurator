import { act, renderHook, waitFor } from "@testing-library/react";
import type {
	ConversationTurn,
	GroundTruthItem,
	Reference,
} from "../../../src/models/groundTruth";

vi.mock("../../../src/config/demo", () => ({
	default: true,
	DEMO_MODE: true,
	shouldUseDemoProvider: () => true,
	isDemoModeIgnored: () => false,
}));

const callAgentChatMock = vi.fn();

vi.mock("../../../src/services/chatService", async () => {
	const actual = await vi.importActual<
		typeof import("../../../src/services/chatService")
	>("../../../src/services/chatService");
	return {
		...actual,
		callAgentChat: callAgentChatMock,
	};
});

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

afterEach(() => {
	callAgentChatMock.mockReset();
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
		expect(result.current.current?.history).toEqual(history);
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

	it("generateAgentTurn appends agent response with references", async () => {
		const { result } = await setupHook();
		await act(async () => {
			result.current.addTurn("user", "Need help with a CAD application");
		});
		callAgentChatMock.mockResolvedValue({
			content: " Generated agent guidance ",
			references: [
				{
					id: "chat-ref-1",
					title: "Doc",
					url: "https://docs.example.com/agent",
					snippet: "Snippet",
					keyParagraph: "Key",
				},
			],
		});
		await act(async () => {
			const res = await result.current.generateAgentTurn(-1);
			expect(res.ok).toBe(true);
			expect(res).toMatchObject({ messageIndex: 1 });
		});
		expect(callAgentChatMock).toHaveBeenCalledTimes(1);
		const current = result.current.current as GroundTruthItem;
		expect(current.history?.length).toBe(2);
		expect(current.history?.[1]).toMatchObject({
			role: "agent",
			content: "Generated agent guidance",
		});
		const refsForTurn = (current.references || []).filter(
			(r) => r.messageIndex === 1,
		);
		expect(refsForTurn).toHaveLength(1);
		expect(refsForTurn[0]).toMatchObject({
			url: "https://docs.example.com/agent",
			snippet: "Snippet",
			keyParagraph: "Key",
		});
	});

	it("generateAgentTurn fails when no prior user turn exists", async () => {
		const { result } = await setupHook();
		callAgentChatMock.mockResolvedValue({ content: "x", references: [] });
		await act(async () => {
			const res = await result.current.generateAgentTurn(-1);
			expect(res.ok).toBe(false);
			if (!res.ok) {
				expect(res.error).toMatch(/user turn/i);
			}
		});
		expect(callAgentChatMock).not.toHaveBeenCalled();
	});

	it("regenerateAgentTurn updates only targeted agent turn and references", async () => {
		const { result } = await setupHook();
		const seedHistory: ConversationTurn[] = [
			{ role: "user", content: "Original Q" },
			{ role: "agent", content: "Outdated A" },
			{ role: "user", content: "Second Q" },
		];
		await act(async () => {
			result.current.updateHistory(seedHistory);
			result.current.addReferences([
				{
					id: "turn-ref",
					title: "Old",
					url: "https://ref.example.com/old",
					snippet: "Old snippet",
					messageIndex: 1,
				},
			] as Reference[]);
		});
		callAgentChatMock.mockResolvedValue({
			content: "Updated agent answer",
			references: [
				{
					id: "chat-ref-2",
					url: "https://ref.example.com/new",
					snippet: "New snippet",
					keyParagraph: "New key",
				},
			],
		});
		await act(async () => {
			const res = await result.current.regenerateAgentTurn(1);
			expect(res.ok).toBe(true);
		});
		const history = result.current.current?.history ?? [];
		expect(history[1]).toMatchObject({ content: "Updated agent answer" });
		expect(history[0]).toMatchObject({ content: "Original Q" });
		expect(history[2]).toMatchObject({ content: "Second Q" });
		const refs = result.current.current?.references ?? [];
		const refsForTurn = refs.filter((r) => r.messageIndex === 1);
		expect(refsForTurn).toHaveLength(1);
		expect(refsForTurn[0].url).toBe("https://ref.example.com/new");
	});

	it("regenerateAgentTurn rejects non-agent turns", async () => {
		const { result } = await setupHook();
		const seedHistory: ConversationTurn[] = [
			{ role: "user", content: "Q" },
			{ role: "user", content: "Another" },
		];
		await act(async () => {
			result.current.updateHistory(seedHistory);
		});
		await act(async () => {
			const res = await result.current.regenerateAgentTurn(1);
			expect(res.ok).toBe(false);
			if (!res.ok) {
				expect(res.error).toMatch(/only agent turns/i);
			}
		});
	});

	it("stateSignature ignores visitedAt mutations for hasUnsaved", async () => {
		const { result } = await setupHook();
		const before = result.current.hasUnsaved;
		const firstRef = result.current.current?.references?.[0];
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
		const ref = result.current.current?.references?.[0];
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
