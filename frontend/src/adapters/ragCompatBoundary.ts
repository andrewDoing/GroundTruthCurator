import {
	type CompatPluginsMap,
	collectCanonicalReferencesFromCompatPlugins,
	getCompatReferencesFromData,
	getCompatRetrievalsFromData,
	retrievalsToCanonicalReferences,
	writeCompatPluginEnvelope,
} from "../models/ragCompatPayload";

const _RAG_COMPAT_KEY = "rag-compat";

type ReferenceLike = {
	id: string;
	title?: string;
	url: string;
	snippet?: string;
	visitedAt?: string | null;
	keyParagraph?: string;
	bonus?: boolean;
	messageIndex?: number;
	turnId?: string;
	toolCallId?: string;
};

export function collectReferencesFromCompat(args: {
	plugins: CompatPluginsMap | undefined;
	historyTurnIds: Array<string | undefined>;
	indexByTurnId: Map<string, number>;
}): ReferenceLike[] {
	const { plugins, historyTurnIds, indexByTurnId } = args;
	return collectCanonicalReferencesFromCompatPlugins({
		plugins,
		historyTurnIds,
		indexByTurnId,
	});
}

export function withCompatReferences(args: {
	plugins: CompatPluginsMap | undefined;
	refs: ReferenceLike[];
}): CompatPluginsMap {
	const { plugins, refs } = args;
	return writeCompatPluginEnvelope({ plugins, refs });
}

export function sanitizeCompatData(
	data: unknown,
	removedKeys: readonly string[],
	historyTurnIds: Array<string | undefined> = [],
	indexByTurnId: Map<string, number> = new Map(),
): Record<string, unknown> {
	if (!data || typeof data !== "object" || Array.isArray(data)) {
		return {};
	}
	const sanitized = { ...(data as Record<string, unknown>) };
	const canonicalRefs = getCompatReferencesFromData(sanitized);
	if (!canonicalRefs) {
		const retrievals = getCompatRetrievalsFromData(sanitized);
		if (retrievals) {
			const materialized = retrievalsToCanonicalReferences({
				retrievals,
				historyTurnIds,
				indexByTurnId,
			});
			if (materialized.length > 0) {
				sanitized.references = materialized;
			}
		}
	}
	for (const key of removedKeys) {
		delete sanitized[key];
	}
	delete sanitized.retrievals;
	return sanitized;
}

export function sanitizeCompatPluginForPatch(args: {
	plugins: CompatPluginsMap | undefined;
	removedKeys: readonly string[];
	historyTurnIds?: Array<string | undefined>;
	indexByTurnId?: Map<string, number>;
}): CompatPluginsMap | undefined {
	const { plugins, removedKeys, historyTurnIds, indexByTurnId } = args;
	if (!plugins) {
		return undefined;
	}
	const nextPlugins = { ...plugins };
	const existingCompat = nextPlugins[_RAG_COMPAT_KEY];
	if (!existingCompat) {
		return nextPlugins;
	}
	nextPlugins[_RAG_COMPAT_KEY] = {
		kind: _RAG_COMPAT_KEY,
		version: existingCompat.version || "1.0",
		data: sanitizeCompatData(
			existingCompat.data,
			removedKeys,
			historyTurnIds,
			indexByTurnId,
		),
	};
	return nextPlugins;
}
