import type { GroundTruthItem, Reference } from "./groundTruth";
import { getItemReferences } from "./groundTruth";
import {
	refsApprovalReady,
	validateConversationPattern,
	validateExpectedTools,
} from "./validators";

/**
 * Check whether a plugin declares exemption from the required-tools check.
 * A plugin payload with `data.canBypassRequiredTools: true` opts the item
 * out of the ≥1 required tool gate.
 */
export function canBypassRequiredToolsCheck(item: GroundTruthItem): boolean {
	if (!item.plugins) return false;
	return Object.values(item.plugins).some(
		(p) => p.data?.canBypassRequiredTools === true,
	);
}

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
	const refs = getItemReferences(item);
	const hasReferences = refs.length > 0;
	return hasReferences && refsApprovalReady(item);
}

// Determine if a multi-turn / generic item can be approved.
// Generic approval gate: valid conversation pattern + not deleted +
// ≥1 required expected tool (unless plugin bypass) +
// all required expected tools present in toolCalls (when specified).
export function canApproveMultiTurn(
	item: GroundTruthItem | null | undefined,
): boolean {
	if (!item || !item.history || item.history.length === 0) return false;
	if (item.deleted) return false;

	// Validate conversation pattern (starts with user, pairs complete)
	const patternValidation = validateConversationPattern(item.history);
	if (!patternValidation.valid) return false;

	// Require at least one required tool unless a plugin overrides this gate
	const hasRequired = (item.expectedTools?.required?.length ?? 0) > 0;
	if (!hasRequired && !canBypassRequiredToolsCheck(item)) return false;

	// Validate expected tools when the item defines required tools
	const toolValidation = validateExpectedTools(item);
	if (!toolValidation.valid) return false;

	return true;
}
