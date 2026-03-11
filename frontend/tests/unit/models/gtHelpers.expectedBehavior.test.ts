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
import type { GroundTruthItem } from "../../../src/models/groundTruth";
import { canApproveMultiTurn } from "../../../src/models/gtHelpers";

describe("canApproveMultiTurn - Expected Behavior Validation", () => {
	const baseItem: GroundTruthItem = {
		id: "test-1",
		providerId: "test",
		question: "Test question",
		answer: "Test answer",
		status: "draft",
		references: [],
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

	it("should allow approval for multi-turn items even when references are unvisited", () => {
		const itemWithUnvisitedReferences: GroundTruthItem = {
			...baseItem,
			references: [
				{
					id: "ref-1",
					url: "https://example.com/trace",
					visitedAt: null,
				},
			],
		};

		const result = canApproveMultiTurn(itemWithUnvisitedReferences);
		expect(result).toBe(true);
	});
});
