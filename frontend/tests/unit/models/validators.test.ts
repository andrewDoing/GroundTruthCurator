import { describe, expect, it } from "vitest";
import type { ConversationTurn } from "../../../src/models/groundTruth";
import { validateConversationPattern } from "../../../src/models/validators";

describe("validateConversationPattern", () => {
	it("should reject empty or undefined history", () => {
		const result1 = validateConversationPattern(undefined);
		expect(result1.valid).toBe(false);
		expect(result1.errors).toContain(
			"Conversation must have at least one turn",
		);

		const result2 = validateConversationPattern([]);
		expect(result2.valid).toBe(false);
		expect(result2.errors).toContain(
			"Conversation must have at least one turn",
		);
	});

	it("should reject conversation that doesn't start with user turn", () => {
		const history: ConversationTurn[] = [{ role: "agent", content: "Hello" }];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors).toContain("Conversation must start with a user turn");
	});

	it("should accept valid single user-agent pair", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "What is the weather?" },
			{ role: "agent", content: "It's sunny today." },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});

	it("should reject conversation ending with user turn (incomplete)", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "What is the weather?" },
			{ role: "agent", content: "It's sunny today." },
			{ role: "user", content: "What about tomorrow?" },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors).toContain(
			"Conversation must end with an agent response (every user turn needs an agent response)",
		);
	});

	it("should accept valid multi-turn conversation", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "What is the weather?" },
			{ role: "agent", content: "It's sunny today." },
			{ role: "user", content: "What about tomorrow?" },
			{ role: "agent", content: "Tomorrow will be cloudy." },
			{ role: "user", content: "Should I bring an umbrella?" },
			{ role: "agent", content: "Yes, rain is expected in the evening." },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});

	it("should reject conversation with broken alternating pattern", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Question 1" },
			{ role: "user", content: "Question 2" }, // Wrong - should be agent
			{ role: "agent", content: "Answer" },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors.length).toBeGreaterThan(0);
		expect(
			result.errors.some((e) => e.includes("Turn 2 should be a agent turn")),
		).toBe(true);
	});

	it("should reject conversation with consecutive agent turns", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Question" },
			{ role: "agent", content: "Answer 1" },
			{ role: "agent", content: "Answer 2" }, // Wrong - should be user
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors.length).toBeGreaterThan(0);
	});

	it("should provide multiple errors when multiple violations exist", () => {
		const history: ConversationTurn[] = [
			{ role: "agent", content: "Starting with agent" }, // Error 1: doesn't start with user
			{ role: "agent", content: "Another agent" }, // Error 2: wrong pattern
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors.length).toBeGreaterThan(1);
	});

	it("should handle conversation with only one user turn (incomplete)", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Just a question" },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors).toContain(
			"Conversation must end with an agent response (every user turn needs an agent response)",
		);
	});
});
