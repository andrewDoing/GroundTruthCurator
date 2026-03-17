import type { components } from "../api/generated";
import {
	createConversationTurn,
	ensureConversationTurnIdentity,
	type GroundTruthItem,
	getItemReferences,
	type PluginPayload,
	type Reference,
	type ToolCallRecord,
	withDerivedLegacyFields,
} from "../models/groundTruth";
import { urlToTitle } from "../models/utils";

const _RAG_COMPAT_KEY = "rag-compat";
const _REMOVED_COMPAT_PATCH_KEYS = [
	"synthQuestion",
	"editedQuestion",
	"answer",
	"refs",
	"totalReferences",
	"historyAnnotations",
	"contextUsedForGeneration",
	"contextSource",
	"modelUsedForGeneration",
	"semanticClusterNumber",
	"weight",
	"samplingBucket",
	"questionLength",
];

type ConversationTurn = NonNullable<GroundTruthItem["history"]>[number];
export type ApiReference = {
	url: string;
	title?: string | null;
	content?: string | null;
	keyExcerpt?: string | null;
	type?: string | null;
	bonus?: boolean;
	messageIndex?: number | null;
};
export type ApiHistoryEntry = components["schemas"]["HistoryEntry"] & {
	refs?: ApiReference[];
	expectedBehavior?: string[];
	turnId?: string;
	stepId?: string;
};
export type ApiGroundTruth = Omit<
	components["schemas"]["AgenticGroundTruthEntry-Output"],
	"history"
> & {
	tags?: string[];
	comment?: string | null;
	history?: ApiHistoryEntry[];
};

type StoredTurnIdentity = {
	turnId?: string;
	stepId?: string;
};

function hasOwnField(value: object, field: PropertyKey): boolean {
	return Object.hasOwn(value, field);
}

function sanitizeCompatDataForPatch(data: unknown): Record<string, unknown> {
	if (!data || typeof data !== "object" || Array.isArray(data)) {
		return {};
	}

	const sanitized = { ...(data as Record<string, unknown>) };
	for (const key of _REMOVED_COMPAT_PATCH_KEYS) {
		delete sanitized[key];
	}
	return sanitized;
}

function normalizeToolCalls(
	toolCalls: components["schemas"]["ToolCallRecord"][] | null | undefined,
): ToolCallRecord[] | undefined {
	if (!toolCalls?.length) {
		return undefined;
	}

	return toolCalls.map((toolCall) => ({
		...toolCall,
		arguments: toolCall.arguments ?? undefined,
	}));
}

function getStoredTurnIdentities(
	plugins: Record<string, PluginPayload>,
): StoredTurnIdentity[] {
	const turnIdentity = (
		plugins[_RAG_COMPAT_KEY]?.data as Record<string, unknown>
	)?.turnIdentity;
	return Array.isArray(turnIdentity)
		? (turnIdentity as StoredTurnIdentity[])
		: [];
}

export function groundTruthFromApi(
	api: ApiGroundTruth,
	providerId = "api",
): GroundTruthItem {
	const plugins: Record<string, PluginPayload> =
		api.plugins && Object.keys(api.plugins).length
			? (api.plugins as Record<string, PluginPayload>)
			: {};
	const compatData =
		(plugins[_RAG_COMPAT_KEY]?.data as Record<string, unknown> | undefined) ||
		{};
	const editedQuestion = compatData.editedQuestion;
	const synthQuestion = compatData.synthQuestion;
	const initialQuestion =
		(typeof editedQuestion === "string" && editedQuestion) ||
		(typeof synthQuestion === "string" && synthQuestion) ||
		"";
	const storedTurnIdentity = getStoredTurnIdentities(plugins);
	let history: GroundTruthItem["history"];
	let usedLegacyCompatHistory = false;
	const legacyRefs: Reference[] = [];
	let refIndex = 0;

	if (Array.isArray(api.history)) {
		history = new Array(api.history.length);

		for (let idx = 0; idx < api.history.length; idx++) {
			const h = api.history[idx];
			// Preserve free-form roles; map "assistant" to "agent" for backward compat.
			const role = h.role === "assistant" ? "agent" : h.role;
			const identity = storedTurnIdentity[idx];
			history[idx] = createConversationTurn({
				role,
				content: h.msg,
				turnId: h.turnId || identity?.turnId,
				stepId: h.stepId || identity?.stepId,
				expectedBehavior:
					h.expectedBehavior && h.expectedBehavior.length > 0
						? (h.expectedBehavior as ConversationTurn["expectedBehavior"])
						: undefined,
			});

			if (h.refs && h.refs.length > 0) {
				for (const r of h.refs) {
					legacyRefs.push({
						id: `ref_${refIndex++}`,
						title: r.title || (r.url ? urlToTitle(r.url) : undefined),
						url: r.url,
						snippet: r.content ?? undefined,
						keyParagraph: r.keyExcerpt ?? undefined,
						visitedAt: null,
						bonus: r.bonus === true,
						messageIndex: idx,
						turnId: history[idx]?.turnId,
					});
				}
			}
		}
	} else if (initialQuestion) {
		// Legacy single-turn compat payload: create initial history from plugin-owned fields
		const answer = compatData.answer;
		history = [
			createConversationTurn({
				role: "user",
				content: initialQuestion,
				turnId: storedTurnIdentity[0]?.turnId,
				stepId: storedTurnIdentity[0]?.stepId,
			}),
			createConversationTurn({
				role: "agent",
				content: typeof answer === "string" ? answer : "",
				turnId: storedTurnIdentity[1]?.turnId,
				stepId: storedTurnIdentity[1]?.stepId,
			}),
		];
		usedLegacyCompatHistory = true;
	}

	// Process plugin-owned compat refs for legacy payload migration
	const compatRefs = Array.isArray(compatData.references)
		? compatData.references
		: Array.isArray(compatData.refs)
			? compatData.refs
			: [];
	if (compatRefs.length > 0) {
		const messageIndex = usedLegacyCompatHistory ? 1 : undefined;
		const turnId =
			typeof messageIndex === "number"
				? history?.[messageIndex]?.turnId
				: undefined;

		for (const r of compatRefs) {
			if (!r || typeof r !== "object" || !("url" in r)) {
				continue;
			}
			const ref = r as ApiReference;
			legacyRefs.push({
				id: `ref_${refIndex++}`,
				title: ref.title || (ref.url ? urlToTitle(ref.url) : undefined),
				url: ref.url,
				snippet: ref.content ?? undefined,
				keyParagraph: ref.keyExcerpt ?? undefined,
				visitedAt: null,
				bonus: ref.bonus === true,
				messageIndex,
				turnId,
			});
		}
	}

	const existingReferences = (
		plugins[_RAG_COMPAT_KEY]?.data as Record<string, unknown> | undefined
	)?.references;
	const hasCanonicalReferences = Array.isArray(existingReferences);

	// When canonical references are absent but legacy refs were extracted, migrate them.
	if (!hasCanonicalReferences && legacyRefs.length > 0) {
		const existingPlugin = plugins[_RAG_COMPAT_KEY];
		plugins[_RAG_COMPAT_KEY] = {
			kind: _RAG_COMPAT_KEY,
			version: existingPlugin?.version || "1.0",
			data: {
				...(existingPlugin?.data || {}),
				references: legacyRefs.map((ref) => ({
					url: ref.url,
					title: ref.title,
					content: ref.snippet,
					keyExcerpt: ref.keyParagraph,
					bonus: ref.bonus ?? false,
					messageIndex: ref.turnId ? undefined : ref.messageIndex,
					turnId: ref.turnId,
					toolCallId: ref.toolCallId,
					visitedAt: ref.visitedAt ?? null,
				})),
			},
		};
	}

	const deleted = api.status === "deleted";

	return withDerivedLegacyFields({
		id: api.id,
		providerId,
		history: history ? ensureConversationTurnIdentity(history) : history,
		comment: api.comment ?? undefined,
		status:
			(deleted ? "draft" : (api.status as GroundTruthItem["status"])) ||
			("draft" as GroundTruthItem["status"]),
		deleted,
		tags: api.tags || [],
		manualTags: api.manualTags || [],
		computedTags: api.computedTags || [],
		reviewedAt: api.reviewedAt ?? null,
		// Generic schema fields — passed through from the API
		scenarioId: api.scenarioId || undefined,
		contextEntries:
			hasOwnField(api, "contextEntries") && Array.isArray(api.contextEntries)
				? api.contextEntries
				: undefined,
		toolCalls: normalizeToolCalls(api.toolCalls),
		expectedTools: api.expectedTools ?? undefined,
		feedback: api.feedback?.length ? api.feedback : undefined,
		metadata:
			api.metadata && Object.keys(api.metadata).length
				? (api.metadata as Record<string, unknown>)
				: undefined,
		plugins: Object.keys(plugins).length ? plugins : undefined,
		traceIds: api.traceIds ?? undefined,
		tracePayload:
			api.tracePayload && Object.keys(api.tracePayload).length
				? (api.tracePayload as Record<string, unknown>)
				: undefined,
		...({
			datasetName: api.datasetName,
			bucket: (api.bucket as string) || "0",
			_etag: api._etag,
		} as Record<string, unknown>),
	});
}

export function groundTruthToPatch(args: {
	item: GroundTruthItem;
}): Partial<ApiGroundTruth> {
	const item = withDerivedLegacyFields(args.item);
	const history = ensureConversationTurnIdentity(item.history);

	// Extract references from per-call plugin state
	const references = getItemReferences(item);

	const body: Partial<ApiGroundTruth> = {
		status: (item.deleted
			? "deleted"
			: item.status) as components["schemas"]["GroundTruthStatus"],
		manualTags: item.manualTags || [],
	};

	if (history.length > 0) {
		body.history = history.map((turn, idx) => {
			let turnRefs: ApiReference[] | undefined;
			if (turn.role !== "user") {
				const refsForTurn = references.filter(
					(r) => r.turnId === turn.turnId || r.messageIndex === idx,
				);
				if (refsForTurn.length > 0) {
					turnRefs = refsForTurn.map((r) => ({
						url: r.url,
						title: r.title || undefined,
						content: r.snippet || undefined,
						keyExcerpt: r.keyParagraph || undefined,
						bonus: !!r.bonus,
					}));
				}
			}

			// Map "agent" back to "assistant" for backward compat; preserve other free-form roles.
			const apiRole = turn.role === "agent" ? "assistant" : turn.role;

			return {
				role: apiRole,
				msg: turn.content,
				turnId: turn.turnId,
				stepId: turn.stepId,
				expectedBehavior: turn.expectedBehavior || undefined,
				...(turnRefs ? { refs: turnRefs } : {}),
			};
		});
	}

	if (typeof item.comment !== "undefined") {
		(body as Record<string, unknown>).comment = item.comment ?? null;
	}

	// Pass through generic fields when present
	if (
		hasOwnField(item, "contextEntries") &&
		Array.isArray(item.contextEntries)
	) {
		(body as Record<string, unknown>).contextEntries = item.contextEntries;
	}
	if (item.toolCalls?.length) {
		(body as Record<string, unknown>).toolCalls = item.toolCalls;
	}
	if (item.expectedTools) {
		(body as Record<string, unknown>).expectedTools = item.expectedTools;
	}
	if (item.feedback?.length) {
		(body as Record<string, unknown>).feedback = item.feedback;
	}
	if (item.metadata && Object.keys(item.metadata).length) {
		(body as Record<string, unknown>).metadata = item.metadata;
	}
	const plugins = { ...(item.plugins || {}) };
	const existingCompat = plugins[_RAG_COMPAT_KEY];
	const compatData = sanitizeCompatDataForPatch(existingCompat?.data);
	if (history.length > 0 || existingCompat) {
		plugins[_RAG_COMPAT_KEY] = {
			kind: _RAG_COMPAT_KEY,
			version: existingCompat?.version || "1.0",
			data: {
				...compatData,
				...(history.length > 0
					? {
							turnIdentity: history.map((turn) => ({
								turnId: turn.turnId,
								stepId: turn.stepId,
							})),
						}
					: {}),
			},
		};
	}
	if (Object.keys(plugins).length) {
		(body as Record<string, unknown>).plugins = plugins;
	}
	if (item.traceIds) {
		(body as Record<string, unknown>).traceIds = item.traceIds;
	}
	if (item.tracePayload && Object.keys(item.tracePayload).length) {
		(body as Record<string, unknown>).tracePayload = item.tracePayload;
	}

	return body;
}
