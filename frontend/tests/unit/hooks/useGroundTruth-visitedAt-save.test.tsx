import { act, renderHook, waitFor } from "@testing-library/react";

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
	const actual = await importOriginal<
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
	refs: [
		{
			url: "https://example.com/doc1",
			content: "Snippet one",
			keyExcerpt: null,
			bonus: false,
		},
	],
	status: "draft",
	tags: ["t1"],
	datasetName: "ds",
	bucket: "0",
	_etag: "etag1",
};

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
			const normalizedRefs = (refsPatch.length ? refsPatch : initialApiItem.refs).map(
				(r) => ({
					url: r.url,
					content: r.content ?? null,
					keyExcerpt: r.keyExcerpt ?? null,
					bonus: r.bonus ?? false,
				}),
			);
			return {
				...initialApiItem,
				id,
				editedQuestion: patch.editedQuestion || initialApiItem.editedQuestion,
				answer: patch.answer || initialApiItem.answer,
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
}));

let useGroundTruth: typeof import("../../../src/hooks/useGroundTruth").default;
beforeAll(async () => {
	vi.resetModules();
	({ default: useGroundTruth } = await import(
		"../../../src/hooks/useGroundTruth"
	));
});

describe("useGroundTruth visitedAt persistence on save (SA-232)", () => {
	it("preserves visitedAt after saving draft with answer change", async () => {
		const { result } = renderHook(() => useGroundTruth());
		await waitFor(() => {
			expect(result.current.current).toBeTruthy();
		});
		const current = result.current.current;
		expect(current).toBeTruthy();
		if (!current?.references?.[0]) {
			throw new Error("Expected at least one reference");
		}
		const ref = current.references[0];
		expect(ref.visitedAt).toBeFalsy();

		// Mark visited via openReference
		await act(async () => {
			result.current.openReference(ref);
		});
		const afterOpenVisitedAt =
			result.current.current?.references?.[0]?.visitedAt;
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
		const afterSaveVisitedAt =
			result.current.current?.references?.[0]?.visitedAt;
		expect(afterSaveVisitedAt).toBeTruthy();
		// It should be exactly the same timestamp (we merge, not overwrite)
		expect(afterSaveVisitedAt).toBe(afterOpenVisitedAt);
	});
});
