import {
	collectCanonicalReferencesFromCompatData,
	getCompatData,
	getCompatRetrievalsFromData,
	writeCompatPluginEnvelope,
} from "./ragCompatPayload";

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
	arguments?: Record<string, unknown>;
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

/**
 * A single retrieval result that can be associated with a specific tool call.
 * Supports per-tool-call ownership instead of flat top-level references,
 * and preserves the raw search payload alongside normalised fields.
 */
export type RetrievalCandidate = {
	url: string;
	title?: string;
	chunk?: string;
	rawPayload?: Record<string, unknown>;
	relevance?: "relevant" | "partially_relevant" | "not_relevant";
	toolCallId?: string;
};

export function getRetrievalsMap(item: Pick<GroundTruthItem, "plugins">) {
	return getCompatRetrievalsFromData(getCompatData(item.plugins));
}

/**
 * Extract a flat Reference[] from per-call retrieval state.
 *
 * Read path: returns per-call candidates when present, mapped to the legacy
 * Reference shape.  Falls back to an empty array when no per-call state
 * exists (caller should provide legacy references separately if needed).
 */
export function getItemReferences(item: GroundTruthItem): Reference[] {
	const history = ensureConversationTurnIdentity(item.history);
	const indexByTurnId = getTurnIndexById(history);
	const historyTurnIds = history.map((turn) => turn.turnId);

	return collectCanonicalReferencesFromCompatData({
		data: getCompatData(item.plugins),
		historyTurnIds,
		indexByTurnId,
	});
}

/**
 * Return a new item with references written into per-call plugin state.
 * Groups references by `toolCallId` (falling back to _unassociated).
 * Immutable — returns a new object.
 */
export function withUpdatedReferences(
	item: GroundTruthItem,
	refs: Reference[],
): GroundTruthItem {
	return {
		...item,
		plugins: writeCompatPluginEnvelope({ plugins: item.plugins, refs }),
	};
}

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
	/** Stable identity for canonical multi-turn editing state. */
	turnId?: string;
	/** Stable workflow-step identity when a turn maps to a durable step. */
	stepId?: string;
	/** Free-form role string. "user" marks the human turn; all non-user roles
	 *  represent non-user/answer content (e.g. "agent", "assistant", "planner"). */
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
	// Which agent turn these refs belong to (optional, legacy association)
	messageIndex?: number;
	// Stable turn ownership for canonical multi-turn editing state.
	turnId?: string;
	// Which tool call these refs belong to (per-call retrieval state)
	toolCallId?: string;
};

export function getTurnIndexById(
	history?: ConversationTurn[],
): Map<string, number> {
	return new Map(
		ensureConversationTurnIdentity(history)
			.map((turn, index) =>
				turn.turnId ? ([turn.turnId, index] as const) : null,
			)
			.filter((entry): entry is readonly [string, number] => entry !== null),
	);
}

export function getReferenceMessageIndex(
	ref: Pick<Reference, "messageIndex" | "turnId">,
	history?: ConversationTurn[],
): number | undefined {
	if (ref.turnId) {
		return getTurnIndexById(history).get(ref.turnId);
	}
	return ref.messageIndex;
}

function getReferenceChunkIdentityKey(
	ref: Pick<Reference, "snippet" | "keyParagraph">,
): string | null {
	const snippet = ref.snippet?.trim();
	const keyParagraph = ref.keyParagraph?.trim();
	if (!snippet && !keyParagraph) {
		return null;
	}
	return JSON.stringify([snippet ?? null, keyParagraph ?? null]);
}

export function getReferenceIdentityKey(
	ref: Pick<
		Reference,
		| "url"
		| "toolCallId"
		| "turnId"
		| "messageIndex"
		| "snippet"
		| "keyParagraph"
	>,
): string {
	const ownerKey = ref.toolCallId ? `tool:${ref.toolCallId}` : "tool:none";
	const turnKey = ref.turnId
		? `turn:${ref.turnId}`
		: ref.messageIndex !== undefined
			? `index:${ref.messageIndex}`
			: "index:none";
	const chunkKey = getReferenceChunkIdentityKey(ref);
	return chunkKey
		? `${ownerKey}::${turnKey}::${ref.url}::chunk:${chunkKey}`
		: `${ownerKey}::${turnKey}::${ref.url}`;
}

export type GroundTruthItem = {
	id: string;
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
	/** Legacy compatibility projection derived from history when absent. */
	question?: string;
	/** ISO date string of the last review, when provided by the API. */
	reviewedAt?: string | null;
	/**
	 * Markdown instructions specific to this item/dataset.
	 * Rendered in a collapsible pane above the Question/Answer editors.
	 */
	curationInstructions?: string;
	/** ETag for optimistic concurrency control */
	_etag?: string;
};

// Helper functions for multi-turn support

const LEGACY_HOST_DELETE_GATES = [
	"stored-data audit completed",
	"caller audit completed",
	"import/export verification completed",
] as const;

export type LegacyHostDeleteGate = (typeof LEGACY_HOST_DELETE_GATES)[number];

export function getLegacyHostDeleteGates(): LegacyHostDeleteGate[] {
	return [...LEGACY_HOST_DELETE_GATES];
}

function normalizeRole(role: string): string {
	return role.trim().toLowerCase();
}

export function isUserRole(role: string): boolean {
	return normalizeRole(role) === "user";
}

export function isNonUserRole(role: string): boolean {
	return !isUserRole(role);
}

export function createConversationTurn(args: {
	role: string;
	content: string;
	turnId?: string;
	stepId?: string;
	expectedBehavior?: ExpectedBehavior[];
}): ConversationTurn {
	return {
		turnId: args.turnId || `turn_${Math.random().toString(36).slice(2, 10)}`,
		stepId: args.stepId,
		role: args.role,
		content: args.content,
		expectedBehavior: args.expectedBehavior,
	};
}

export function ensureConversationTurnIdentity(
	history?: ConversationTurn[],
): ConversationTurn[] {
	return (history || []).map((turn, index) => ({
		...turn,
		turnId: turn.turnId || turn.stepId || `turn_${index + 1}`,
		stepId: turn.stepId || turn.turnId || `step_${index + 1}`,
	}));
}

/**
 * Returns the last user message from history.
 */
export function getLastUserTurn(item: GroundTruthItem): string {
	if (!Array.isArray(item.history)) {
		return item.question || "";
	}
	const history = ensureConversationTurnIdentity(item.history);
	if (history.length === 0) {
		return "";
	}
	// Find the last user turn
	for (let i = history.length - 1; i >= 0; i--) {
		if (isUserRole(history[i].role)) {
			return history[i].content;
		}
	}
	return "";
}

/**
 * Returns the last agent message from history.
 * Non-user turns are treated as answer content.
 */
export function getLastAgentTurn(item: GroundTruthItem): string {
	if (!Array.isArray(item.history)) {
		return "";
	}
	const history = ensureConversationTurnIdentity(item.history);
	if (history.length === 0) {
		return "";
	}
	// Find the last non-user turn.
	for (let i = history.length - 1; i >= 0; i--) {
		if (isNonUserRole(history[i].role)) {
			return history[i].content;
		}
	}
	return "";
}

/**
 * Returns the total number of turns in the conversation
 */
export function getTurnCount(item: GroundTruthItem): number {
	return ensureConversationTurnIdentity(item.history).length;
}

/**
 * Checks if the item is using multi-turn mode
 */
export function isMultiTurn(item: GroundTruthItem): boolean {
	return ensureConversationTurnIdentity(item.history).length > 0;
}

/**
 * Returns a short preview string for queue display:
 * uses the first user turn from history.
 */
export function getQueuePreview(item: GroundTruthItem): string {
	if (!Array.isArray(item.history)) {
		return item.question || "(no message)";
	}
	const first = ensureConversationTurnIdentity(item.history).find((t) =>
		isUserRole(t.role),
	);
	return first?.content || "(no message)";
}

export function withDerivedLegacyFields(
	item: GroundTruthItem,
): GroundTruthItem {
	const history = Array.isArray(item.history)
		? ensureConversationTurnIdentity(item.history)
		: item.history;
	const derivedItem = {
		...item,
		history,
	};
	return {
		...derivedItem,
		question: getLastUserTurn(derivedItem),
	};
}

/**
 * Returns whether the item has any generic evidence data worth showing
 * in the evidence/trace panel (toolCalls, expectedTools, traceIds, metadata, feedback).
 */
export function hasEvidenceData(item: GroundTruthItem): boolean {
	return (
		(item.contextEntries?.length ?? 0) > 0 ||
		(item.toolCalls?.length ?? 0) > 0 ||
		item.expectedTools != null ||
		item.traceIds != null ||
		Object.keys(item.metadata ?? {}).length > 0 ||
		Object.keys(item.plugins ?? {}).length > 0 ||
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
