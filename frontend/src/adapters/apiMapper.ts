import type { components } from "../api/generated";
import type {
	GroundTruthItem,
	PluginPayload,
	Reference,
} from "../models/groundTruth";
import { urlToTitle } from "../models/utils";

const _RAG_COMPAT_KEY = "rag-compat";
const _UNASSOCIATED_KEY = "_unassociated";

type RetrievalBucket = {
	candidates: Array<{
		url: string;
		title?: string;
		chunk?: string;
		relevance?: string;
		toolCallId?: string;
		messageIndex?: number;
		keyParagraph?: string;
		bonus?: boolean;
	}>;
};
type RetrievalsMap = Record<string, RetrievalBucket>;

type ConversationTurn = NonNullable<GroundTruthItem["history"]>[number];
export type ApiHistoryEntry = components["schemas"]["HistoryEntry"] & {
	refs?: components["schemas"]["Reference"][];
	expectedBehavior?: string[];
};
export type ApiGroundTruth =
	components["schemas"]["AgenticGroundTruthEntry-Output"] & {
		synthQuestion?: string | null;
		editedQuestion?: string | null;
		answer?: string | null;
		refs?: components["schemas"]["Reference"][];
		totalReferences?: number;
		tags?: string[];
		comment?: string | null;
	} & Omit<
			components["schemas"]["AgenticGroundTruthEntry-Output"],
			"history"
		> & {
			history?: ApiHistoryEntry[];
		};
export type ApiReference = components["schemas"]["Reference"];

export function groundTruthFromApi(
	api: ApiGroundTruth,
	providerId = "api",
): GroundTruthItem {
	let history: GroundTruthItem["history"];
	const legacyRefs: Reference[] = [];
	let refIndex = 0;

	if (api.history && api.history.length > 0) {
		history = new Array(api.history.length);

		for (let idx = 0; idx < api.history.length; idx++) {
			const h = api.history[idx];
			// Preserve free-form roles; map "assistant" to "agent" for backward compat.
			const role = h.role === "assistant" ? "agent" : h.role;
			history[idx] = {
				role,
				content: h.msg,
				expectedBehavior:
					h.expectedBehavior && h.expectedBehavior.length > 0
						? (h.expectedBehavior as ConversationTurn["expectedBehavior"])
						: undefined,
			};

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
					});
				}
			}
		}
	} else {
		// Legacy single-turn item: create initial history from synthQuestion/editedQuestion
		const initialQuestion = api.editedQuestion || api.synthQuestion || "";
		if (initialQuestion) {
			history = [
				{ role: "user" as const, content: initialQuestion },
				{ role: "agent" as const, content: api.answer || "" },
			];
		}
	}

	// Process top-level refs (backward compatibility)
	if (api.refs && api.refs.length > 0) {
		const wasLegacyConversion = !api.history || api.history.length === 0;
		const messageIndex = wasLegacyConversion ? 1 : undefined;

		for (const r of api.refs) {
			legacyRefs.push({
				id: `ref_${refIndex++}`,
				title: r.title || (r.url ? urlToTitle(r.url) : undefined),
				url: r.url,
				snippet: r.content ?? undefined,
				keyParagraph: r.keyExcerpt ?? undefined,
				visitedAt: null,
				bonus: r.bonus === true,
				messageIndex,
			});
		}
	}

	// Build plugin data — merge existing plugins with per-call retrieval state
	const plugins: Record<string, PluginPayload> =
		api.plugins && Object.keys(api.plugins).length
			? (api.plugins as Record<string, PluginPayload>)
			: {};

	// Read per-call retrieval state from plugin data if it already exists
	const existingRetrievals = (
		plugins[_RAG_COMPAT_KEY]?.data as Record<string, unknown> | undefined
	)?.retrievals;
	const hasPerCallState =
		existingRetrievals &&
		typeof existingRetrievals === "object" &&
		!Array.isArray(existingRetrievals) &&
		Object.keys(existingRetrievals as Record<string, unknown>).length > 0;

	// When no per-call state exists but legacy refs were extracted, migrate them
	if (!hasPerCallState && legacyRefs.length > 0) {
		const retrievals: RetrievalsMap = {};
		for (const ref of legacyRefs) {
			const key = ref.toolCallId || _UNASSOCIATED_KEY;
			if (!retrievals[key]) {
				retrievals[key] = { candidates: [] };
			}
			retrievals[key].candidates.push({
				url: ref.url,
				title: ref.title,
				chunk: ref.snippet,
				relevance: undefined,
				toolCallId: ref.toolCallId,
				messageIndex: ref.messageIndex,
				keyParagraph: ref.keyParagraph,
				bonus: ref.bonus,
			});
		}

		const existingPlugin = plugins[_RAG_COMPAT_KEY];
		plugins[_RAG_COMPAT_KEY] = {
			kind: _RAG_COMPAT_KEY,
			version: existingPlugin?.version || "1.0",
			data: { ...(existingPlugin?.data || {}), retrievals },
		};
	}

	const question = api.editedQuestion || api.synthQuestion || "";
	const deleted = api.status === "deleted";

	return {
		id: api.id,
		providerId,
		question,
		answer: api.answer ?? "",
		history,
		comment: api.comment ?? undefined,
		status:
			(deleted ? "draft" : (api.status as GroundTruthItem["status"])) ||
			("draft" as GroundTruthItem["status"]),
		deleted,
		tags: api.tags || [],
		manualTags: api.manualTags || [],
		computedTags: api.computedTags || [],
		reviewedAt: api.reviewedAt ?? null,
		totalReferences: api.totalReferences,
		// Generic schema fields — passed through from the API
		scenarioId: api.scenarioId || undefined,
		contextEntries: api.contextEntries?.length ? api.contextEntries : undefined,
		toolCalls: api.toolCalls?.length ? api.toolCalls : undefined,
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
	};
}

export function groundTruthToPatch(args: {
	item: GroundTruthItem;
	originalApi?: ApiGroundTruth;
}): Partial<ApiGroundTruth> {
	const { item, originalApi } = args;

	// Extract references from per-call plugin state
	const references = getItemReferencesFromPlugins(item);

	const hadLegacyTopLevelRefs =
		!!originalApi &&
		!originalApi.history &&
		(originalApi.refs?.length || 0) > 0;

	let topLevelRefs: ApiReference[] = [];
	if (hadLegacyTopLevelRefs) {
		topLevelRefs = references
			.filter((r) => r.messageIndex === 1 || r.messageIndex === undefined)
			.map((r) => ({
				url: r.url,
				title: r.title || undefined,
				keyExcerpt: r.keyParagraph || undefined,
				content: r.snippet || undefined,
				bonus: !!r.bonus,
			}));
	} else {
		topLevelRefs = references
			.filter((r) => r.messageIndex === undefined)
			.map((r) => ({
				url: r.url,
				title: r.title || undefined,
				keyExcerpt: r.keyParagraph || undefined,
				content: r.snippet || undefined,
				bonus: !!r.bonus,
			}));
	}

	const body: Partial<ApiGroundTruth> = {
		status: (item.deleted
			? "deleted"
			: item.status) as components["schemas"]["GroundTruthStatus"],
		answer: item.answer,
		editedQuestion: item.question,
		refs: topLevelRefs,
		manualTags: item.manualTags || [],
	};

	if (item.history && item.history.length > 0) {
		body.history = item.history.map((turn, idx) => {
			let turnRefs: ApiReference[] | undefined;
			if (turn.role !== "user") {
				const refsForTurn = references.filter((r) => r.messageIndex === idx);
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
				expectedBehavior: turn.expectedBehavior || undefined,
				...(turnRefs ? { refs: turnRefs } : {}),
			};
		});
	}

	if (typeof item.comment !== "undefined") {
		(body as Record<string, unknown>).comment = item.comment ?? null;
	}

	// Pass through generic fields when present
	if (item.contextEntries?.length) {
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
	if (item.plugins && Object.keys(item.plugins).length) {
		(body as Record<string, unknown>).plugins = item.plugins;
	}
	if (item.traceIds) {
		(body as Record<string, unknown>).traceIds = item.traceIds;
	}
	if (item.tracePayload && Object.keys(item.tracePayload).length) {
		(body as Record<string, unknown>).tracePayload = item.tracePayload;
	}

	return body;
}

/**
 * Extract references from per-call plugin state.
 * Used internally by the patch mapper and externally by UI components.
 */
function getItemReferencesFromPlugins(item: GroundTruthItem): Reference[] {
	const data = item.plugins?.[_RAG_COMPAT_KEY]?.data as
		| Record<string, unknown>
		| undefined;
	if (!data) return [];

	const retrievals = data.retrievals;
	if (
		!retrievals ||
		typeof retrievals !== "object" ||
		Array.isArray(retrievals)
	) {
		return [];
	}

	const refs: Reference[] = [];
	let refIndex = 0;
	for (const [toolCallId, bucket] of Object.entries(
		retrievals as Record<
			string,
			{ candidates?: Array<Record<string, unknown>> }
		>,
	)) {
		if (!bucket?.candidates) continue;
		for (const c of bucket.candidates) {
			refs.push({
				id: `ref_${refIndex++}`,
				title: (c.title as string) || undefined,
				url: (c.url as string) || "",
				snippet: (c.chunk as string) || undefined,
				keyParagraph: (c.keyParagraph as string) || undefined,
				visitedAt: (c.visitedAt as string) || null,
				bonus: (c.bonus as boolean) || false,
				messageIndex: c.messageIndex as number | undefined,
				toolCallId: toolCallId !== _UNASSOCIATED_KEY ? toolCallId : undefined,
			});
		}
	}
	return refs;
}
