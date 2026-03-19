import { describe, expect, it } from "vitest";
import {
	type ApiGroundTruth,
	groundTruthFromApi,
	groundTruthToPatch,
} from "../../../src/adapters/apiMapper";
import type { GroundTruthItem } from "../../../src/models/groundTruth";
import { getItemReferences } from "../../../src/models/groundTruth";

function makeApiItem(overrides: Partial<ApiGroundTruth> = {}): ApiGroundTruth {
	return {
		id: "gt-1",
		status: "draft",
		history: undefined,
		tags: [],
		manualTags: [],
		computedTags: [],
		comment: null,
		datasetName: "dataset-1",
		bucket: "bucket-1" as ApiGroundTruth["bucket"],
		_etag: "etag-1",
		...overrides,
	} as ApiGroundTruth;
}

function withCompatData(
	data: Record<string, unknown>,
): Pick<ApiGroundTruth, "plugins"> {
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

describe("groundTruthFromApi", () => {
	describe("role mapping", () => {
		it("preserves history role values from the API payload", () => {
			const api = makeApiItem({
				history: [{ role: "assistant", msg: "Hello from assistant" }],
			});
			const result = groundTruthFromApi(api);
			expect(result.history?.[0].role).toBe("assistant");
			expect(result.history?.[0].content).toBe("Hello from assistant");
		});

		it("maps history role 'user' to 'user'", () => {
			const api = makeApiItem({
				history: [{ role: "user", msg: "Hello from user" }],
			});
			const result = groundTruthFromApi(api);
			expect(result.history?.[0].role).toBe("user");
			expect(result.history?.[0].content).toBe("Hello from user");
		});

		it("derives compatibility question from the latest user turn", () => {
			const api = makeApiItem({
				history: [
					{ role: "user", msg: "Initial question" },
					{ role: "planner", msg: "Planner output" },
					{ role: "user", msg: "Follow-up question" },
					{ role: "assistant", msg: "Final answer" },
				],
			});
			const result = groundTruthFromApi(api);
			expect(result.question).toBe("Follow-up question");
		});
	});

	describe("expectedBehavior handling", () => {
		it("preserves non-empty expectedBehavior array", () => {
			const api = makeApiItem({
				history: [
					{
						role: "assistant",
						msg: "Answer",
						expectedBehavior: ["tool:search", "generation:answer"],
					},
				],
			});
			const result = groundTruthFromApi(api);
			expect(result.history?.[0].expectedBehavior).toEqual([
				"tool:search",
				"generation:answer",
			]);
		});

		it("converts empty expectedBehavior to undefined", () => {
			const api = makeApiItem({
				history: [{ role: "assistant", msg: "Answer", expectedBehavior: [] }],
			});
			const result = groundTruthFromApi(api);
			expect(result.history?.[0].expectedBehavior).toBeUndefined();
		});

		it("handles missing expectedBehavior as undefined", () => {
			const api = makeApiItem({
				history: [{ role: "assistant", msg: "Answer" }],
			});
			const result = groundTruthFromApi(api);
			expect(result.history?.[0].expectedBehavior).toBeUndefined();
		});
	});

	describe("reference mapping", () => {
		it("reads canonical rag-compat data.references", () => {
			const api = makeApiItem({
				history: [{ role: "assistant", msg: "A" }],
				...withCompatData({
					references: [
						{
							url: "https://canonical.ref/1",
							title: "Canonical Ref",
							content: "Canonical snippet",
							keyExcerpt: "Canonical key excerpt",
							bonus: true,
							messageIndex: 0,
						},
					],
				}),
			});
			const result = groundTruthFromApi(api);
			const [ref] = getItemReferences(result);
			expect(ref.url).toBe("https://canonical.ref/1");
			expect(ref.title).toBe("Canonical Ref");
			expect(ref.snippet).toBe("Canonical snippet");
			expect(ref.keyParagraph).toBe("Canonical key excerpt");
			expect(ref.bonus).toBe(true);
		});

		it("ignores retired turn-level refs from history payloads", () => {
			const api = makeApiItem({
				history: [
					{ role: "user", msg: "Question" },
					{
						role: "assistant",
						msg: "Answer",
						refs: [
							{ url: "https://ref1.com", content: "Snippet 1", bonus: false },
							{ url: "https://ref2.com", content: "Snippet 2", bonus: false },
						],
					},
					{ role: "user", msg: "Follow-up" },
					{
						role: "assistant",
						msg: "Follow-up answer",
						refs: [
							{ url: "https://ref3.com", content: "Snippet 3", bonus: false },
						],
					},
				],
			});
			const result = groundTruthFromApi(api);

			expect(getItemReferences(result)).toEqual([]);
		});

		it("maps canonical plugin reference fields correctly", () => {
			const api = makeApiItem({
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							references: [
								{
									url: "https://example.com",
									title: "Example Title",
									content: "Snippet content",
									keyExcerpt: "Key paragraph",
									bonus: true,
								},
							],
						},
					},
				},
			});
			const result = groundTruthFromApi(api);
			const ref = getItemReferences(result)[0];

			expect(ref.url).toBe("https://example.com");
			expect(ref.title).toBe("Example Title");
			expect(ref.snippet).toBe("Snippet content");
			expect(ref.keyParagraph).toBe("Key paragraph");
			expect(ref.bonus).toBe(true);
			expect(ref.visitedAt).toBeNull();
			expect(ref.id).toMatch(/^ref_\d+$/);
		});
	});

	describe("retired single-turn compat behavior", () => {
		it("does not synthesize history from editedQuestion and answer", () => {
			const api = makeApiItem({
				history: undefined,
				...withCompatData({
					editedQuestion: "What is X?",
					answer: "X is Y",
				}),
			});
			const result = groundTruthFromApi(api);

			expect(result.history).toBeUndefined();
		});

		it("does not fall back to synthQuestion when editedQuestion is empty", () => {
			const api = makeApiItem({
				history: undefined,
				...withCompatData({
					synthQuestion: "Synth question?",
					editedQuestion: "",
					answer: "Answer",
				}),
			});
			const result = groundTruthFromApi(api);

			expect(result.history).toBeUndefined();
		});

		it("does not import legacy top-level refs", () => {
			const api = makeApiItem({
				history: undefined,
				...withCompatData({
					editedQuestion: "Question",
					answer: "Answer",
					refs: [
						{
							url: "https://legacy.ref",
							content: "Legacy content",
							bonus: false,
						},
					],
				}),
			});
			const result = groundTruthFromApi(api);

			expect(getItemReferences(result)).toEqual([]);
		});

		it("does not create synthetic turns when answer is empty", () => {
			const api = makeApiItem({
				history: undefined,
				...withCompatData({
					editedQuestion: "Question without answer",
					answer: "",
				}),
			});
			const result = groundTruthFromApi(api);

			expect(result.history).toBeUndefined();
		});

		it("treats explicit API empty history as authoritative over compat question/answer", () => {
			const api = makeApiItem({
				history: [],
				...withCompatData({
					editedQuestion: "Compat question",
					answer: "Compat answer",
				}),
			});
			const result = groundTruthFromApi(api);

			expect(result.history).toEqual([]);
		});
	});

	describe("multi-turn item top-level refs", () => {
		it("does not import compat refs for true multi-turn", () => {
			const api = makeApiItem({
				history: [
					{ role: "user", msg: "Q" },
					{ role: "assistant", msg: "A" },
				],
				...withCompatData({
					refs: [
						{
							url: "https://global.ref",
							content: "Global ref",
							bonus: false,
						},
					],
				}),
			});
			const result = groundTruthFromApi(api);

			expect(getItemReferences(result)).toEqual([]);
		});

		it("treats explicit empty canonical references as authoritative", () => {
			const api = makeApiItem({
				history: [{ role: "assistant", msg: "A" }],
				...withCompatData({
					references: [],
					retrievals: {
						_unassociated: {
							candidates: [{ url: "https://stale.ref", messageIndex: 0 }],
						},
					},
				}),
			});
			const result = groundTruthFromApi(api);

			expect(getItemReferences(result)).toEqual([]);
		});
	});

	describe("deleted status mapping", () => {
		it("maps status 'deleted' to deleted: true and status: 'draft'", () => {
			const api = makeApiItem({ status: "deleted" });
			const result = groundTruthFromApi(api);

			expect(result.deleted).toBe(true);
			expect(result.status).toBe("draft");
		});

		it("maps non-deleted status correctly", () => {
			const api = makeApiItem({ status: "approved" });
			const result = groundTruthFromApi(api);

			expect(result.deleted).toBe(false);
			expect(result.status).toBe("approved");
		});
	});

	describe("metadata preservation", () => {
		it("preserves datasetName, bucket, and _etag", () => {
			const api = makeApiItem({
				datasetName: "my-dataset",
				bucket: "my-bucket" as ApiGroundTruth["bucket"],
				_etag: "my-etag",
			});
			const result = groundTruthFromApi(api);

			expect((result as Record<string, unknown>).datasetName).toBe(
				"my-dataset",
			);
			expect((result as Record<string, unknown>).bucket).toBe("my-bucket");
			expect((result as Record<string, unknown>)._etag).toBe("my-etag");
		});

		it("sets providerId to 'api'", () => {
			const api = makeApiItem();
			const result = groundTruthFromApi(api);
			expect(result.providerId).toBe("api");
		});
	});

	describe("tag handling", () => {
		it("preserves tags, manualTags, and computedTags", () => {
			const api = makeApiItem({
				tags: ["tag1", "tag2"],
				manualTags: ["manual1"],
				computedTags: ["computed1", "computed2"],
			});
			const result = groundTruthFromApi(api);

			expect(result.tags).toEqual(["tag1", "tag2"]);
			expect(result.manualTags).toEqual(["manual1"]);
			expect(result.computedTags).toEqual(["computed1", "computed2"]);
		});

		it("defaults missing tag arrays to empty", () => {
			const api = makeApiItem({
				tags: undefined,
				manualTags: undefined,
				computedTags: undefined,
			});
			const result = groundTruthFromApi(api);

			expect(result.tags).toEqual([]);
			expect(result.manualTags).toEqual([]);
			expect(result.computedTags).toEqual([]);
		});
	});

	describe("tool call handling", () => {
		it("normalizes null tool call arguments to undefined", () => {
			const api = makeApiItem({
				toolCalls: [
					{
						id: "tc-1",
						name: "search_docs",
						callType: "tool",
						arguments: null,
					},
				],
			});
			const result = groundTruthFromApi(api);

			expect(result.toolCalls).toHaveLength(1);
			expect(result.toolCalls?.[0]).toMatchObject({
				id: "tc-1",
				name: "search_docs",
				callType: "tool",
			});
			expect(result.toolCalls?.[0].arguments).toBeUndefined();
		});
	});

	describe("contextEntries handling", () => {
		it("preserves explicit empty contextEntries arrays", () => {
			const api = makeApiItem({ contextEntries: [] });
			const result = groundTruthFromApi(api);

			expect(result.contextEntries).toEqual([]);
		});
	});
});

describe("groundTruthToPatch", () => {
	function makeDomainItem(
		overrides: Partial<GroundTruthItem> = {},
	): GroundTruthItem {
		return {
			id: "gt-1",
			providerId: "api",
			question: "Test question",
			history: [{ role: "agent", content: "Test answer" }],
			status: "draft",
			deleted: false,
			tags: [],
			manualTags: [],
			...overrides,
		};
	}

	describe("role mapping", () => {
		it("preserves UI role values when serializing patch payloads", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
			});
			const patch = groundTruthToPatch({ item });

			expect(patch.history?.[0].role).toBe("user");
			expect(patch.history?.[1].role).toBe("agent");
		});
	});

	describe("reference handling", () => {
		it("does not create rag-compat plugin when history exists without compat payload", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					other: {
						kind: "other",
						version: "1.0",
						data: { keep: true },
					},
				},
			});
			const patch = groundTruthToPatch({ item });
			const patchPlugins = (patch as Record<string, unknown>).plugins as
				| Record<string, { data?: Record<string, unknown> }>
				| undefined;
			expect(patchPlugins?.other?.data).toEqual({ keep: true });
			expect(patchPlugins?.["rag-compat"]).toBeUndefined();
		});

		it("round-trips canonical rag-compat data.references through patch generation", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							references: [
								{
									url: "https://canonical.roundtrip/ref",
									title: "Round Trip Ref",
									content: "Round trip snippet",
									keyExcerpt: "Round trip excerpt",
									messageIndex: 1,
								},
							],
						},
					},
				},
			});

			const patch = groundTruthToPatch({ item });
			expect(patch.history?.[1].refs).toBeUndefined();
			const patchPlugins = (patch as Record<string, unknown>).plugins as
				| Record<string, { data?: Record<string, unknown> }>
				| undefined;
			expect(patchPlugins?.["rag-compat"]?.data?.references).toEqual([
				expect.objectContaining({
					url: "https://canonical.roundtrip/ref",
					title: "Round Trip Ref",
				}),
			]);
		});

		it("materializes retrieval-only rag-compat payloads into canonical references during save patch", () => {
			const fromApi = groundTruthFromApi(
				makeApiItem({
					history: [
						{ role: "user", msg: "Q", turnId: "turn-user" },
						{ role: "assistant", msg: "A", turnId: "turn-answer" },
					],
					...withCompatData({
						retrievals: {
							tc1: {
								candidates: [
									{
										url: "https://retrieval.only/ref",
										title: "Retrieval Only Ref",
										chunk: "retrieval snippet",
										messageIndex: 1,
									},
								],
							},
						},
					}),
				}),
			);

			const patch = groundTruthToPatch({ item: fromApi });
			const patchPlugins = (patch as Record<string, unknown>).plugins as
				| Record<string, { data?: Record<string, unknown> }>
				| undefined;

			expect(patchPlugins?.["rag-compat"]?.data?.references).toEqual([
				expect.objectContaining({
					url: "https://retrieval.only/ref",
					title: "Retrieval Only Ref",
					toolCallId: "tc1",
					turnId: "turn-answer",
				}),
			]);
			expect(patchPlugins?.["rag-compat"]?.data?.retrievals).toBeUndefined();
		});

		it("scrubs removed legacy compat keys and deprecated compat retrievals", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							synthQuestion: "legacy question",
							editedQuestion: "legacy edited",
							answer: "legacy answer",
							refs: [{ url: "https://legacy.ref" }],
							totalReferences: 99,
							historyAnnotations: [{ note: "legacy" }],
							references: [{ url: "https://canonical.ref" }],
							retrievals: {
								_unassociated: {
									candidates: [{ url: "https://retrieval.ref" }],
								},
							},
						},
					},
				},
			});

			const patch = groundTruthToPatch({ item });
			const patchPlugins = (patch as Record<string, unknown>).plugins as
				| Record<string, { data?: Record<string, unknown> }>
				| undefined;
			const compatData = patchPlugins?.["rag-compat"]?.data;

			expect(compatData).toBeDefined();
			expect(compatData?.synthQuestion).toBeUndefined();
			expect(compatData?.editedQuestion).toBeUndefined();
			expect(compatData?.answer).toBeUndefined();
			expect(compatData?.refs).toBeUndefined();
			expect(compatData?.totalReferences).toBeUndefined();
			expect(compatData?.historyAnnotations).toBeUndefined();
			expect(compatData?.references).toEqual([
				expect.objectContaining({ url: "https://canonical.ref" }),
			]);
			expect(compatData?.retrievals).toBeUndefined();
			expect(compatData?.turnIdentity).toBeUndefined();
		});

		it("does not emit retired refs on user or agent turns in history", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							retrievals: {
								_unassociated: {
									candidates: [
										{ url: "https://ref.com", messageIndex: 1 },
										{ url: "https://user-ref.com", messageIndex: 0 },
									],
								},
							},
						},
					},
				},
			});
			const patch = groundTruthToPatch({ item });

			// User turn should not have refs
			expect(patch.history?.[0].refs).toBeUndefined();

			expect(patch.history?.[1].refs).toBeUndefined();
		});

		it("does not emit refs even when mapped to non-user turns", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							retrievals: {
								_unassociated: {
									candidates: [
										{ url: "https://legacy.ref", messageIndex: 1 },
										{ url: "https://new.ref", messageIndex: 1 },
									],
								},
							},
						},
					},
				},
			});
			const patch = groundTruthToPatch({ item });

			expect(patch.history?.[1]?.refs).toBeUndefined();
		});

		it("does not emit refs when item history exists", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							retrievals: {
								_unassociated: {
									candidates: [
										{ url: "https://legacy-empty.ref", messageIndex: 1 },
										{ url: "https://new-empty.ref", messageIndex: 1 },
									],
								},
							},
						},
					},
				},
			});
			const patch = groundTruthToPatch({ item });

			expect(patch.history?.[1]?.refs).toBeUndefined();
		});

		it("does not serialize refs into assistant history entries", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							retrievals: {
								_unassociated: {
									candidates: [{ url: "https://turn.ref", messageIndex: 1 }],
								},
							},
						},
					},
				},
			});
			const patch = groundTruthToPatch({ item });

			expect(patch.history?.[1].refs).toBeUndefined();
		});

		it("omits ref fields from patch history entries", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				plugins: {
					"rag-compat": {
						kind: "rag-compat",
						version: "1.0",
						data: {
							retrievals: {
								_unassociated: {
									candidates: [
										{
											url: "https://example.com",
											title: "Title",
											chunk: "Snippet",
											keyParagraph: "Key",
											bonus: true,
											messageIndex: 1,
										},
									],
								},
							},
						},
					},
				},
			});
			const patch = groundTruthToPatch({ item });
			expect(patch.history?.[1].refs).toBeUndefined();
		});
	});

	describe("deleted flag mapping", () => {
		it("maps deleted: true to status 'deleted'", () => {
			const item = makeDomainItem({ deleted: true, status: "draft" });
			const patch = groundTruthToPatch({ item });
			expect(patch.status).toBe("deleted");
		});

		it("preserves status when not deleted", () => {
			const item = makeDomainItem({ deleted: false, status: "approved" });
			const patch = groundTruthToPatch({ item });
			expect(patch.status).toBe("approved");
		});
	});

	describe("comment handling", () => {
		it("includes comment when defined", () => {
			const item = makeDomainItem({ comment: "This is a comment" });
			const patch = groundTruthToPatch({ item });
			expect((patch as Record<string, unknown>).comment).toBe(
				"This is a comment",
			);
		});

		it("preserves empty string comment", () => {
			// Empty string is a defined value, so it's preserved as-is
			const item = makeDomainItem({ comment: "" });
			const patch = groundTruthToPatch({ item });
			expect((patch as Record<string, unknown>).comment).toBe("");
		});

		it("omits comment when undefined", () => {
			// When comment is undefined, it's not included in the patch at all
			const item = makeDomainItem({ comment: undefined });
			const patch = groundTruthToPatch({ item });
			expect("comment" in patch).toBe(false);
		});
	});

	describe("expectedBehavior serialization", () => {
		it("includes expectedBehavior in patch", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{
						role: "agent",
						content: "A",
						expectedBehavior: [
							"generation:clarification",
							"generation:need-context",
						],
					},
				],
			});
			const patch = groundTruthToPatch({ item });
			expect(patch.history?.[1].expectedBehavior).toEqual([
				"generation:clarification",
				"generation:need-context",
			]);
		});

		it("omits expectedBehavior when undefined", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
			});
			const patch = groundTruthToPatch({ item });
			expect(patch.history?.[1].expectedBehavior).toBeUndefined();
		});
	});

	describe("basic field mapping", () => {
		it("serializes canonical history content without role remapping", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "My question" },
					{ role: "agent", content: "My answer" },
				],
			});
			const patch = groundTruthToPatch({ item });
			expect(patch.history?.[0]).toMatchObject({
				role: "user",
				msg: "My question",
			});
			expect(patch.history?.[1]).toMatchObject({
				role: "agent",
				msg: "My answer",
			});
		});

		it("includes manualTags", () => {
			const item = makeDomainItem({ manualTags: ["tag1", "tag2"] });
			const patch = groundTruthToPatch({ item });
			expect(patch.manualTags).toEqual(["tag1", "tag2"]);
		});
	});

	describe("contextEntries serialization", () => {
		it("includes explicit empty contextEntries arrays in the patch", () => {
			const item = makeDomainItem({ contextEntries: [] });
			const patch = groundTruthToPatch({ item });

			expect(patch).toHaveProperty("contextEntries");
			expect((patch as Record<string, unknown>).contextEntries).toEqual([]);
		});

		it("omits undefined contextEntries from the patch", () => {
			const item = makeDomainItem({ contextEntries: undefined });
			const patch = groundTruthToPatch({ item });

			expect("contextEntries" in patch).toBe(false);
		});
	});
});
