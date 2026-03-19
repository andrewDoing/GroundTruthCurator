/**
 * Unit tests for expected behavior validation in gtHelpers
 *
 * NOTE (Phase 2 generic schema): canApproveMultiTurn no longer requires
 * expectedBehavior on every agent turn. Approval is gated only on:
 *   - valid conversation pattern (user/non-user alternating, ends on non-user)
 *   - item not deleted
 * These tests document the current generic-approval behavior.
 */

import { describe, expect, it } from "vitest";
import type {
	ConversationTurn,
	GroundTruthItem,
} from "../../../src/models/groundTruth";
import {
	canApproveCandidate,
	canApproveMultiTurn,
} from "../../../src/models/gtHelpers";

describe("canApproveMultiTurn - Expected Behavior Validation", () => {
	const baseItem: GroundTruthItem = {
		id: "test-1",
		providerId: "test",
		question: "Test question",
		status: "draft",
		expectedTools: { required: [{ name: "search" }] },
		toolCalls: [{ id: "tc1", name: "search", callType: "tool" }],
		history: [
			{
				role: "user",
				content: "How do I extrude a shape?",
			},
			{
				role: "agent",
				content: "Here is how you extrude a shape...",
				expectedBehavior: ["tool:search", "generation:answer"],
			},
		],
	};

	it("should allow approval when all agent turns have expected behavior", () => {
		const result = canApproveMultiTurn(baseItem);
		expect(result).toBe(true);
	});

	it("should allow approval when agent turn has no expected behavior (generic schema: not required)", () => {
		const itemWithoutBehavior: GroundTruthItem = {
			...baseItem,
			history: [
				{
					role: "user",
					content: "How do I extrude a shape?",
				},
				{
					role: "agent",
					content: "Here is how you extrude a shape...",
					// Missing expectedBehavior — no longer blocks approval
				},
			],
		};

		const result = canApproveMultiTurn(itemWithoutBehavior);
		expect(result).toBe(true);
	});

	it("should allow approval when agent turn has empty expected behavior array (generic schema: not required)", () => {
		const itemWithEmptyBehavior: GroundTruthItem = {
			...baseItem,
			history: [
				{
					role: "user",
					content: "How do I extrude a shape?",
				},
				{
					role: "agent",
					content: "Here is how you extrude a shape...",
					expectedBehavior: [],
				},
			],
		};

		const result = canApproveMultiTurn(itemWithEmptyBehavior);
		expect(result).toBe(true);
	});

	it("should allow approval when all multiple agent turns have expected behavior", () => {
		const multiTurnItem: GroundTruthItem = {
			...baseItem,
			history: [
				{
					role: "user",
					content: "How do I extrude a shape?",
				},
				{
					role: "agent",
					content: "Can you specify which software?",
					expectedBehavior: ["generation:need-context"],
				},
				{
					role: "user",
					content: "A CAD application",
				},
				{
					role: "agent",
					content: "Here is how you extrude in a CAD application...",
					expectedBehavior: ["tool:search", "generation:answer"],
				},
			],
		};

		const result = canApproveMultiTurn(multiTurnItem);
		expect(result).toBe(true);
	});

	it("should allow approval when any agent turn is missing expected behavior (generic schema: not required)", () => {
		const multiTurnItem: GroundTruthItem = {
			...baseItem,
			history: [
				{
					role: "user",
					content: "How do I extrude a shape?",
				},
				{
					role: "agent",
					content: "Can you specify which software?",
					expectedBehavior: ["generation:need-context"],
				},
				{
					role: "user",
					content: "A CAD application",
				},
				{
					role: "agent",
					content: "Here is how you extrude in a CAD application...",
					// Missing expectedBehavior on second agent turn — no longer blocks
				},
			],
		};

		const result = canApproveMultiTurn(multiTurnItem);
		expect(result).toBe(true);
	});

	it("should allow approval with single expected behavior", () => {
		const itemWithSingleBehavior: GroundTruthItem = {
			...baseItem,
			history: [
				{
					role: "user",
					content: "Tell me about this software",
				},
				{
					role: "agent",
					content: "It is a 3D CAD software...",
					expectedBehavior: ["generation:answer"],
				},
			],
		};

		const result = canApproveMultiTurn(itemWithSingleBehavior);
		expect(result).toBe(true);
	});

	it("blocks multi-turn approval when required references are unvisited", () => {
		const itemWithUnvisitedReferences: GroundTruthItem = {
			...baseItem,
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						retrievals: {
							_unassociated: {
								candidates: [{ url: "https://example.com/trace" }],
							},
						},
					},
				},
			},
		};

		const result = canApproveMultiTurn(itemWithUnvisitedReferences, {
			requireReferenceVisit: true,
			requireKeyParagraph: false,
		});
		expect(result).toBe(false);
	});

	it("blocks multi-turn approval when required key paragraphs are missing", () => {
		const itemWithShortKeyParagraph: GroundTruthItem = {
			...baseItem,
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						retrievals: {
							_unassociated: {
								candidates: [
									{
										url: "https://example.com/trace",
										visitedAt: "2026-03-13T12:00:00Z",
										keyParagraph: "Too short to satisfy the requirement.",
									},
								],
							},
						},
					},
				},
			},
		};

		const result = canApproveMultiTurn(itemWithShortKeyParagraph, {
			requireReferenceVisit: true,
			requireKeyParagraph: true,
		});
		expect(result).toBe(false);
	});

	it("allows multi-turn approval when reference requirements are disabled", () => {
		const itemWithUnvisitedReferences: GroundTruthItem = {
			...baseItem,
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						retrievals: {
							_unassociated: {
								candidates: [{ url: "https://example.com/trace" }],
							},
						},
					},
				},
			},
		};

		const result = canApproveMultiTurn(itemWithUnvisitedReferences, {
			requireReferenceVisit: false,
			requireKeyParagraph: false,
		});
		expect(result).toBe(true);
	});

	it("threads reference requirements through canApproveCandidate for multi-turn items", () => {
		const itemWithUnvisitedReferences: GroundTruthItem = {
			...baseItem,
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						retrievals: {
							_unassociated: {
								candidates: [{ url: "https://example.com/trace" }],
							},
						},
					},
				},
			},
		};

		const result = canApproveCandidate(itemWithUnvisitedReferences, {
			requireReferenceVisit: true,
			requireKeyParagraph: false,
		});
		expect(result).toBe(false);
	});

	it("allows multi-turn approval when required references are visited and annotated", () => {
		const itemWithReadyReferences: GroundTruthItem = {
			...baseItem,
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						retrievals: {
							_unassociated: {
								candidates: [
									{
										url: "https://example.com/trace",
										visitedAt: "2026-03-13T12:00:00Z",
										keyParagraph:
											"This key paragraph is comfortably longer than forty characters.",
									},
								],
							},
						},
					},
				},
			},
		};

		const result = canApproveCandidate(itemWithReadyReferences, {
			requireReferenceVisit: true,
			requireKeyParagraph: true,
		});
		expect(result).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// canApproveMultiTurn – expectedTools gating (Phase 4)
// ---------------------------------------------------------------------------

describe("canApproveMultiTurn - expectedTools gating", () => {
	const localBaseItem: GroundTruthItem = {
		id: "test-et",
		providerId: "test",
		question: "Test question",
		history: [{ role: "agent", content: "Test answer" }],
		status: "draft",
	};
	const validHistory: ConversationTurn[] = [
		{ role: "user", content: "q" },
		{ role: "agent", content: "a" },
	];

	it("blocks approval when no expectedTools are defined (≥1 required tool gate)", () => {
		const item: GroundTruthItem = {
			...localBaseItem,
			history: validHistory,
		};
		expect(canApproveMultiTurn(item)).toBe(false);
	});

	it("approves when all required tools are present in toolCalls", () => {
		const item: GroundTruthItem = {
			...localBaseItem,
			history: validHistory,
			expectedTools: { required: [{ name: "search" }] },
			toolCalls: [{ id: "1", name: "search", callType: "tool" }],
		};
		expect(canApproveMultiTurn(item)).toBe(true);
	});

	it("blocks approval when a required tool is missing from toolCalls", () => {
		const item: GroundTruthItem = {
			...localBaseItem,
			history: validHistory,
			expectedTools: { required: [{ name: "search" }] },
			toolCalls: [],
		};
		expect(canApproveMultiTurn(item)).toBe(false);
	});

	it("blocks approval when only optional or notNeeded tools exist (no required)", () => {
		const item: GroundTruthItem = {
			...localBaseItem,
			history: validHistory,
			expectedTools: {
				optional: [{ name: "summarize" }],
				notNeeded: [{ name: "rerank" }],
			},
			toolCalls: [],
		};
		expect(canApproveMultiTurn(item)).toBe(false);
	});

	it("allows plugin bypass of required-tools gate", () => {
		const item: GroundTruthItem = {
			...localBaseItem,
			history: validHistory,
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1",
					data: { canBypassRequiredTools: true },
				},
			},
		};
		expect(canApproveMultiTurn(item)).toBe(true);
	});

	it("plugin bypass does not skip validation of required tools actually defined", () => {
		const item: GroundTruthItem = {
			...localBaseItem,
			history: validHistory,
			expectedTools: { required: [{ name: "search" }] },
			toolCalls: [],
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1",
					data: { canBypassRequiredTools: true },
				},
			},
		};
		// Bypass allows the "≥1 required" gate, but validateExpectedTools still blocks
		// because the required "search" tool is missing from toolCalls
		expect(canApproveMultiTurn(item)).toBe(false);
	});
});
