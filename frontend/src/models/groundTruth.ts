// Domain models and constants for Ground Truth items

export type ExpectedBehavior =
	| "tool:search"
	| "generation:answer"
	| "generation:need-context"
	| "generation:clarification"
	| "generation:out-of-domain";

export type ConversationTurn = {
	role: "user" | "agent";
	content: string;
	/** Expected behavior(s) for this turn in the conversation (agent turns only) */
	expectedBehavior?: ExpectedBehavior[];
};

export type Reference = {
	id: string;
	title?: string;
	url: string;
	snippet?: string;
	visitedAt?: string | null;
	keyParagraph?: string;
	// Mark as bonus (additional context)
	bonus?: boolean;
	// Which agent turn these refs belong to (optional)
	messageIndex?: number;
};

export type GroundTruthItem = {
	id: string;
	question: string;
	answer: string;
	// NEW: full conversation history for multi-turn support
	history?: ConversationTurn[];
	references: Reference[];
	status: "draft" | "approved" | "skipped" | "deleted";
	providerId: string; // e.g., 'json'
	deleted?: boolean; // soft delete flag (sidebar still shows it)
	/** Free-form general tags associated with this item. */
	tags?: string[];
	/** User-curated manual tags (editable) */
	manualTags?: string[];
	/** System-generated computed tags (read-only in UI) */
	computedTags?: string[];
	/** Optional free-form curator comments/notes. */
	comment?: string;
	/** Optional dataset name when sourced from API-backed provider. */
	datasetName?: string;
	/** Optional storage bucket when sourced from API-backed provider. */
	bucket?: string;
	/** ISO date string of the last review, when provided by the API. */
	reviewedAt?: string | null;
	/**
	 * Markdown instructions specific to this item/dataset.
	 * Rendered in a collapsible pane above the Question/Answer editors.
	 */
	curationInstructions?: string;
	/** Backend-computed total count of references (item-level + all turn-level). */
	totalReferences?: number;
	/** ETag for optimistic concurrency control */
	_etag?: string;
};

// Helper functions for multi-turn support

/**
 * Returns the last user message from history, or falls back to item.question
 */
export function getLastUserTurn(item: GroundTruthItem): string {
	if (!item.history || item.history.length === 0) {
		return item.question;
	}
	// Find the last user turn
	for (let i = item.history.length - 1; i >= 0; i--) {
		if (item.history[i].role === "user") {
			return item.history[i].content;
		}
	}
	return item.question;
}

/**
 * Returns the last agent message from history, or falls back to item.answer
 */
export function getLastAgentTurn(item: GroundTruthItem): string {
	if (!item.history || item.history.length === 0) {
		return item.answer;
	}
	// Find the last agent turn
	for (let i = item.history.length - 1; i >= 0; i--) {
		if (item.history[i].role === "agent") {
			return item.history[i].content;
		}
	}
	return item.answer;
}

/**
 * Returns the total number of turns in the conversation
 */
export function getTurnCount(item: GroundTruthItem): number {
	return item.history?.length || 0;
}

/**
 * Checks if the item is using multi-turn mode
 */
export function isMultiTurn(item: GroundTruthItem): boolean {
	return !!item.history && item.history.length > 0;
}

/**
 * Format turns as a plain-text transcript for agent prompts.
 * Optionally limits the transcript to turns before `upToIndex`.
 */
export function formatConversationForAgent(
	turns: ConversationTurn[] | undefined,
	upToIndex?: number,
): string {
	if (!turns?.length) return "";
	const end =
		typeof upToIndex === "number"
			? Math.max(0, Math.min(upToIndex, turns.length))
			: turns.length;
	const slice = turns.slice(0, end);
	return slice
		.map((turn) => {
			const label = turn.role === "agent" ? "Agent" : "User";
			const body = (turn.content || "").trim();
			return body ? `${label}: ${body}` : `${label}:`;
		})
		.join("\n")
		.trim();
}
