import { getCachedConfig } from "../services/runtimeConfig";
import type { ConversationTurn, GroundTruthItem } from "./groundTruth";

// Get config value for reference visit requirement (default: true)
const requireReferenceVisit = () => {
	const config = getCachedConfig();
	if (config !== null) {
		return config.requireReferenceVisit;
	}
	// Fallback to env var if config not loaded yet (shouldn't happen in normal flow)
	const val = import.meta.env.VITE_REQUIRE_REFERENCE_VISIT;
	if (val === undefined || val === null) return true;
	if (typeof val === "boolean") return val;
	return val !== "false" && val !== "0";
};

// Get config value for key paragraph requirement (default: false)
const requireKeyParagraph = () => {
	const config = getCachedConfig();
	if (config !== null) {
		return config.requireKeyParagraph;
	}
	// Fallback to env var if config not loaded yet (shouldn't happen in normal flow)
	const val = import.meta.env.VITE_REQUIRE_KEY_PARAGRAPH;
	if (val === undefined || val === null) return false;
	if (typeof val === "boolean") return val;
	return val === "true" || val === "1";
};

/**
 * Validation result for multi-turn conversations.
 * Contains validation status and detailed error messages.
 */
type ConversationValidationResult = {
	valid: boolean;
	errors: string[];
};

/**
 * Validates that a conversation follows the required pattern:
 * - Must start with a user turn
 * - Must alternate between user and agent turns
 * - Every user turn must have a corresponding agent turn
 * - The conversation should end with an agent turn for approval
 *
 * @param history - The conversation history to validate
 * @returns Validation result with any errors found
 */
export function validateConversationPattern(
	history: ConversationTurn[] | undefined,
): ConversationValidationResult {
	const errors: string[] = [];

	if (!history || history.length === 0) {
		errors.push("Conversation must have at least one turn");
		return { valid: false, errors };
	}

	// Must start with user turn
	if (history[0].role !== "user") {
		errors.push("Conversation must start with a user turn");
	}

	// Check alternating pattern and that every user has an agent response
	for (let i = 0; i < history.length; i++) {
		const currentTurn = history[i];
		const expectedRole = i % 2 === 0 ? "user" : "agent";

		if (currentTurn.role !== expectedRole) {
			errors.push(
				`Turn ${i + 1} should be a ${expectedRole} turn, but found ${currentTurn.role} turn`,
			);
		}
	}

	// For approval, the conversation should end with an agent turn (even index count)
	// This ensures every user query has an agent response
	if (history.length % 2 !== 0) {
		errors.push(
			"Conversation must end with an agent response (every user turn needs an agent response)",
		);
	}

	return {
		valid: errors.length === 0,
		errors,
	};
}

// Validation helper (SELF-TESTED)
export function refsApprovalReady(it: GroundTruthItem): boolean {
	// Rule: Approval is allowed with zero references.
	if (!it.references || it.references.length === 0) return true;

	// Check if all references must be visited (configurable)
	if (requireReferenceVisit()) {
		const allVisited = it.references.every((r) => Boolean(r.visitedAt));
		if (!allVisited) return false;
	}

	// Check if key paragraphs are required for all references (configurable)
	if (requireKeyParagraph()) {
		const allHaveKeyParagraph = it.references.every(
			(r) => r.keyParagraph && r.keyParagraph.trim().length >= 40,
		);
		if (!allHaveKeyParagraph) return false;
	}

	return true;
}
