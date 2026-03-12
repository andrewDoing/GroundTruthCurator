// Domain models and constants for Ground Truth items

// ---------------------------------------------------------------------------
// Generic schema types (aligned with gt_schema_v5_generic.py and generated API)
// ---------------------------------------------------------------------------

/** A key-value pair of context provided to the agent scenario. */
export type ContextEntry = {
	key: string;
	value: unknown;
};

/** A record of a single tool or sub-agent call made during execution. */
export type ToolCallRecord = {
	id: string;
	name: string;
	callType: "tool" | "subagent";
	agent?: string | null;
	stepNumber?: number | null;
	parallelGroup?: string | null;
	parentCallId?: string | null;
	response?: unknown;
};

/** A single tool expectation within an expected-tools group. */
export type ToolExpectation = {
	name: string;
	arguments?: Record<string, unknown> | string | null;
};

/**
 * Item-level expected tool specification.
 * Tools are implicitly allowed unless listed here.
 */
export type ExpectedTools = {
	required?: ToolExpectation[];
	optional?: ToolExpectation[];
	notNeeded?: ToolExpectation[];
};

/** Curator or automated feedback attached to an item. */
export type FeedbackEntry = {
	source: string;
	values?: Record<string, unknown>;
};

/** An opaque plugin payload stored under a named slot. */
export type PluginPayload = {
	kind: string;
	version: string;
	data?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Existing types kept for backward compat
// ---------------------------------------------------------------------------

export type ExpectedBehavior =
	| "tool:search"
	| "generation:answer"
	| "generation:need-context"
	| "generation:clarification"
	| "generation:out-of-domain";

export type ConversationTurn = {
	/** Free-form role string. "user" marks the human turn; any other value is a non-user (agent/assistant) turn.
	 *  Common values: "user", "agent", "assistant", "output-agent", "orchestrator-agent". */
	role: string;
	content: string;
	/** Expected behavior(s) for this turn in the conversation (agent turns only, legacy/compat) */
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
	// ---------------------------------------------------------------------------
	// Legacy / backward-compat fields (kept for single-turn and mapper compat)
	// ---------------------------------------------------------------------------
	question: string;
	answer: string;
	// ---------------------------------------------------------------------------
	// Generic schema fields (Phase 2+)
	// ---------------------------------------------------------------------------
	/** Conversation history. Free-form roles; "user" marks human turns. */
	history?: ConversationTurn[];
	/** Scenario identifier linking this item to an originating scenario. */
	scenarioId?: string;
	/** Context entries provided to the agent (key-value pairs). */
	contextEntries?: ContextEntry[];
	/** Tool call records captured during agent execution. */
	toolCalls?: ToolCallRecord[];
	/** Item-level tool expectations (required / optional / not-needed). */
	expectedTools?: ExpectedTools;
	/** Feedback entries from curators or automated systems. */
	feedback?: FeedbackEntry[];
	/** Arbitrary metadata dictionary for trace info and other extensions. */
	metadata?: Record<string, unknown>;
	/** Plugin-specific payloads keyed by plugin slot name. */
	plugins?: Record<string, PluginPayload>;
	/** Trace correlation IDs (e.g., conversationId, sessionId). */
	traceIds?: Record<string, string> | null;
	/** Full raw trace payload for evidence review. */
	tracePayload?: Record<string, unknown>;
	// ---------------------------------------------------------------------------
	// Legacy reference surface (compatibility; canonical data lives in history)
	// ---------------------------------------------------------------------------
	references: Reference[];
	// ---------------------------------------------------------------------------
	// Common lifecycle and metadata fields
	// ---------------------------------------------------------------------------
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
 * Returns the last agent message from history, or falls back to item.answer.
 * "Agent" is any turn whose role is not "user" (supports free-form roles).
 */
export function getLastAgentTurn(item: GroundTruthItem): string {
	if (!item.history || item.history.length === 0) {
		return item.answer;
	}
	// Find the last non-user turn (any agent/assistant/orchestrator role)
	for (let i = item.history.length - 1; i >= 0; i--) {
		if (item.history[i].role !== "user") {
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
 * Returns a short preview string for queue display:
 * uses the first user turn from history, falling back to item.question.
 */
export function getQueuePreview(item: GroundTruthItem): string {
	const first = item.history?.find((t) => t.role === "user");
	return first?.content || item.question || "(no message)";
}

/**
 * Returns whether the item has any generic evidence data worth showing
 * in the evidence/trace panel (toolCalls, expectedTools, traceIds, metadata, feedback).
 */
export function hasEvidenceData(item: GroundTruthItem): boolean {
	return (
		(item.toolCalls?.length ?? 0) > 0 ||
		item.expectedTools != null ||
		item.traceIds != null ||
		Object.keys(item.metadata ?? {}).length > 0 ||
		(item.feedback?.length ?? 0) > 0 ||
		Object.keys(item.tracePayload ?? {}).length > 0
	);
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
			const label =
				turn.role === "user"
					? "User"
					: turn.role === "agent"
						? "Agent"
						: turn.role;
			const body = (turn.content || "").trim();
			return body ? `${label}: ${body}` : `${label}:`;
		})
		.join("\n")
		.trim();
}
