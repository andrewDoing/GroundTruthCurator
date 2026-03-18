import { describe, expect, it } from "vitest";
import type {
	ApiGroundTruth,
	ApiReference,
} from "../../../src/adapters/apiMapper";
import { groundTruthFromApi } from "../../../src/adapters/apiMapper";
import type { components } from "../../../src/api/generated";
import { getItemReferences } from "../../../src/models/groundTruth";
import { mapGroundTruthFromApi } from "../../../src/services/groundTruths";

type ApiItem = Omit<
	components["schemas"]["AgenticGroundTruthEntry-Output"],
	"history"
> & {
	tags?: string[];
	comment?: string | null;
	history?: (components["schemas"]["HistoryEntry"] & {
		refs?: ApiReference[];
		expectedBehavior?: string[];
	})[];
};

function makeApiItem(overrides: Partial<ApiItem> = {}): ApiItem {
	return {
		id: "gt-1",
		status: "draft",
		history: undefined,
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

describe("mapGroundTruthFromApi", () => {
	describe("core-generic mapping", () => {
		it("preserves assistant role values and keeps stable turn ids", () => {
			const apiItem = makeApiItem({
				history: [
					{ role: "user", msg: "Question" },
					{ role: "assistant", msg: "Answer" },
				],
			});
			const result = mapGroundTruthFromApi(apiItem);
			expect(result.history?.[0]).toMatchObject({
				role: "user",
				content: "Question",
			});
			expect(result.history?.[1]).toMatchObject({
				role: "assistant",
				content: "Answer",
			});
			expect(result.history?.[0].turnId).toBeTruthy();
			expect(result.history?.[1].turnId).toBeTruthy();
		});

		it("ignores retired per-turn history refs", () => {
			const apiItem = makeApiItem({
				history: [
					{ role: "user", msg: "Q1" },
					{
						role: "assistant",
						msg: "A1",
						refs: [
							{
								url: "https://turn-ref.com",
								content: "turn content",
								bonus: false,
							},
						],
					},
				],
			});
			const result = mapGroundTruthFromApi(apiItem);
			expect(getItemReferences(result)).toEqual([]);
		});
	});

	describe("retired compat read mapping", () => {
		it("does not synthesize history from retired single-turn fields", () => {
			const apiItem = makeApiItem({
				history: undefined,
				...withCompatData({
					synthQuestion: "Synth",
					editedQuestion: "Edited",
					answer: "A",
				}),
			});
			const result = mapGroundTruthFromApi(apiItem);
			expect(result.history).toBeUndefined();
		});

		it("does not import retired compat refs", () => {
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
			const result = mapGroundTruthFromApi(apiItem);
			expect(getItemReferences(result)).toEqual([]);
		});
	});

	describe("providerId", () => {
		it("defaults to 'api' when not provided", () => {
			const result = mapGroundTruthFromApi(makeApiItem());
			expect(result.providerId).toBe("api");
		});

		it("uses provided providerId", () => {
			const result = mapGroundTruthFromApi(makeApiItem(), "custom-provider");
			expect(result.providerId).toBe("custom-provider");
		});
	});
});

describe("mapper parity: groundTruthFromApi and mapGroundTruthFromApi", () => {
	function normalizeTurnIdentity(item: ReturnType<typeof groundTruthFromApi>) {
		const normalizedPlugins = item.plugins
			? Object.fromEntries(
					Object.entries(item.plugins).map(([slot, payload]) => [
						slot,
						slot === "rag-compat" && payload.data?.retrievals
							? {
									...payload,
									data: {
										...payload.data,
										retrievals: Object.fromEntries(
											Object.entries(
												payload.data.retrievals as Record<
													string,
													{ candidates?: Array<Record<string, unknown>> }
												>,
											).map(([key, bucket]) => [
												key,
												{
													...bucket,
													candidates: (bucket.candidates ?? []).map(
														(candidate) => ({
															...candidate,
															turnId: candidate.turnId
																? "<normalized>"
																: undefined,
														}),
													),
												},
											]),
										),
									},
								}
							: payload,
					]),
				)
			: item.plugins;
		return {
			...item,
			history: item.history?.map((turn) => ({
				...turn,
				turnId: "<normalized>",
				stepId: "<normalized>",
			})),
			plugins: normalizedPlugins,
		};
	}

	function makeSharedPayload(
		overrides: Partial<ApiGroundTruth> = {},
	): ApiGroundTruth {
		return {
			id: "parity-1",
			status: "draft",
			history: undefined,
			tags: ["t1"],
			manualTags: ["m1"],
			computedTags: ["c1"],
			comment: "a comment",
			datasetName: "ds",
			bucket: "bkt" as ApiGroundTruth["bucket"],
			_etag: "etag-parity",
			reviewedAt: "2024-01-01T00:00:00Z",
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						references: [],
					},
				},
			},
			...overrides,
		} as ApiGroundTruth;
	}

	it("produces identical output for a canonical payload", () => {
		const payload = makeSharedPayload();
		const fromProvider = groundTruthFromApi(payload);
		const fromService = mapGroundTruthFromApi(payload);
		expect(normalizeTurnIdentity(fromProvider)).toEqual(
			normalizeTurnIdentity(fromService),
		);
	});

	it("produces identical output for a multi-turn payload with retired per-turn refs", () => {
		const payload = makeSharedPayload({
			history: [
				{ role: "user", msg: "First question" },
				{
					role: "assistant",
					msg: "First answer",
					refs: [{ url: "https://ref1.com", content: "Ref 1", bonus: false }],
				},
				{ role: "user", msg: "Follow-up" },
				{
					role: "assistant",
					msg: "Follow-up answer",
					refs: [{ url: "https://ref2.com", content: "Ref 2", bonus: true }],
				},
			],
		});
		const fromProvider = groundTruthFromApi(payload);
		const fromService = mapGroundTruthFromApi(payload);
		expect(normalizeTurnIdentity(fromProvider)).toEqual(
			normalizeTurnIdentity(fromService),
		);
		expect(getItemReferences(fromProvider)).toHaveLength(0);
	});

	it("preserves reviewedAt through both paths identically", () => {
		const payload = makeSharedPayload({ reviewedAt: "2025-06-01T12:00:00Z" });
		const fromProvider = groundTruthFromApi(payload);
		const fromService = mapGroundTruthFromApi(payload);
		expect(fromProvider.reviewedAt).toBe("2025-06-01T12:00:00Z");
		expect(fromService.reviewedAt).toBe("2025-06-01T12:00:00Z");
		expect(normalizeTurnIdentity(fromProvider)).toEqual(
			normalizeTurnIdentity(fromService),
		);
	});
});
