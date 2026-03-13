/**
 * Test data helpers for creating GroundTruthItem fixtures.
 * After Phase 6: canonical state is history[]; question/answer are derived.
 */
import type { GroundTruthItem } from "../src/models/groundTruth";

export function makeTestItem(
	overrides: Partial<GroundTruthItem> & {
		/** Shorthand: creates a two-turn conversation from question/answer strings */
		simpleQA?: { question: string; answer: string };
	} = {},
): GroundTruthItem {
	const { simpleQA, ...rest } = overrides;

	const baseHistory = simpleQA
		? [
				{ role: "user", content: simpleQA.question, turnId: "turn_1" },
				{ role: "agent", content: simpleQA.answer, turnId: "turn_2" },
			]
		: [];

	return {
		id: "test-item",
		providerId: "test",
		status: "draft",
		history: baseHistory,
		...rest,
	};
}
