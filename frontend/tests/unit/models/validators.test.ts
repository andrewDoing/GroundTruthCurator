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

	it("should reject conversation ending with user turn", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "What is the weather?" },
			{ role: "agent", content: "It's sunny today." },
			{ role: "user", content: "What about tomorrow?" },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors).toContain(
			"Conversation must end with an agent response",
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

	it("should accept consecutive agent turns (agentic workflow)", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Why is my bill high?" },
			{ role: "agent", content: "The usage spike came from streaming." },
			{
				role: "agent",
				content: "Root cause: long streaming sessions on mobile data.",
			},
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});

	it("should accept multiple agent roles in sequence", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Diagnose network issue" },
			{ role: "orchestrator-agent", content: "Routing to diagnostics..." },
			{ role: "output-agent", content: "Signal strength is low in your area." },
			{ role: "agent", content: "Summary: tower congestion detected." },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});

	it("should reject conversation starting with agent even if multiple agents follow", () => {
		const history: ConversationTurn[] = [
			{ role: "agent", content: "Starting with agent" },
			{ role: "agent", content: "Another agent" },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors).toContain("Conversation must start with a user turn");
	});

	it("should reject consecutive user turns that end with user", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Question 1" },
			{ role: "user", content: "Question 2" },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(false);
		expect(result.errors).toContain(
			"Conversation must end with an agent response",
		);
	});

	it("should accept consecutive user turns followed by agent", () => {
		const history: ConversationTurn[] = [
			{ role: "user", content: "Question 1" },
			{ role: "user", content: "Wait, let me rephrase" },
			{ role: "agent", content: "Here is my answer." },
		];
		const result = validateConversationPattern(history);
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});
});

// ---------------------------------------------------------------------------
// validateExpectedTools
// ---------------------------------------------------------------------------
import type { GroundTruthItem } from "../../../src/models/groundTruth";
import { validateExpectedTools } from "../../../src/models/validators";

const baseItem: GroundTruthItem = {
	id: "t1",
	providerId: "test",
	question: "q",
	answer: "a",
	status: "draft",
};

describe("validateExpectedTools", () => {
	it("returns valid when no expectedTools defined", () => {
		const result = validateExpectedTools({ ...baseItem });
		expect(result.valid).toBe(true);
		expect(result.missingRequired).toHaveLength(0);
	});

	it("returns valid when expectedTools.required is empty", () => {
		const result = validateExpectedTools({
			...baseItem,
			expectedTools: { required: [] },
		});
		expect(result.valid).toBe(true);
	});

	it("returns valid when all required tools are in toolCalls", () => {
		const result = validateExpectedTools({
			...baseItem,
			expectedTools: {
				required: [{ name: "search" }, { name: "lookup" }],
			},
			toolCalls: [
				{ id: "1", name: "search", callType: "tool" },
				{ id: "2", name: "lookup", callType: "tool" },
			],
		});
		expect(result.valid).toBe(true);
		expect(result.missingRequired).toHaveLength(0);
	});

	it("returns invalid with missingRequired when a required tool is absent", () => {
		const result = validateExpectedTools({
			...baseItem,
			expectedTools: {
				required: [{ name: "search" }, { name: "lookup" }],
			},
			toolCalls: [{ id: "1", name: "search", callType: "tool" }],
		});
		expect(result.valid).toBe(false);
		expect(result.missingRequired).toEqual(["lookup"]);
		expect(result.errors).toHaveLength(1);
		expect(result.errors[0]).toContain("lookup");
	});

	it("ignores optional and notNeeded in validation", () => {
		const result = validateExpectedTools({
			...baseItem,
			expectedTools: {
				required: [{ name: "search" }],
				optional: [{ name: "summarize" }],
				notNeeded: [{ name: "rerank" }],
			},
			toolCalls: [{ id: "1", name: "search", callType: "tool" }],
		});
		expect(result.valid).toBe(true);
	});

	it("returns multiple missing tools in errors array", () => {
		const result = validateExpectedTools({
			...baseItem,
			expectedTools: {
				required: [{ name: "toolA" }, { name: "toolB" }, { name: "toolC" }],
			},
			toolCalls: [],
		});
		expect(result.valid).toBe(false);
		expect(result.missingRequired).toHaveLength(3);
		expect(result.errors).toHaveLength(3);
	});
});
