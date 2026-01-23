/**
 * Unit tests for expected behavior validation in gtHelpers
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

	it("should block approval when agent turn has no expected behavior", () => {
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
					// Missing expectedBehavior
				},
			],
		};

		const result = canApproveMultiTurn(itemWithoutBehavior);
		expect(result).toBe(false);
	});

	it("should block approval when agent turn has empty expected behavior array", () => {
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
		expect(result).toBe(false);
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

	it("should block approval when any agent turn is missing expected behavior", () => {
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
					// Missing expectedBehavior on second agent turn
				},
			],
		};

		const result = canApproveMultiTurn(multiTurnItem);
		expect(result).toBe(false);
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
});
