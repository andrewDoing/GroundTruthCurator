import { describe, expect, it } from "vitest";
import {
	groundTruthFromApi,
	groundTruthToPatch,
	type ApiGroundTruth,
} from "../../../src/adapters/apiMapper";
import type { GroundTruthItem } from "../../../src/models/groundTruth";

function makeApiItem(overrides: Partial<ApiGroundTruth> = {}): ApiGroundTruth {
	return {
		id: "gt-1",
		status: "draft",
		answer: "Test answer",
		synthQuestion: "Synth question",
		editedQuestion: "Edited question",
		history: undefined,
		refs: [],
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

describe("groundTruthFromApi", () => {
	describe("role mapping", () => {
		it("maps history role 'assistant' to 'agent'", () => {
			const api = makeApiItem({
				history: [{ role: "assistant", msg: "Hello from assistant" }],
			});
			const result = groundTruthFromApi(api);
			expect(result.history?.[0].role).toBe("agent");
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
		it("assigns turn refs to correct messageIndex", () => {
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
						refs: [{ url: "https://ref3.com", content: "Snippet 3", bonus: false }],
					},
				],
			});
			const result = groundTruthFromApi(api);

			// Refs from history[1] should have messageIndex 1
			const refsAt1 = result.references.filter((r) => r.messageIndex === 1);
			expect(refsAt1).toHaveLength(2);
			expect(refsAt1.map((r) => r.url)).toEqual([
				"https://ref1.com",
				"https://ref2.com",
			]);

			// Refs from history[3] should have messageIndex 3
			const refsAt3 = result.references.filter((r) => r.messageIndex === 3);
			expect(refsAt3).toHaveLength(1);
			expect(refsAt3[0].url).toBe("https://ref3.com");
		});

		it("maps ref fields correctly", () => {
			const api = makeApiItem({
				history: [
					{ role: "user", msg: "Q" },
					{
						role: "assistant",
						msg: "A",
						refs: [
							{
								url: "https://example.com",
								title: "Example Title",
								content: "Snippet content",
								keyExcerpt: "Key paragraph",
								bonus: true,
							},
						],
					},
				],
			});
			const result = groundTruthFromApi(api);
			const ref = result.references[0];

			expect(ref.url).toBe("https://example.com");
			expect(ref.title).toBe("Example Title");
			expect(ref.snippet).toBe("Snippet content");
			expect(ref.keyParagraph).toBe("Key paragraph");
			expect(ref.bonus).toBe(true);
			expect(ref.visitedAt).toBeNull();
			expect(ref.id).toMatch(/^ref_\d+$/);
		});
	});

	describe("legacy single-turn conversion", () => {
		it("creates 2-turn history from editedQuestion and answer", () => {
			const api = makeApiItem({
				editedQuestion: "What is X?",
				answer: "X is Y",
				history: undefined,
			});
			const result = groundTruthFromApi(api);

			expect(result.history).toHaveLength(2);
			expect(result.history?.[0]).toMatchObject({
				role: "user",
				content: "What is X?",
			});
			expect(result.history?.[1]).toMatchObject({
				role: "agent",
				content: "X is Y",
			});
		});

		it("falls back to synthQuestion when editedQuestion is empty", () => {
			const api = makeApiItem({
				synthQuestion: "Synth question?",
				editedQuestion: "",
				answer: "Answer",
				history: undefined,
			});
			const result = groundTruthFromApi(api);

			expect(result.history?.[0].content).toBe("Synth question?");
		});

		it("assigns legacy top-level refs to messageIndex 1", () => {
			const api = makeApiItem({
				editedQuestion: "Question",
				answer: "Answer",
				refs: [{ url: "https://legacy.ref", content: "Legacy content", bonus: false }],
				history: undefined,
			});
			const result = groundTruthFromApi(api);

			expect(result.references).toHaveLength(1);
			expect(result.references[0].messageIndex).toBe(1);
		});

		it("creates empty agent turn when answer is empty", () => {
			const api = makeApiItem({
				editedQuestion: "Question without answer",
				answer: "",
				history: undefined,
			});
			const result = groundTruthFromApi(api);

			expect(result.history).toHaveLength(2);
			expect(result.history?.[1].content).toBe("");
		});
	});

	describe("multi-turn item top-level refs", () => {
		it("assigns top-level refs to undefined messageIndex for true multi-turn", () => {
			const api = makeApiItem({
				history: [
					{ role: "user", msg: "Q" },
					{ role: "assistant", msg: "A" },
				],
				refs: [{ url: "https://global.ref", content: "Global ref", bonus: false }],
			});
			const result = groundTruthFromApi(api);

			expect(result.references).toHaveLength(1);
			expect(result.references[0].messageIndex).toBeUndefined();
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

			expect((result as Record<string, unknown>).datasetName).toBe("my-dataset");
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
});

describe("groundTruthToPatch", () => {
	function makeDomainItem(overrides: Partial<GroundTruthItem> = {}): GroundTruthItem {
		return {
			id: "gt-1",
			providerId: "api",
			question: "Test question",
			answer: "Test answer",
			status: "draft",
			deleted: false,
			tags: [],
			manualTags: [],
			references: [],
			...overrides,
		};
	}

	describe("role mapping", () => {
		it("maps UI role 'agent' to API role 'assistant'", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
			});
			const patch = groundTruthToPatch({ item });

			expect(patch.history?.[0].role).toBe("user");
			expect(patch.history?.[1].role).toBe("assistant");
		});
	});

	describe("reference handling", () => {
		it("includes refs only on agent turns in history", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				references: [
					{ id: "r1", url: "https://ref.com", messageIndex: 1 },
					{ id: "r2", url: "https://user-ref.com", messageIndex: 0 }, // Should be ignored
				],
			});
			const patch = groundTruthToPatch({ item });

			// User turn should not have refs
			expect(patch.history?.[0].refs).toBeUndefined();

			// Agent turn should have refs
			expect(patch.history?.[1].refs).toHaveLength(1);
			expect(patch.history?.[1].refs?.[0].url).toBe("https://ref.com");
		});

		it("preserves top-level refs for legacy items", () => {
			const originalApi = makeApiItem({
				history: undefined,
				refs: [{ url: "https://legacy.ref", bonus: false }],
			});
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				references: [
					{ id: "r1", url: "https://legacy.ref", messageIndex: 1 },
					{ id: "r2", url: "https://new.ref", messageIndex: 1 },
				],
			});
			const patch = groundTruthToPatch({ item, originalApi });

			// Top-level refs should include refs with messageIndex 1
			expect(patch.refs).toHaveLength(2);
			expect(patch.refs?.map((r) => r.url)).toContain("https://legacy.ref");
			expect(patch.refs?.map((r) => r.url)).toContain("https://new.ref");
		});

		it("omits top-level refs for true multi-turn items", () => {
			const originalApi = makeApiItem({
				history: [
					{ role: "user", msg: "Q" },
					{
						role: "assistant",
						msg: "A",
						refs: [{ url: "https://turn.ref", bonus: false }],
					},
				],
				refs: [],
			});
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				references: [{ id: "r1", url: "https://turn.ref", messageIndex: 1 }],
			});
			const patch = groundTruthToPatch({ item, originalApi });

			// Top-level refs should be empty for true multi-turn
			expect(patch.refs).toHaveLength(0);

			// Refs should be in history
			expect(patch.history?.[1].refs).toHaveLength(1);
		});

		it("maps ref fields correctly in patch", () => {
			const item = makeDomainItem({
				history: [
					{ role: "user", content: "Q" },
					{ role: "agent", content: "A" },
				],
				references: [
					{
						id: "r1",
						url: "https://example.com",
						title: "Title",
						snippet: "Snippet",
						keyParagraph: "Key",
						bonus: true,
						messageIndex: 1,
					},
				],
			});
			const patch = groundTruthToPatch({ item });
			const ref = patch.history?.[1].refs?.[0];

			expect(ref?.url).toBe("https://example.com");
			expect(ref?.title).toBe("Title");
			expect(ref?.content).toBe("Snippet");
			expect(ref?.keyExcerpt).toBe("Key");
			expect(ref?.bonus).toBe(true);
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
			expect((patch as Record<string, unknown>).comment).toBe("This is a comment");
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
						expectedBehavior: ["generation:clarification", "generation:need-context"],
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
		it("includes answer and editedQuestion", () => {
			const item = makeDomainItem({
				question: "My question",
				answer: "My answer",
			});
			const patch = groundTruthToPatch({ item });
			expect(patch.answer).toBe("My answer");
			expect(patch.editedQuestion).toBe("My question");
		});

		it("includes manualTags", () => {
			const item = makeDomainItem({ manualTags: ["tag1", "tag2"] });
			const patch = groundTruthToPatch({ item });
			expect(patch.manualTags).toEqual(["tag1", "tag2"]);
		});
	});
});
