import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiReference } from "../../../src/adapters/apiMapper";
import { ApiProvider } from "../../../src/adapters/apiProvider";
import type { components } from "../../../src/api/generated";
import type {
	GroundTruthItem,
	Reference,
} from "../../../src/models/groundTruth";
import {
	getItemReferences,
	withUpdatedReferences,
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

type ApiHistoryEntry = components["schemas"]["HistoryEntry"] & {
	refs?: ApiReference[];
	expectedBehavior?: string[];
};
type ApiItem = Omit<
	components["schemas"]["AgenticGroundTruthEntry-Output"],
	"history"
> & {
	synthQuestion?: string | null;
	editedQuestion?: string | null;
	answer?: string | null;
	refs?: ApiReference[];
	totalReferences?: number;
	tags?: string[];
	comment?: string | null;
	history?: ApiHistoryEntry[];
};

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

function withCompatData(
	data: Record<string, unknown>,
): Pick<ApiItem, "plugins"> {
	return {
		plugins: {
			"rag-compat": {
				kind: "rag-compat",
				version: "1.0",
				data,
			},
		},
	};
}

beforeEach(() => {
	mockGetMyAssignments.mockReset();
	mockUpdateAssignedGroundTruth.mockReset();
	mockDeleteGroundTruth.mockReset();
	mockGetGroundTruth.mockReset();
});

describe("ApiProvider mapping", () => {
	describe("core-generic multi-turn contracts", () => {
		it("maps history roles, content, and stable turn identity", async () => {
			const apiItem = makeApiItem({
				history: [
					{ role: "user", msg: "How do I?" },
					{ role: "assistant", msg: "Use the regenerate command." },
				],
			});
			mockGetMyAssignments.mockResolvedValue([apiItem]);
			const provider = new ApiProvider();
			const { items } = await provider.list();
			const history = items[0].history ?? [];
			expect(history).toHaveLength(2);
			expect(history[0]).toMatchObject({ role: "user", content: "How do I?" });
			expect(history[1]).toMatchObject({
				role: "agent",
				content: "Use the regenerate command.",
			});
			expect(history[0]?.turnId).toBeTruthy();
			expect(history[1]?.turnId).toBeTruthy();
		});

		it("maps per-turn refs onto the owning non-user turn", async () => {
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
			const turn = items[0].history?.[1];
			const [ref] = getItemReferences(items[0]);
			expect(ref).toMatchObject({
				url: "https://turn.ref",
				bonus: true,
				messageIndex: 1,
				turnId: turn?.turnId,
			});
		});
	});

	describe("compat-migration read projections", () => {
		it("projects legacy single-turn payloads into stable user and agent turns", async () => {
			const apiItem = makeApiItem({
				tags: ["important", "technical"],
				history: undefined,
				...withCompatData({
					synthQuestion: "What is X?",
					editedQuestion: "What is X exactly?",
					answer: "X is Y",
				}),
			});
			mockGetMyAssignments.mockResolvedValue([apiItem]);
			const provider = new ApiProvider();
			const { items } = await provider.list();
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

		it("anchors legacy top-level refs to the synthesized agent turn even without an answer", async () => {
			const apiItem = makeApiItem({
				history: undefined,
				...withCompatData({
					editedQuestion: "How do I configure authentication for my app?",
					answer: "",
					refs: [
						{
							url: "https://docs.example.com/auth",
							content: "Authentication documentation content",
							keyExcerpt: "Use OAuth 2.0 for authentication",
							bonus: false,
						},
					],
				}),
			});
			mockGetMyAssignments.mockResolvedValue([apiItem]);
			const provider = new ApiProvider();
			const { items } = await provider.list();
			const history = items[0].history ?? [];
			const [ref] = getItemReferences(items[0]);
			expect(history).toHaveLength(2);
			expect(history[0]?.content).toBe(
				"How do I configure authentication for my app?",
			);
			expect(history[1]).toMatchObject({ role: "agent", content: "" });
			expect(ref).toMatchObject({
				url: "https://docs.example.com/auth",
				messageIndex: 1,
				turnId: history[1]?.turnId,
			});
		});
	});
});

describe("ApiProvider serialization", () => {
	describe("core-generic multi-turn writes", () => {
		it("serializes history roles and keeps refs scoped to non-user turns", async () => {
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
				{ role: "user", content: "Updated Q", turnId: "turn-user-updated" },
				{ role: "agent", content: "Updated A", turnId: "turn-agent-updated" },
			];
			const refs: Reference[] = [
				{ id: "global", url: "https://global" },
				{
					id: "turn",
					url: "https://turn",
					turnId: "turn-agent-updated",
				},
				{
					id: "user-ref",
					url: "https://user",
					turnId: "turn-user-updated",
				},
			];
			const updated: GroundTruthItem = withUpdatedReferences(
				{ ...domain, history },
				refs,
			);
			await provider.save(updated);
			expect(capturedPatch).toBeDefined();
			const patch = capturedPatch as Patch;
			const patchHistory = patch.history as ApiItem["history"];
			expect(patchHistory?.[0]?.role).toBe("user");
			expect(patchHistory?.[1]?.role).toBe("assistant");
			expect(patchHistory?.[0]?.refs).toBeUndefined();
			expect(patchHistory?.[1]?.refs).toHaveLength(1);
			expect(patchHistory?.[1]?.refs?.[0]?.url).toBe("https://turn");
		});

		it("keeps true multi-turn refs out of top-level compatibility fields", async () => {
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
				refs: [],
			});
			let capturedPatch: Patch | undefined;
			mockUpdateAssignedGroundTruth.mockImplementation(
				async (
					_dataset: string,
					_bucket: string,
					_id: string,
					patch: Patch,
				) => {
					capturedPatch = patch;
					return apiItem;
				},
			);
			mockGetMyAssignments.mockResolvedValue([apiItem]);
			const provider = new ApiProvider();
			const { items } = await provider.list();
			await provider.save(items[0]);
			const patch = capturedPatch as Patch;
			const patchHistory = patch.history as ApiItem["history"];
			expect(patch.refs).toBeUndefined();
			expect(patchHistory?.[1]?.refs).toHaveLength(1);
			expect(patchHistory?.[1]?.refs?.[0]?.url).toBe("https://turn.ref");
		});
	});

	describe("compat-migration write projections", () => {
		it("preserves legacy top-level refs when saving a synthesized single-turn item", async () => {
			const apiItem = makeApiItem({
				history: undefined,
				...withCompatData({
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
				}),
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
			const legacyRefs = getItemReferences(items[0]);
			const updated: GroundTruthItem = withUpdatedReferences(
				items[0],
				legacyRefs.map((ref) =>
					ref.url === "https://legacy.ref/doc1"
						? { ...ref, bonus: true, keyParagraph: "Updated key" }
						: ref,
				),
			);
			await provider.save(updated);
			const patch = capturedPatch as Patch;
			const patchHistory = patch.history as ApiItem["history"];
			expect(patch.refs).toBeUndefined();
			expect(patchHistory?.[1]?.refs).toHaveLength(2);
		});
	});
});
