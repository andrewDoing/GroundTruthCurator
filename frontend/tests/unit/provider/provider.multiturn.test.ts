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
	turnId?: string;
	stepId?: string;
};
type ApiItem = Omit<
	components["schemas"]["AgenticGroundTruthEntry-Output"],
	"history"
> & {
	tags?: string[];
	comment?: string | null;
	history?: ApiHistoryEntry[];
};

type Patch = Partial<ApiItem>;

function makeApiItem(overrides: Partial<ApiItem> = {}): ApiItem {
	return {
		id: "gt-1",
		status: "draft",
		history: [],
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
				role: "assistant",
				content: "Use the regenerate command.",
			});
			expect(history[0]?.turnId).toBeTruthy();
			expect(history[1]?.turnId).toBeTruthy();
		});

		it("ignores retired history refs payloads on read", async () => {
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
			expect(getItemReferences(items[0])).toEqual([]);
		});
	});

	describe("retired compat read behavior", () => {
		it("does not synthesize history from retired compat question/answer fields", async () => {
			const apiItem = makeApiItem({
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
			expect(items[0].history).toBeUndefined();
		});

		it("does not import retired compat refs into canonical references", async () => {
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
			expect(getItemReferences(items[0])).toEqual([]);
		});
	});
});

describe("ApiProvider serialization", () => {
	describe("core-generic multi-turn writes", () => {
		it("serializes history roles and omits retired history refs", async () => {
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
			expect(patchHistory?.[1]?.role).toBe("agent");
			expect(patchHistory?.[0]?.refs).toBeUndefined();
			expect(patchHistory?.[1]?.refs).toBeUndefined();
			expect((patch as Record<string, unknown>).refs).toBeUndefined();
		});
	});

	describe("canonical write projections", () => {
		it("persists canonical plugin references without history refs emission", async () => {
			const apiItem = makeApiItem({
				history: [
					{ role: "user", msg: "Q", turnId: "t-user" },
					{ role: "assistant", msg: "A", turnId: "t-agent" },
				],
				...withCompatData({
					references: [
						{
							url: "https://canonical.ref/doc1",
							content: "Canonical content",
							messageIndex: 1,
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
						plugins: (patch.plugins as ApiItem["plugins"]) ?? apiItem.plugins,
						status: (patch.status as ApiItem["status"]) ?? apiItem.status,
					} as ApiItem;
				},
			);
			mockGetMyAssignments.mockResolvedValue([apiItem]);
			const provider = new ApiProvider();
			const { items } = await provider.list();
			const existingRefs = getItemReferences(items[0]);
			const updated: GroundTruthItem = withUpdatedReferences(
				items[0],
				existingRefs.map((ref) =>
					ref.url === "https://canonical.ref/doc1"
						? { ...ref, bonus: true, keyParagraph: "Updated key" }
						: ref,
				),
			);
			await provider.save(updated);
			const patch = capturedPatch as Patch;
			const patchHistory = patch.history as ApiItem["history"];
			expect((patch as Record<string, unknown>).refs).toBeUndefined();
			expect(patchHistory?.[1]?.refs).toBeUndefined();
			expect(
				(patch.plugins?.["rag-compat"]?.data as { references?: unknown })
					.references,
			).toBeDefined();
		});
	});
});
