import { getCachedConfig } from "../services/runtimeConfig";
import type { ConversationTurn, GroundTruthItem } from "./groundTruth";
import { getItemReferences } from "./groundTruth";

// ---------------------------------------------------------------------------
// Expected-tools validation
// ---------------------------------------------------------------------------

/**
 * Result of validating an item's expectedTools against its actual toolCalls.
 */
export type ExpectedToolsValidationResult = {
	/** True when all required tools are present in toolCalls (or no requirements). */
	valid: boolean;
	/** Names of required tools that were not found in toolCalls. */
	missingRequired: string[];
	/** Human-readable error messages, one per missing required tool. */
	errors: string[];
};

/**
 * Validates that every tool listed under `expectedTools.required` appears at
 * least once in `toolCalls`.  Optional and notNeeded buckets are informational
 * and do not affect the result.
 *
 * Returns `valid: true` when:
 * - `expectedTools` is absent or has no required tools, OR
 * - All required tools appear in `toolCalls`.
 */
export function validateExpectedTools(
	item: GroundTruthItem,
): ExpectedToolsValidationResult {
	const required = item.expectedTools?.required;
	if (!required?.length) {
		return { valid: true, missingRequired: [], errors: [] };
	}

	const calledNames = new Set((item.toolCalls ?? []).map((tc) => tc.name));
	const missingRequired = required
		.filter((te) => !calledNames.has(te.name))
		.map((te) => te.name);

	return {
		valid: missingRequired.length === 0,
		missingRequired,
		errors: missingRequired.map(
			(name) => `Required tool "${name}" was not called`,
		),
	};
}

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
 * - Must start with a user turn (role === "user")
 * - Must alternate between user and non-user turns (free-form agent roles supported)
 * - Every user turn must have a corresponding non-user (agent) turn
 * - The conversation should end with a non-user turn for approval
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

	// Check alternating pattern: even indices must be "user", odd indices must be non-"user"
	for (let i = 0; i < history.length; i++) {
		const currentTurn = history[i];
		const expectedIsUser = i % 2 === 0;

		if (expectedIsUser && currentTurn.role !== "user") {
			errors.push(
				`Turn ${i + 1} should be a user turn, but found role "${currentTurn.role}"`,
			);
		} else if (!expectedIsUser && currentTurn.role === "user") {
			errors.push(
				`Turn ${i + 1} should be an agent/non-user turn, but found user turn`,
			);
		}
	}

	// For approval, the conversation should end with a non-user turn (even index count)
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
	const refs = getItemReferences(it);
	// Rule: Approval is allowed with zero references.
	if (refs.length === 0) return true;

	// Check if all references must be visited (configurable)
	if (requireReferenceVisit()) {
		const allVisited = refs.every((r) => Boolean(r.visitedAt));
		if (!allVisited) return false;
	}

	// Check if key paragraphs are required for all references (configurable)
	if (requireKeyParagraph()) {
		const allHaveKeyParagraph = refs.every(
			(r) => r.keyParagraph && r.keyParagraph.trim().length >= 40,
		);
		if (!allHaveKeyParagraph) return false;
	}

	return true;
}
