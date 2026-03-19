import type { components } from "../api/generated";
import {
	createConversationTurn,
	ensureConversationTurnIdentity,
	type GroundTruthItem,
	type PluginPayload,
	type ToolCallRecord,
	withDerivedLegacyFields,
} from "../models/groundTruth";
import { sanitizeCompatPluginForPatch } from "./ragCompatBoundary";

const _REMOVED_COMPAT_PATCH_KEYS = [
	"synthQuestion",
	"editedQuestion",
	"answer",
	"refs",
	"totalReferences",
	"retrievals",
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

function hasOwnField(value: object, field: PropertyKey): boolean {
	return Object.hasOwn(value, field);
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

export function groundTruthFromApi(
	api: ApiGroundTruth,
	providerId = "api",
): GroundTruthItem {
	const plugins: Record<string, PluginPayload> =
		api.plugins && Object.keys(api.plugins).length
			? (api.plugins as Record<string, PluginPayload>)
			: {};
	let history: GroundTruthItem["history"];

	if (Array.isArray(api.history)) {
		history = new Array(api.history.length);

		for (let idx = 0; idx < api.history.length; idx++) {
			const h = api.history[idx];
			history[idx] = createConversationTurn({
				role: h.role,
				content: h.msg,
				turnId: h.turnId,
				stepId: h.stepId,
				expectedBehavior:
					h.expectedBehavior && h.expectedBehavior.length > 0
						? (h.expectedBehavior as ConversationTurn["expectedBehavior"])
						: undefined,
			});
		}
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

	const body: Partial<ApiGroundTruth> = {
		status: (item.deleted
			? "deleted"
			: item.status) as components["schemas"]["GroundTruthStatus"],
		manualTags: item.manualTags || [],
	};

	if (history.length > 0) {
		body.history = history.map((turn) => {
			return {
				role: turn.role,
				msg: turn.content,
				turnId: turn.turnId,
				stepId: turn.stepId,
				expectedBehavior: turn.expectedBehavior || undefined,
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
	const plugins = sanitizeCompatPluginForPatch({
		plugins: item.plugins,
		removedKeys: _REMOVED_COMPAT_PATCH_KEYS,
		historyTurnIds: history.map((turn) => turn.turnId),
		indexByTurnId: new Map(
			history
				.map((turn, index) =>
					turn.turnId ? ([turn.turnId, index] as const) : null,
				)
				.filter((entry): entry is readonly [string, number] => entry !== null),
		),
	});
	if (plugins && Object.keys(plugins).length) {
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
