import { act, renderHook, waitFor } from "@testing-library/react";
import { getItemReferences } from "../../../src/models/groundTruth";

// Force API mode (not demo) so we exercise ApiProvider code path
vi.mock("../../../src/config/demo", () => ({
	default: false,
	DEMO_MODE: false,
	shouldUseDemoProvider: () => false,
	isDemoModeIgnored: () => false,
}));

const runtimeConfigFixture = {
	requireReferenceVisit: true,
	requireKeyParagraph: false,
	selfServeLimit: 10,
};

vi.mock("../../../src/services/runtimeConfig", async (importOriginal) => {
	const actual =
		await importOriginal<
			typeof import("../../../src/services/runtimeConfig")
		>();
	return {
		...actual,
		getRuntimeConfig: vi.fn().mockResolvedValue(runtimeConfigFixture),
		getCachedConfig: vi.fn(() => runtimeConfigFixture),
		clearConfigCache: vi.fn(() => {}),
	};
});

// Mock assignments + groundTruth services used by ApiProvider
const initialApiItem = {
	id: "api-1",
	editedQuestion: "What is test question?",
	synthQuestion: null,
	answer: "original answer",
	comment: null,
	refs: [],
	history: [
		{
			role: "user",
			msg: "What is test question?",
			turnId: "turn-user-1",
			stepId: "step-user-1",
		},
		{
			role: "assistant",
			msg: "original answer",
			turnId: "turn-agent-1",
			stepId: "step-agent-1",
		},
		{
			role: "user",
			msg: "What about the duplicate URL case?",
			turnId: "turn-user-2",
			stepId: "step-user-2",
		},
		{
			role: "assistant",
			msg: "follow-up answer",
			turnId: "turn-agent-2",
			stepId: "step-agent-2",
		},
	],
	toolCalls: [
		{
			id: "tool-call-search",
			name: "search",
			callType: "tool",
		},
		{
			id: "tool-call-browser",
			name: "browser.open",
			callType: "tool",
		},
	],
	plugins: {
		"rag-compat": {
			kind: "rag-compat",
			version: "1.0",
			data: {
				turnIdentity: [
					{ turnId: "turn-user-1", stepId: "step-user-1" },
					{ turnId: "turn-agent-1", stepId: "step-agent-1" },
					{ turnId: "turn-user-2", stepId: "step-user-2" },
					{ turnId: "turn-agent-2", stepId: "step-agent-2" },
				],
				retrievals: {
					"tool-call-search": {
						candidates: [
							{
								url: "https://example.com/doc1",
								title: "Doc one",
								chunk: "Snippet one",
								toolCallId: "tool-call-search",
								turnId: "turn-agent-1",
								bonus: false,
							},
						],
					},
					"tool-call-browser": {
						candidates: [
							{
								url: "https://example.com/doc1",
								title: "Doc one follow-up",
								chunk: "Snippet duplicate",
								toolCallId: "tool-call-browser",
								turnId: "turn-agent-2",
								bonus: false,
							},
						],
					},
				},
			},
		},
	},
	status: "draft",
	tags: ["t1"],
	contextEntries: undefined,
	expectedTools: undefined,
	datasetName: "ds",
	bucket: "0",
	_etag: "etag1",
};

function stripVisitedAtFromPlugins(plugins: unknown): unknown {
	if (!plugins || typeof plugins !== "object") {
		return plugins;
	}
	const nextPlugins = structuredClone(plugins) as Record<string, unknown>;
	const ragCompat = nextPlugins["rag-compat"];
	if (!ragCompat || typeof ragCompat !== "object") {
		return nextPlugins;
	}
	const ragCompatRecord = ragCompat as {
		data?: { retrievals?: Record<string, { candidates?: unknown[] }> };
	};
	const retrievals = ragCompatRecord.data?.retrievals;
	if (!retrievals) {
		return nextPlugins;
	}
	for (const bucket of Object.values(retrievals)) {
		if (!Array.isArray(bucket?.candidates)) continue;
		bucket.candidates = bucket.candidates.map((candidate) => {
			if (!candidate || typeof candidate !== "object") return candidate;
			const { visitedAt: _visitedAt, ...rest } = candidate as Record<
				string,
				unknown
			>;
			return rest;
		});
	}
	return nextPlugins;
}

const getMyAssignmentsMock = vi.fn().mockResolvedValue([initialApiItem]);
const updateAssignedGroundTruthMock = vi
	.fn()
	.mockImplementation(
		(
			_dataset: string,
			_bucket: string,
			id: string,
			patch: Record<string, unknown>,
		) => {
			// Simulate backend dropping visitedAt (never stores it) by rebuilding refs from patch only
			type RefPatch = {
				url: string;
				content?: string | null;
				keyExcerpt?: string | null;
				bonus?: boolean;
			};
			const refsFromTopLevel: RefPatch[] = Array.isArray(patch.refs)
				? (patch.refs as unknown[]).filter((r): r is RefPatch => {
						if (typeof r !== "object" || r === null) return false;
						const candidate = r as { url?: unknown };
						return typeof candidate.url === "string";
					})
				: [];
			const refsFromHistory: RefPatch[] = Array.isArray(patch.history)
				? (patch.history as unknown[]).flatMap((turn) => {
						if (typeof turn !== "object" || turn === null) return [];
						const refs = (turn as { refs?: unknown }).refs;
						if (!Array.isArray(refs)) return [];
						return refs.filter((r): r is RefPatch => {
							if (typeof r !== "object" || r === null) return false;
							const candidate = r as { url?: unknown };
							return typeof candidate.url === "string";
						});
					})
				: [];
			const refsPatch = [...refsFromTopLevel, ...refsFromHistory];
			const normalizedRefs = (
				refsPatch.length ? refsPatch : initialApiItem.refs
			).map((r) => ({
				url: r.url,
				content: r.content ?? null,
				keyExcerpt: r.keyExcerpt ?? null,
				bonus: r.bonus ?? false,
			}));
			return {
				...initialApiItem,
				id,
				editedQuestion: patch.editedQuestion || initialApiItem.editedQuestion,
				answer: patch.answer || initialApiItem.answer,
				history:
					Array.isArray(patch.history) && patch.history.length > 0
						? patch.history
						: initialApiItem.history,
				toolCalls:
					Array.isArray(patch.toolCalls) && patch.toolCalls.length > 0
						? patch.toolCalls
						: initialApiItem.toolCalls,
				contextEntries: Array.isArray(patch.contextEntries)
					? patch.contextEntries
					: initialApiItem.contextEntries,
				expectedTools:
					patch.expectedTools && typeof patch.expectedTools === "object"
						? patch.expectedTools
						: initialApiItem.expectedTools,
				plugins:
					patch.plugins !== undefined
						? stripVisitedAtFromPlugins(patch.plugins)
						: initialApiItem.plugins,
				status:
					(typeof patch.status === "string"
						? patch.status
						: initialApiItem.status) || "draft",
				refs: normalizedRefs,
				_etag: "etag2",
			};
		},
	);

vi.mock("../../../src/services/assignments", () => ({
	getMyAssignments: getMyAssignmentsMock,
	updateAssignedGroundTruth: updateAssignedGroundTruthMock,
	duplicateItem: vi.fn(),
}));

vi.mock("../../../src/services/groundTruths", () => ({
	deleteGroundTruth: vi.fn(),
	getGroundTruth: vi.fn(),
	getGroundTruthRaw: vi.fn(),
}));

let useGroundTruth: typeof import("../../../src/hooks/useGroundTruth").default;
beforeAll(async () => {
	vi.resetModules();
	({ default: useGroundTruth } = await import(
		"../../../src/hooks/useGroundTruth"
	));
});

describe("useGroundTruth visitedAt persistence on save (SA-232)", () => {
	beforeEach(() => {
		updateAssignedGroundTruthMock.mockClear();
	});

	it("preserves visitedAt after saving draft with answer change", async () => {
		const { result } = renderHook(() => useGroundTruth());
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});
		const current = result.current.current;
		expect(current).toBeTruthy();
		if (!current) {
			throw new Error("Expected current item");
		}
		const currentRefs = getItemReferences(current);
		if (!currentRefs[0]) {
			throw new Error("Expected at least one reference");
		}
		const ref = currentRefs[0];
		expect(ref.visitedAt).toBeFalsy();

		// Mark visited via openReference
		await act(async () => {
			result.current.openReference(ref);
		});
		const afterOpenCurrent = result.current.current;
		expect(afterOpenCurrent).toBeTruthy();
		if (!afterOpenCurrent) {
			throw new Error("Expected current item after opening reference");
		}
		const afterOpenVisitedAt =
			getItemReferences(afterOpenCurrent)[0]?.visitedAt;
		expect(afterOpenVisitedAt).toBeTruthy();

		// Change answer so save is not a no-op
		await act(async () => {
			result.current.updateAnswer("updated answer");
		});

		// Save
		await act(async () => {
			const res = await result.current.save();
			expect(res.ok).toBe(true);
		});

		// visitedAt should still be present
		const afterSaveCurrent = result.current.current;
		expect(afterSaveCurrent).toBeTruthy();
		if (!afterSaveCurrent) {
			throw new Error("Expected current item after save");
		}
		const afterSaveVisitedAt =
			getItemReferences(afterSaveCurrent)[0]?.visitedAt;
		expect(afterSaveVisitedAt).toBeTruthy();
		// It should be exactly the same timestamp (we merge, not overwrite)
		expect(afterSaveVisitedAt).toBe(afterOpenVisitedAt);
	});

	it("preserves distinct visitedAt values for duplicate URLs with different turn and tool ownership", async () => {
		const { result } = renderHook(() => useGroundTruth());
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const current = result.current.current;
		expect(current).toBeTruthy();
		if (!current) {
			throw new Error("Expected current item");
		}

		const duplicateUrlRefs = getItemReferences(current).filter(
			(ref) => ref.url === "https://example.com/doc1",
		);
		expect(duplicateUrlRefs).toHaveLength(2);

		await act(async () => {
			result.current.updateReference(duplicateUrlRefs[0].id, {
				visitedAt: "2026-03-13T10:00:00.000Z",
			});
			result.current.updateReference(duplicateUrlRefs[1].id, {
				visitedAt: "2026-03-13T10:05:00.000Z",
			});
			result.current.updateAnswer("updated answer for duplicate URL merge");
		});

		await act(async () => {
			const saveResult = await result.current.save();
			expect(saveResult.ok).toBe(true);
		});

		const afterSaveCurrent = result.current.current;
		expect(afterSaveCurrent).toBeTruthy();
		if (!afterSaveCurrent) {
			throw new Error("Expected current item after save");
		}

		const afterSaveRefs = getItemReferences(afterSaveCurrent).filter(
			(ref) => ref.url === "https://example.com/doc1",
		);
		expect(afterSaveRefs).toHaveLength(2);
		expect(
			afterSaveRefs.find((ref) => ref.toolCallId === "tool-call-search")
				?.visitedAt,
		).toBe("2026-03-13T10:00:00.000Z");
		expect(
			afterSaveRefs.find((ref) => ref.toolCallId === "tool-call-browser")
				?.visitedAt,
		).toBe("2026-03-13T10:05:00.000Z");
	});

	it("keeps same-owner duplicate URL chunks distinct and restores each visitedAt after save", async () => {
		const { result } = renderHook(() => useGroundTruth());
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});

		const current = result.current.current;
		expect(current).toBeTruthy();
		if (!current) {
			throw new Error("Expected current item");
		}

		const baseRef = getItemReferences(current).find(
			(ref) =>
				ref.url === "https://example.com/doc1" &&
				ref.toolCallId === "tool-call-search" &&
				ref.turnId === "turn-agent-1",
		);
		expect(baseRef).toBeTruthy();
		if (!baseRef) {
			throw new Error("Expected baseline reference");
		}

		await act(async () => {
			result.current.addReferences([
				{
					...baseRef,
					id: "ref-same-owner-second-chunk",
					snippet: "Snippet one - second chunk",
					keyParagraph: "Second chunk paragraph",
					visitedAt: null,
				},
			]);
		});

		const afterAddCurrent = result.current.current;
		expect(afterAddCurrent).toBeTruthy();
		if (!afterAddCurrent) {
			throw new Error("Expected current item after adding duplicate chunk");
		}

		const sameOwnerRefs = getItemReferences(afterAddCurrent).filter(
			(ref) =>
				ref.url === "https://example.com/doc1" &&
				ref.toolCallId === "tool-call-search" &&
				ref.turnId === "turn-agent-1",
		);
		expect(sameOwnerRefs).toHaveLength(2);

		const firstChunk = sameOwnerRefs.find(
			(ref) => ref.snippet === "Snippet one",
		);
		const secondChunk = sameOwnerRefs.find(
			(ref) => ref.snippet === "Snippet one - second chunk",
		);
		expect(firstChunk).toBeTruthy();
		expect(secondChunk).toBeTruthy();
		if (!firstChunk || !secondChunk) {
			throw new Error("Expected both same-owner chunks");
		}

		await act(async () => {
			result.current.updateReference(firstChunk.id, {
				visitedAt: "2026-03-13T11:00:00.000Z",
			});
			result.current.updateReference(secondChunk.id, {
				visitedAt: "2026-03-13T11:05:00.000Z",
			});
			result.current.updateAnswer(
				"updated answer for same-owner duplicate chunk",
			);
		});

		await act(async () => {
			const saveResult = await result.current.save();
			expect(saveResult.ok).toBe(true);
		});

		const afterSaveCurrent = result.current.current;
		expect(afterSaveCurrent).toBeTruthy();
		if (!afterSaveCurrent) {
			throw new Error("Expected current item after save");
		}

		const afterSaveRefs = getItemReferences(afterSaveCurrent).filter(
			(ref) =>
				ref.url === "https://example.com/doc1" &&
				ref.toolCallId === "tool-call-search" &&
				ref.turnId === "turn-agent-1",
		);
		expect(afterSaveRefs).toHaveLength(2);
		expect(
			afterSaveRefs.find((ref) => ref.snippet === "Snippet one")?.visitedAt,
		).toBe("2026-03-13T11:00:00.000Z");
		expect(
			afterSaveRefs.find((ref) => ref.snippet === "Snippet one - second chunk")
				?.visitedAt,
		).toBe("2026-03-13T11:05:00.000Z");
	});
});
