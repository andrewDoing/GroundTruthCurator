import { describe, expect, it } from "vitest";
import {
	formatConversationForAgent,
	getLastAgentTurn,
	getLastUserTurn,
	getTurnCount,
	isMultiTurn,
	type ConversationTurn,
	type GroundTruthItem,
} from "../../../src/models/groundTruth";

describe("groundTruth multi-turn helpers", () => {
	const makeItem = (overrides: Partial<GroundTruthItem> = {}): GroundTruthItem => ({
		id: "item-1",
		providerId: "demo",
		question: "fallback question",
		answer: "fallback answer",
		references: [],
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
		it("falls back to question when no user turns exist", () => {
			const item = makeItem({ history: [{ role: "agent", content: "Agent" }] });
			expect(getLastUserTurn(item)).toBe("fallback question");
		});

		it("falls back to answer when no agent turns exist", () => {
			const item = makeItem({ history: [{ role: "user", content: "User" }] });
			expect(getLastAgentTurn(item)).toBe("fallback answer");
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
