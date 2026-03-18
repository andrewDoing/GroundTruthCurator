import { describe, expect, it } from "vitest";
import {
	type ConversationTurn,
	formatConversationForAgent,
	type GroundTruthItem,
	getLastAgentTurn,
	getLastUserTurn,
	getTurnCount,
	isMultiTurn,
	withDerivedLegacyFields,
} from "../../../src/models/groundTruth";

describe("groundTruth multi-turn helpers", () => {
	const makeItem = (
		overrides: Partial<GroundTruthItem> = {},
	): GroundTruthItem => ({
		id: "item-1",
		providerId: "demo",
		question: "fallback question",
		history: [{ role: "agent", content: "fallback answer" }],
		status: "draft",
		...overrides,
	});

	describe("formatConversationForAgent", () => {
		it("returns empty string when no turns provided", () => {
			expect(formatConversationForAgent(undefined)).toBe("");
			expect(formatConversationForAgent([])).toBe("");
		});

		it("includes all turns with labels in order", () => {
			const turns: ConversationTurn[] = [
				{ role: "user", content: "Hello" },
				{ role: "agent", content: "Hi there" },
			];
			const result = formatConversationForAgent(turns);
			expect(result).toBe("User: Hello\nAgent: Hi there");
		});

		it("truncates conversation up to provided index (exclusive)", () => {
			const turns: ConversationTurn[] = [
				{ role: "user", content: "First" },
				{ role: "agent", content: "Second" },
				{ role: "user", content: "Third" },
			];
			const result = formatConversationForAgent(turns, 2);
			expect(result).toBe("User: First\nAgent: Second");
		});
	});

	describe("last turn helpers", () => {
		it("returns empty compatibility question when canonical history has no user turn", () => {
			const item = makeItem({ history: [{ role: "agent", content: "Agent" }] });
			expect(getLastUserTurn(item)).toBe("");
		});

		it("returns empty compatibility answer when canonical history has no agent turn", () => {
			const item = makeItem({ history: [{ role: "user", content: "User" }] });
			expect(getLastAgentTurn(item)).toBe("");
		});

		it("treats custom non-user roles as answer turns", () => {
			const item = makeItem({
				history: [
					{ role: "user", content: "User" },
					{ role: "planner", content: "Intermediate planner output" },
				],
			});
			expect(getLastAgentTurn(item)).toBe("Intermediate planner output");
		});

		it("returns latest matching turn content", () => {
			const item = makeItem({
				history: [
					{ role: "user", content: "First question" },
					{ role: "agent", content: "Initial answer" },
					{ role: "user", content: "Follow-up" },
					{ role: "agent", content: "Updated answer" },
				],
			});
			expect(getLastUserTurn(item)).toBe("Follow-up");
			expect(getLastAgentTurn(item)).toBe("Updated answer");
		});

		it("derives compatibility question from the latest user turn for cross-layer parity", () => {
			const item = makeItem({
				history: [
					{ role: "user", content: "Initial question" },
					{ role: "planner", content: "Interim planning output" },
					{ role: "user", content: "Follow-up question" },
					{ role: "assistant", content: "Final answer" },
				],
			});
			expect(withDerivedLegacyFields(item).question).toBe("Follow-up question");
		});

		it("returns the last non-user turn regardless of role label", () => {
			const item = makeItem({
				history: [
					{ role: "user", content: "Question" },
					{ role: "assistant", content: "Assistant output" },
					{ role: "planner", content: "Planner output" },
				],
			});
			expect(getLastAgentTurn(item)).toBe("Planner output");
		});
	});

	describe("conversation metadata helpers", () => {
		it("detects multi-turn items when history has entries", () => {
			const item = makeItem({ history: [{ role: "user", content: "Hi" }] });
			expect(isMultiTurn(item)).toBe(true);
		});

		it("counts turns based on history length", () => {
			const item = makeItem({
				history: [
					{ role: "user", content: "One" },
					{ role: "agent", content: "Two" },
					{ role: "user", content: "Three" },
				],
			});
			expect(getTurnCount(item)).toBe(3);
		});

		it("treats missing history as zero turns", () => {
			const item = makeItem({ history: undefined });
			expect(isMultiTurn(item)).toBe(false);
			expect(getTurnCount(item)).toBe(0);
		});
	});
});
