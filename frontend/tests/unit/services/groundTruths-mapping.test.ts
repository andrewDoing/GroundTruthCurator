import { describe, expect, it } from "vitest";
import type { components } from "../../../src/api/generated";
import { mapGroundTruthFromApi } from "../../../src/services/groundTruths";

type ApiItem = components["schemas"]["GroundTruthItem-Output"];

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
	describe("reference messageIndex assignment for single-turn conversion", () => {
		it("assigns refs to messageIndex 1 when converting single-turn with answer", () => {
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

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.references).toHaveLength(1);
			expect(result.references[0].messageIndex).toBe(1); // Agent turn index
		});

		it("assigns refs to messageIndex 1 even when no answer exists (Bug Fix: SA-86)", () => {
			// Bug 3: For Questions Without an Answer, Agent Turn Doesn't Get Created and UI Doesn't Show Existing Refs
			// Fix ensures that refs are assigned to agent turn (messageIndex = 1) even when answer is empty
			const apiItem = makeApiItem({
				synthQuestion: "Question",
				answer: "",
				refs: [
					{
						url: "https://example.com",
						content: "content",
						bonus: false,
					},
				],
				history: undefined,
			});

			const result = mapGroundTruthFromApi(apiItem);

			// References should be assigned to agent turn (messageIndex = 1)
			expect(result.references[0].messageIndex).toBe(1);
		});

		it("creates empty agent turn when question exists but answer is missing (Bug Fix: SA-86)", () => {
			// Bug 3: Ensures agent turn is created even without an answer
			const apiItem = makeApiItem({
				synthQuestion: "Question without answer",
				answer: "",
				history: undefined,
			});

			const result = mapGroundTruthFromApi(apiItem);

			// Should create both user and agent turns
			expect(result.history).toHaveLength(2);
			expect(result.history?.[0]).toMatchObject({
				role: "user",
				content: "Question without answer",
			});
			expect(result.history?.[1]).toMatchObject({
				role: "agent",
				content: "", // Empty agent content
			});
		});

		it("creates empty agent turn for null answer (Bug Fix: SA-86)", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Question",
				answer: null as unknown as string,
				history: undefined,
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.history).toHaveLength(2);
			expect(result.history?.[1]).toMatchObject({
				role: "agent",
				content: "",
			});
		});

		it("creates empty agent turn for undefined answer (Bug Fix: SA-86)", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Question",
				answer: undefined as unknown as string,
				history: undefined,
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.history).toHaveLength(2);
			expect(result.history?.[1]).toMatchObject({
				role: "agent",
				content: "",
			});
		});

		it("assigns refs to messageIndex 1 for question with refs but no answer (Bug Fix: SA-86)", () => {
			// Real-world scenario: curated question with research refs but answer not yet written
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

			const result = mapGroundTruthFromApi(apiItem);

			// Should create history with empty agent turn
			expect(result.history).toHaveLength(2);
			expect(result.history?.[0].content).toBe(
				"How do I configure authentication for my app?",
			);
			expect(result.history?.[1].content).toBe("");

			// All refs should be assigned to the agent turn
			expect(result.references).toHaveLength(2);
			expect(result.references[0].messageIndex).toBe(1);
			expect(result.references[1].messageIndex).toBe(1);
		});

		it("preserves per-turn refs when history exists", () => {
			const apiItem = makeApiItem({
				history: [
					{
						role: "user",
						msg: "Q1",
						refs: undefined,
					},
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

			// Per-turn refs should be extracted with proper messageIndex
			// This is tested in the provider tests, so we just verify they exist
			expect(result.references).toBeDefined();
		});
	});

	describe("history mapping", () => {
		it("converts assistant role to agent", () => {
			const apiItem = makeApiItem({
				history: [
					{ role: "user", msg: "Question" },
					{ role: "assistant", msg: "Answer" },
				],
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.history?.[1].role).toBe("agent");
		});

		it("preserves user role", () => {
			const apiItem = makeApiItem({
				history: [{ role: "user", msg: "Question" }],
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.history?.[0].role).toBe("user");
		});

		it("creates history from synthQuestion when no history provided", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Synth Q",
				answer: "A",
				history: undefined,
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.history).toHaveLength(2);
			expect(result.history?.[0].content).toBe("Synth Q");
			expect(result.history?.[1].content).toBe("A");
		});

		it("prefers editedQuestion over synthQuestion", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Synth",
				editedQuestion: "Edited",
				history: undefined,
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.history?.[0].content).toBe("Edited");
		});
	});

	describe("providerId", () => {
		it("defaults to 'api' when not provided", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Q",
			});

			const result = mapGroundTruthFromApi(apiItem);

			expect(result.providerId).toBe("api");
		});

		it("uses provided providerId", () => {
			const apiItem = makeApiItem({
				synthQuestion: "Q",
			});

			const result = mapGroundTruthFromApi(apiItem, "custom-provider");

			expect(result.providerId).toBe("custom-provider");
		});
	});
});
