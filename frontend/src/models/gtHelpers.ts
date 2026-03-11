import { getCachedConfig } from "../services/runtimeConfig";
import type { GroundTruthItem, Reference } from "./groundTruth";
import { refsApprovalReady, validateConversationPattern } from "./validators";

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

// Dedupe references by URL and messageIndex combination
// In multi-turn contexts, the same URL can exist for different turns
// In single-turn contexts (no messageIndex), dedupe by URL only
export function dedupeReferences(
	existing: Reference[],
	chosen: Reference[],
): Reference[] {
	// Create a composite key: URL + messageIndex (or URL only if no messageIndex)
	const makeKey = (r: Reference) =>
		r.messageIndex !== undefined ? `${r.url}::turn${r.messageIndex}` : r.url;

	const map = new Map(existing.map((r) => [makeKey(r), r] as const));
	for (const r of chosen) {
		const key = makeKey(r);
		if (!map.has(key)) {
			map.set(key, r);
		}
	}
	return Array.from(map.values());
}

// Determine if an item can be approved (generic or single-turn)
export function canApproveCandidate(
	item: GroundTruthItem | null | undefined,
): boolean {
	if (!item) return false;
	if (item.deleted) return false;

	// Check if multi-turn or generic (has history)
	if (item.history && item.history.length > 0) {
		return canApproveMultiTurn(item);
	}

	// Single-turn fallback (compatibility — kept for items without history)
	const hasReferences =
		Array.isArray(item.references) && item.references.length > 0;
	return hasReferences && refsApprovalReady(item);
}

// Determine if a multi-turn / generic item can be approved.
// Generic approval gate: valid conversation pattern + not deleted.
// Reference-visit and per-turn expectedBehavior requirements are now
// optional/configurable rather than hard gates (moved toward compatibility pack).
export function canApproveMultiTurn(
	item: GroundTruthItem | null | undefined,
): boolean {
	if (!item || !item.history || item.history.length === 0) return false;
	if (item.deleted) return false;

	// Validate conversation pattern (starts with user, pairs complete)
	const patternValidation = validateConversationPattern(item.history);
	if (!patternValidation.valid) return false;

	// Check if all references must be visited (configurable)
	if (requireReferenceVisit() && item.references.length > 0) {
		const allVisited = item.references.every((r) => Boolean(r.visitedAt));
		if (!allVisited) return false;
	}

	// Check if key paragraphs are required (configurable)
	if (requireKeyParagraph() && item.references.length > 0) {
		const allHaveKeyParagraph = item.references.every(
			(r) => r.keyParagraph && r.keyParagraph.trim().length >= 40,
		);
		if (!allHaveKeyParagraph) return false;
	}

	return true;
}
