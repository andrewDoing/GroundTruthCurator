import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProvider } from "../../../src/adapters/apiProvider";
import type { components } from "../../../src/api/generated";
import type {
	GroundTruthItem,
	Reference,
} from "../../../src/models/groundTruth";

const {
	mockGetMyAssignments,
	mockUpdateAssignedGroundTruth,
	mockDeleteGroundTruth,
	mockGetGroundTruth,
} = vi.hoisted(() => ({
	mockGetMyAssignments: vi.fn(),
	mockUpdateAssignedGroundTruth: vi.fn(),
	mockDeleteGroundTruth: vi.fn(),
	mockGetGroundTruth: vi.fn(),
}));

vi.mock("../../../src/services/assignments", () => ({
	getMyAssignments: mockGetMyAssignments,
	updateAssignedGroundTruth: mockUpdateAssignedGroundTruth,
	duplicateItem: vi.fn(),
}));

vi.mock("../../../src/services/groundTruths", () => ({
	deleteGroundTruth: mockDeleteGroundTruth,
	getGroundTruth: mockGetGroundTruth,
}));

type ApiItem = components["schemas"]["GroundTruthItem-Output"];

type Patch = Partial<ApiItem>;

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
	mockGetGroundTruth.mockReset();
});

describe("ApiProvider multi-turn mapping", () => {
	it("list maps history roles and content", async () => {
		const apiItem = makeApiItem({
			history: [
				{ role: "user", msg: "How do I?" },
				{ role: "assistant", msg: "Use the regenerate command." },
			],
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items).toHaveLength(1);
		const history = items[0].history ?? [];
		expect(history[0]).toMatchObject({ role: "user", content: "How do I?" });
		expect(history[1]).toMatchObject({
			role: "agent",
			content: "Use the regenerate command.",
		});
	});

	it("list maps per-turn refs with messageIndex", async () => {
		const apiItem = makeApiItem({
			history: [
				{ role: "user", msg: "Q" },
				{
					role: "assistant",
					msg: "A",
					refs: [
						{
							url: "https://turn.ref",
							content: "Snippet",
							keyExcerpt: "Key",
							bonus: true,
						},
					],
				},
			],
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		const refs = items[0].references;
		const turnRef = refs.find((r) => r.messageIndex === 1);
		expect(turnRef).toBeTruthy();
		expect(turnRef?.url).toBe("https://turn.ref");
		expect(turnRef?.bonus).toBe(true);
	});

	it("list includes top-level refs with messageIndex=1 for legacy items (Bug Fix: SA-86)", async () => {
		// Legacy single-turn items have no history (or empty history array)
		// Top-level refs should be assigned to the agent turn (messageIndex = 1)
		const apiItem = makeApiItem({
			refs: [
				{
					url: "https://top.ref",
					content: "Top snippet",
					keyExcerpt: "Top key",
					bonus: false,
				},
			],
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		const topRef = items[0].references.find(
			(r: Reference) => r.url === "https://top.ref",
		);
		expect(topRef).toBeTruthy();
		// Legacy items: refs assigned to agent turn
		expect(topRef?.messageIndex).toBe(1);
	});

	it("list does not apply top-level tags to user turn when converting single-turn", async () => {
		const apiItem = makeApiItem({
			synthQuestion: "What is X?",
			editedQuestion: "What is X exactly?",
			answer: "X is Y",
			tags: ["important", "technical"],
			history: undefined, // No history = single-turn item
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items).toHaveLength(1);
		const history = items[0].history ?? [];
		expect(history).toHaveLength(2);
		expect(history[0]).toMatchObject({
			role: "user",
			content: "What is X exactly?",
		});
		expect(history[1]).toMatchObject({
			role: "agent",
			content: "X is Y",
		});
	});

	it("list assigns refs to messageIndex 1 when converting single-turn with answer", async () => {
		const apiItem = makeApiItem({
			synthQuestion: "Question",
			answer: "Answer",
			refs: [
				{
					url: "https://example.com",
					content: "content",
					keyExcerpt: "key",
					bonus: false,
				},
			],
			history: undefined,
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items[0].references).toHaveLength(1);
		expect(items[0].references[0].messageIndex).toBe(1);
	});

	it("list assigns refs to messageIndex 1 even when answer is missing (Bug Fix: SA-86)", async () => {
		const apiItem = makeApiItem({
			synthQuestion: "Question",
			answer: "",
			refs: [
				{
					url: "https://example.com",
					content: "content",
					keyExcerpt: "key",
					bonus: false,
				},
			],
			history: undefined,
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items[0].references).toHaveLength(1);
		expect(items[0].references[0].messageIndex).toBe(1);
	});

	it("list creates empty agent turn when question exists but answer is missing (Bug Fix: SA-86)", async () => {
		const apiItem = makeApiItem({
			synthQuestion: "Question without answer",
			editedQuestion: undefined, // No edited question
			answer: "",
			history: undefined,
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items[0].history).toHaveLength(2);
		expect(items[0].history?.[0]).toMatchObject({
			role: "user",
			content: "Question without answer",
		});
		expect(items[0].history?.[1]).toMatchObject({
			role: "agent",
			content: "",
		});
	});

	it("list creates empty agent turn for null answer (Bug Fix: SA-86)", async () => {
		const apiItem = makeApiItem({
			synthQuestion: "Question",
			answer: null as unknown as string,
			history: undefined,
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items[0].history).toHaveLength(2);
		expect(items[0].history?.[1]).toMatchObject({
			role: "agent",
			content: "",
		});
	});

	it("list assigns refs to messageIndex 1 for question with refs but no answer (Bug Fix: SA-86)", async () => {
		const apiItem = makeApiItem({
			editedQuestion: "How do I configure authentication for my app?",
			answer: "",
			refs: [
				{
					url: "https://docs.example.com/auth",
					content: "Authentication documentation content",
					keyExcerpt: "Use OAuth 2.0 for authentication",
					bonus: false,
				},
				{
					url: "https://docs.example.com/config",
					content: "Configuration guide",
					bonus: false,
				},
			],
			history: undefined,
		});
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		expect(items[0].history).toHaveLength(2);
		expect(items[0].history?.[0].content).toBe(
			"How do I configure authentication for my app?",
		);
		expect(items[0].history?.[1].content).toBe("");
		expect(items[0].references).toHaveLength(2);
		expect(items[0].references[0].messageIndex).toBe(1);
		expect(items[0].references[1].messageIndex).toBe(1);
	});
});

describe("ApiProvider multi-turn serialization", () => {
	it("save serializes history roles and agent refs", async () => {
		const apiItem = makeApiItem({
			history: [
				{ role: "user", msg: "Original Q" },
				{ role: "assistant", msg: "Original A" },
			],
		});
		let capturedPatch: Patch | undefined;
		mockUpdateAssignedGroundTruth.mockImplementation(
			async (_dataset: string, _bucket: string, id: string, patch: Patch) => {
				capturedPatch = patch;
				return {
					...apiItem,
					id,
					history: (patch.history as ApiItem["history"]) ?? apiItem.history,
					refs: (patch.refs as ApiItem["refs"]) ?? apiItem.refs,
					answer: (patch.answer as string) ?? apiItem.answer,
					editedQuestion:
						(patch.editedQuestion as string) ?? apiItem.editedQuestion,
					status: (patch.status as ApiItem["status"]) ?? apiItem.status,
				} as ApiItem;
			},
		);
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		const domain = items[0];
		const history: NonNullable<GroundTruthItem["history"]> = [
			{ role: "user", content: "Updated Q" },
			{ role: "agent", content: "Updated A" },
		];
		const refs: Reference[] = [
			{ id: "global", url: "https://global" },
			{
				id: "turn",
				url: "https://turn",
				messageIndex: 1,
			},
		];
		const updated: GroundTruthItem = {
			...domain,
			history,
			references: refs,
		};
		await provider.save(updated);
		expect(capturedPatch).toBeDefined();
		const patch = capturedPatch as Patch;
		const patchHistory = patch.history as ApiItem["history"];
		expect(patchHistory?.[0]?.role).toBe("user");
		expect(patchHistory?.[1]?.role).toBe("assistant");
		const agentRefs = patchHistory?.[1]?.refs;
		expect(agentRefs).toHaveLength(1);
		expect(agentRefs?.[0]?.url).toBe("https://turn");
		const userRefs = patchHistory?.[0]?.refs;
		expect(userRefs).toBeUndefined();
	});

	it("save omits agent refs when none provided", async () => {
		const apiItem = makeApiItem({
			history: [
				{ role: "user", msg: "Original Q" },
				{ role: "assistant", msg: "Original A" },
			],
		});
		let capturedPatch: Patch | undefined;
		mockUpdateAssignedGroundTruth.mockImplementation(
			async (_dataset: string, _bucket: string, _id: string, patch: Patch) => {
				capturedPatch = patch;
				return apiItem;
			},
		);
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		const domain = items[0];
		const history: NonNullable<GroundTruthItem["history"]> = [
			{ role: "user", content: "Updated Q" },
			{ role: "agent", content: "Updated A" },
		];
		const refs: Reference[] = [{ id: "global", url: "https://global" }];
		const updated: GroundTruthItem = {
			...domain,
			history,
			references: refs,
		};
		await provider.save(updated);
		expect(capturedPatch).toBeDefined();
		const patch = capturedPatch as Patch;
		const patchHistory = patch.history as ApiItem["history"];
		expect(patchHistory?.[1]?.refs).toBeUndefined();
	});

	it("save excludes refs for user turns even if provided", async () => {
		const apiItem = makeApiItem({
			history: [
				{ role: "user", msg: "Original Q" },
				{ role: "assistant", msg: "Original A" },
			],
		});
		let capturedPatch: Patch | undefined;
		mockUpdateAssignedGroundTruth.mockImplementation(
			async (_dataset: string, _bucket: string, id: string, patch: Patch) => {
				capturedPatch = patch;
				void id;
				return apiItem;
			},
		);
		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();
		const domain = items[0];
		const history: NonNullable<GroundTruthItem["history"]> = [
			{ role: "user", content: "Updated Q" },
			{ role: "agent", content: "Updated A" },
		];
		const refs: Reference[] = [
			{
				id: "user-ref",
				url: "https://user",
				messageIndex: 0,
			},
			{
				id: "agent-ref",
				url: "https://agent",
				messageIndex: 1,
			},
		];
		const updated: GroundTruthItem = {
			...domain,
			history,
			references: refs,
		};
		await provider.save(updated);
		expect(capturedPatch).toBeDefined();
		const patch = capturedPatch as Patch;
		const patchHistory = patch.history as ApiItem["history"];
		expect(patchHistory?.[0]?.refs).toBeUndefined();
		expect(patchHistory?.[1]?.refs).toHaveLength(1);
		expect(patchHistory?.[1]?.refs?.[0]?.url).toBe("https://agent");
	});

	it("save preserves top-level refs for legacy single-turn items (SA-86 bug fix)", async () => {
		// Regression test for bug where top-level refs were wiped on save
		// Legacy single-turn items have refs at top-level (no history).
		// When loaded, fromApi() converts them to multi-turn and assigns messageIndex=1.
		// When saved, toPatch() must save them back to top-level to prevent data loss.
		const apiItem = makeApiItem({
			synthQuestion: "What is X?",
			answer: "X is Y",
			refs: [
				{
					url: "https://legacy.ref/doc1",
					content: "Legacy content",
					keyExcerpt: "Key paragraph",
					bonus: false,
				},
				{
					url: "https://legacy.ref/doc2",
					content: "Bonus content",
					bonus: true,
				},
			],
			history: undefined, // No history = legacy single-turn item
		});

		let capturedPatch: Patch | undefined;
		mockUpdateAssignedGroundTruth.mockImplementation(
			async (_dataset: string, _bucket: string, id: string, patch: Patch) => {
				capturedPatch = patch;
				return {
					...apiItem,
					id,
					refs: (patch.refs as ApiItem["refs"]) ?? apiItem.refs,
					status: (patch.status as ApiItem["status"]) ?? apiItem.status,
				} as ApiItem;
			},
		);

		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();

		// Verify fromApi() assigned messageIndex=1 to legacy refs
		expect(items[0].references).toHaveLength(2);
		expect(items[0].references[0].messageIndex).toBe(1);
		expect(items[0].references[1].messageIndex).toBe(1);

		// User might edit the item (e.g., change bonus flag, add key paragraph)
		const updated: GroundTruthItem = {
			...items[0],
			references: items[0].references.map((r: Reference) =>
				r.url === "https://legacy.ref/doc1"
					? { ...r, bonus: true, keyParagraph: "Updated key" }
					: r,
			),
		};

		// Save the item
		await provider.save(updated);

		// Verify the patch preserves top-level refs (not wiped out)
		expect(capturedPatch).toBeDefined();
		const patch = capturedPatch as Patch;
		expect(patch.refs).toBeDefined();
		expect(patch.refs).toHaveLength(2);

		// Verify refs are saved to top-level (backward compatible)
		expect(patch.refs?.[0]?.url).toBe("https://legacy.ref/doc1");
		expect(patch.refs?.[0]?.bonus).toBe(true); // User edit preserved
		expect(patch.refs?.[0]?.keyExcerpt).toBe("Updated key"); // User edit preserved
		expect(patch.refs?.[1]?.url).toBe("https://legacy.ref/doc2");
		expect(patch.refs?.[1]?.bonus).toBe(true);

		// Verify refs are ALSO in history[1] for multi-turn compatibility
		const patchHistory = patch.history as ApiItem["history"];
		expect(patchHistory).toBeDefined();
		expect(patchHistory?.[1]?.refs).toBeDefined();
		expect(patchHistory?.[1]?.refs).toHaveLength(2);
	});

	it("save does not include turn refs in top-level for true multi-turn items", async () => {
		// True multi-turn items (created with history) should NOT have turn refs
		// saved to top-level, only to history[].refs
		const apiItem = makeApiItem({
			history: [
				{ role: "user", msg: "Question" },
				{
					role: "assistant",
					msg: "Answer",
					refs: [
						{
							url: "https://turn.ref",
							content: "Turn content",
							bonus: false,
						},
					],
				},
			],
			refs: [], // No top-level refs
		});

		let capturedPatch: Patch | undefined;
		mockUpdateAssignedGroundTruth.mockImplementation(
			async (_dataset: string, _bucket: string, _id: string, patch: Patch) => {
				capturedPatch = patch;
				return apiItem;
			},
		);

		mockGetMyAssignments.mockResolvedValue([apiItem]);
		const provider = new ApiProvider();
		const { items } = await provider.list();

		// Save the item unchanged
		await provider.save(items[0]);

		expect(capturedPatch).toBeDefined();
		const patch = capturedPatch as Patch;

		// Top-level refs should be empty
		expect(patch.refs).toHaveLength(0);

		// Refs should be in history[1]
		const patchHistory = patch.history as ApiItem["history"];
		expect(patchHistory?.[1]?.refs).toHaveLength(1);
		expect(patchHistory?.[1]?.refs?.[0]?.url).toBe("https://turn.ref");
	});
});
