import {
	getRuntimeConfigSnapshot,
	type RuntimeConfig,
} from "../services/runtimeConfig";
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

export type ReferenceApprovalRequirements = Pick<
	RuntimeConfig,
	"requireReferenceVisit" | "requireKeyParagraph"
>;

function getFallbackRequireReferenceVisit() {
	const val = import.meta.env.VITE_REQUIRE_REFERENCE_VISIT;
	if (val === undefined || val === null) return true;
	if (typeof val === "boolean") return val;
	return val !== "false" && val !== "0";
}

function getFallbackRequireKeyParagraph() {
	const val = import.meta.env.VITE_REQUIRE_KEY_PARAGRAPH;
	if (val === undefined || val === null) return false;
	if (typeof val === "boolean") return val;
	return val === "true" || val === "1";
}

export function getReferenceApprovalRequirements(
	config: RuntimeConfig | null = getRuntimeConfigSnapshot(),
): ReferenceApprovalRequirements {
	return {
		requireReferenceVisit:
			config?.requireReferenceVisit ?? getFallbackRequireReferenceVisit(),
		requireKeyParagraph:
			config?.requireKeyParagraph ?? getFallbackRequireKeyParagraph(),
	};
}

/**
 * Validation result for multi-turn conversations.
 * Contains validation status and detailed error messages.
 */
type ConversationValidationResult = {
	valid: boolean;
	errors: string[];
};

/**
 * Validates that a conversation meets minimum structural requirements:
 * - Must have at least one turn
 * - Must start with a user turn (role === "user")
 * - Must end with a non-user (agent) turn
 *
 * Consecutive turns of the same role (e.g. multiple agent responses) are
 * allowed to support agentic workflows such as orchestrator → sub-agent or
 * separate chat_response and RCA turns.
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

	// Must end with an agent (non-user) turn so every user query has a response
	if (history[history.length - 1].role === "user") {
		errors.push("Conversation must end with an agent response");
	}

	return {
		valid: errors.length === 0,
		errors,
	};
}

// Validation helper (SELF-TESTED)
export function refsApprovalReady(
	it: GroundTruthItem,
	requirements = getReferenceApprovalRequirements(),
): boolean {
	const refs = getItemReferences(it);
	// Rule: Approval is allowed with zero references.
	if (refs.length === 0) return true;

	// Check if all references must be visited (configurable)
	if (requirements.requireReferenceVisit) {
		const allVisited = refs.every((r) => Boolean(r.visitedAt));
		if (!allVisited) return false;
	}

	// Check if key paragraphs are required for all references (configurable)
	if (requirements.requireKeyParagraph) {
		const allHaveKeyParagraph = refs.every(
			(r) => r.keyParagraph && r.keyParagraph.trim().length >= 40,
		);
		if (!allHaveKeyParagraph) return false;
	}

	return true;
}
