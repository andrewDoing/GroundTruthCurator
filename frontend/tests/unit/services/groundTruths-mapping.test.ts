import { describe, expect, it } from "vitest";
import type { ApiGroundTruth } from "../../../src/adapters/apiMapper";
import { groundTruthFromApi } from "../../../src/adapters/apiMapper";
import type { components } from "../../../src/api/generated";
import { getItemReferences } from "../../../src/models/groundTruth";
import { mapGroundTruthFromApi } from "../../../src/services/groundTruths";

type ApiItem = Omit<
	components["schemas"]["AgenticGroundTruthEntry-Output"],
	"history"
> & {
	synthQuestion?: string | null;
	editedQuestion?: string | null;
	answer?: string | null;
	refs?: components["schemas"]["Reference"][];
	totalReferences?: number;
	tags?: string[];
	comment?: string | null;
	history?: (components["schemas"]["HistoryEntry"] & {
		refs?: components["schemas"]["Reference"][];
		expectedBehavior?: string[];
	})[];
};

function makeApiItem(overrides: Partial<ApiItem> = {}): ApiItem {
	return {
		id: "gt-1",
		status: "draft",
		answer: "",
		synthQuestion: "",
		editedQuestion: "",
		history: undefined,
		refs: [],
		tags: [],
		comment: null,
		datasetName: "dataset-1",
		bucket: "bucket-1" as ApiItem["bucket"],
		_etag: "etag-1",
		...overrides,
	} as ApiItem;
}

describe("mapGroundTruthFromApi", () => {
	describe("core-generic mapping", () => {
		it("converts assistant role to agent and keeps stable turn ids", () => {
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
				role: "agent",
				content: "Answer",
			});
			expect(result.history?.[0].turnId).toBeTruthy();
			expect(result.history?.[1].turnId).toBeTruthy();
		});

		it("preserves per-turn refs when canonical history already exists", () => {
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
			const [ref] = getItemReferences(result);
			expect(ref).toMatchObject({
				url: "https://turn-ref.com",
				messageIndex: 1,
				turnId: result.history?.[1]?.turnId,
			});
		});
	});

	describe("compat-migration read mapping", () => {
		it("creates synthesized user and agent turns from legacy single-turn fields", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Synth",
				editedQuestion: "Edited",
				answer: "A",
				history: undefined,
			});
			const result = mapGroundTruthFromApi(apiItem);
			expect(result.history).toHaveLength(2);
			expect(result.history?.[0]).toMatchObject({
				role: "user",
				content: "Edited",
			});
			expect(result.history?.[1]).toMatchObject({
				role: "agent",
				content: "A",
			});
		});

		it("anchors legacy top-level refs to the synthesized agent turn when answer is empty", () => {
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
				],
				history: undefined,
			});
			const result = mapGroundTruthFromApi(apiItem);
			const [ref] = getItemReferences(result);
			expect(result.history).toHaveLength(2);
			expect(result.history?.[1]).toMatchObject({ role: "agent", content: "" });
			expect(ref).toMatchObject({
				url: "https://docs.example.com/auth",
				messageIndex: 1,
				turnId: result.history?.[1]?.turnId,
			});
		});
	});

	describe("providerId", () => {
		it("defaults to 'api' when not provided", () => {
			const result = mapGroundTruthFromApi(makeApiItem({ synthQuestion: "Q" }));
			expect(result.providerId).toBe("api");
		});

		it("uses provided providerId", () => {
			const result = mapGroundTruthFromApi(
				makeApiItem({ synthQuestion: "Q" }),
				"custom-provider",
			);
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
			answer: "Parity answer",
			synthQuestion: "Synth parity Q",
			editedQuestion: "Edited parity Q",
			history: undefined,
			refs: [],
			tags: ["t1"],
			manualTags: ["m1"],
			computedTags: ["c1"],
			comment: "a comment",
			datasetName: "ds",
			bucket: "bkt" as ApiGroundTruth["bucket"],
			_etag: "etag-parity",
			reviewedAt: "2024-01-01T00:00:00Z",
			...overrides,
		} as ApiGroundTruth;
	}

	it("produces identical output for a legacy single-turn payload", () => {
		const payload = makeSharedPayload();
		const fromProvider = groundTruthFromApi(payload);
		const fromService = mapGroundTruthFromApi(payload);
		expect(normalizeTurnIdentity(fromProvider)).toEqual(
			normalizeTurnIdentity(fromService),
		);
	});

	it("produces identical output for a multi-turn payload with per-turn refs", () => {
		const payload = makeSharedPayload({
			editedQuestion: "",
			synthQuestion: "",
			answer: "",
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
		expect(getItemReferences(fromProvider)).toHaveLength(2);
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
