import type { components } from "../api/generated";
import type { GroundTruthItem, Reference } from "../models/groundTruth";
import { urlToTitle } from "../models/utils";

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
	const refs: Reference[] = [];
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
					refs.push({
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
			refs.push({
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

	const question = api.editedQuestion || api.synthQuestion || "";
	const deleted = api.status === "deleted";

	return {
		id: api.id,
		providerId,
		question,
		answer: api.answer ?? "",
		history,
		comment: api.comment ?? undefined,
		references: refs,
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
		plugins:
			api.plugins && Object.keys(api.plugins).length
				? (api.plugins as Record<
						string,
						import("../models/groundTruth").PluginPayload
					>)
				: undefined,
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

	const hadLegacyTopLevelRefs =
		!!originalApi &&
		!originalApi.history &&
		(originalApi.refs?.length || 0) > 0;

	let topLevelRefs: ApiReference[] = [];
	if (hadLegacyTopLevelRefs) {
		topLevelRefs = (item.references || [])
			.filter((r) => r.messageIndex === 1 || r.messageIndex === undefined)
			.map((r) => ({
				url: r.url,
				title: r.title || undefined,
				keyExcerpt: r.keyParagraph || undefined,
				content: r.snippet || undefined,
				bonus: !!r.bonus,
			}));
	} else {
		topLevelRefs = (item.references || [])
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
				const refsForTurn = (item.references || []).filter(
					(r) => r.messageIndex === idx,
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
	if (item.traceIds) {
		(body as Record<string, unknown>).traceIds = item.traceIds;
	}
	if (item.tracePayload && Object.keys(item.tracePayload).length) {
		(body as Record<string, unknown>).tracePayload = item.tracePayload;
	}

	return body;
}
