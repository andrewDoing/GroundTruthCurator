const _RAG_COMPAT_KEY = "rag-compat";
const _UNASSOCIATED_KEY = "_unassociated";

export type CompatPluginPayload = {
	kind: string;
	version: string;
	data?: Record<string, unknown>;
};

export type CompatPluginsMap = Record<string, CompatPluginPayload>;

export type CompatReferencePayload = {
	url: string;
	title?: string;
	content?: string;
	keyExcerpt?: string;
	bonus?: boolean;
	messageIndex?: number;
	turnId?: string;
	toolCallId?: string;
	visitedAt?: string | null;
};

export type CanonicalReferencePayload = {
	id: string;
	url: string;
	title?: string;
	snippet?: string;
	visitedAt?: string | null;
	keyParagraph?: string;
	bonus?: boolean;
	messageIndex?: number;
	turnId?: string;
	toolCallId?: string;
};

export type RetrievalCandidatePayload = {
	url: string;
	title?: string;
	chunk?: string;
	relevance?: string;
	toolCallId?: string | null;
	messageIndex?: number;
	turnId?: string;
	keyParagraph?: string;
	bonus?: boolean;
	visitedAt?: string | null;
};

export type RetrievalBucketPayload = {
	candidates: RetrievalCandidatePayload[];
};

export type RetrievalsMap = Record<string, RetrievalBucketPayload>;

function asObjectRecord(value: unknown): Record<string, unknown> | undefined {
	if (!value || typeof value !== "object" || Array.isArray(value)) {
		return undefined;
	}
	return value as Record<string, unknown>;
}

export function getCompatData(
	plugins: CompatPluginsMap | undefined,
): Record<string, unknown> | undefined {
	return asObjectRecord(plugins?.[_RAG_COMPAT_KEY]?.data);
}

export function getCompatReferencesFromData(
	data: Record<string, unknown> | undefined,
): CompatReferencePayload[] | undefined {
	const references = data?.references;
	if (!Array.isArray(references)) {
		return undefined;
	}
	return references as CompatReferencePayload[];
}

export function getCompatReferencesFromPlugins(
	plugins: CompatPluginsMap | undefined,
): CompatReferencePayload[] | undefined {
	return getCompatReferencesFromData(getCompatData(plugins));
}

export function getCompatRetrievalsFromData(
	data: Record<string, unknown> | undefined,
): RetrievalsMap | undefined {
	const retrievals = data?.retrievals;
	if (
		retrievals &&
		typeof retrievals === "object" &&
		!Array.isArray(retrievals)
	) {
		return retrievals as RetrievalsMap;
	}
	return undefined;
}

export function getCompatRetrievalsFromPlugins(
	plugins: CompatPluginsMap | undefined,
): RetrievalsMap | undefined {
	return getCompatRetrievalsFromData(getCompatData(plugins));
}

export function retrievalsToCanonicalReferences(args: {
	retrievals: RetrievalsMap;
	historyTurnIds: Array<string | undefined>;
	indexByTurnId: Map<string, number>;
}): CompatReferencePayload[] {
	const { retrievals, historyTurnIds, indexByTurnId } = args;
	const refs: CompatReferencePayload[] = [];
	for (const [toolCallId, bucket] of Object.entries(retrievals)) {
		if (!bucket?.candidates) continue;
		for (const candidate of bucket.candidates) {
			if (!candidate?.url) continue;
			const storedTurnId = candidate.turnId;
			const resolvedMessageIndex =
				storedTurnId && indexByTurnId.has(storedTurnId)
					? indexByTurnId.get(storedTurnId)
					: candidate.messageIndex;
			const resolvedTurnId =
				storedTurnId ||
				(typeof resolvedMessageIndex === "number"
					? historyTurnIds[resolvedMessageIndex]
					: undefined);
			refs.push({
				url: candidate.url,
				title: candidate.title,
				content: candidate.chunk,
				keyExcerpt: candidate.keyParagraph,
				bonus: candidate.bonus ?? false,
				messageIndex: resolvedTurnId ? undefined : resolvedMessageIndex,
				turnId: resolvedTurnId,
				toolCallId:
					toolCallId !== _UNASSOCIATED_KEY
						? toolCallId
						: candidate.toolCallId || undefined,
				visitedAt: candidate.visitedAt ?? null,
			});
		}
	}
	return refs;
}

export function compatReferencesToCanonicalPayload(args: {
	references: CompatReferencePayload[];
	historyTurnIds: Array<string | undefined>;
	indexByTurnId: Map<string, number>;
}): CanonicalReferencePayload[] {
	const { references, historyTurnIds, indexByTurnId } = args;
	return references
		.filter((ref): ref is CompatReferencePayload => !!ref?.url)
		.map((ref, index) => {
			const resolvedMessageIndex =
				ref.turnId && indexByTurnId.has(ref.turnId)
					? indexByTurnId.get(ref.turnId)
					: ref.messageIndex;
			const resolvedTurnId =
				ref.turnId ||
				(typeof resolvedMessageIndex === "number"
					? historyTurnIds[resolvedMessageIndex]
					: undefined);
			return {
				id: `ref_${index}`,
				title: ref.title,
				url: ref.url,
				snippet: ref.content,
				visitedAt: ref.visitedAt ?? null,
				keyParagraph: ref.keyExcerpt,
				bonus: ref.bonus ?? false,
				messageIndex: resolvedMessageIndex,
				turnId: resolvedTurnId,
				toolCallId: ref.toolCallId,
			};
		});
}

export function collectCanonicalReferencesFromCompatData(args: {
	data: Record<string, unknown> | undefined;
	historyTurnIds: Array<string | undefined>;
	indexByTurnId: Map<string, number>;
}): CanonicalReferencePayload[] {
	const { data, historyTurnIds, indexByTurnId } = args;
	const canonicalRefs = getCompatReferencesFromData(data);
	if (canonicalRefs) {
		return compatReferencesToCanonicalPayload({
			references: canonicalRefs,
			historyTurnIds,
			indexByTurnId,
		});
	}

	const retrievals = getCompatRetrievalsFromData(data);
	if (!retrievals) {
		return [];
	}
	return retrievalsToCanonicalReferences({
		retrievals,
		historyTurnIds,
		indexByTurnId,
	}).map((ref, index) => ({
		id: `ref_${index}`,
		title: ref.title,
		url: ref.url,
		snippet: ref.content,
		visitedAt: ref.visitedAt ?? null,
		keyParagraph: ref.keyExcerpt,
		bonus: ref.bonus ?? false,
		messageIndex: ref.turnId ? undefined : ref.messageIndex,
		turnId: ref.turnId,
		toolCallId: ref.toolCallId,
	}));
}

export function collectCanonicalReferencesFromCompatPlugins(args: {
	plugins: CompatPluginsMap | undefined;
	historyTurnIds: Array<string | undefined>;
	indexByTurnId: Map<string, number>;
}): CanonicalReferencePayload[] {
	const { plugins, historyTurnIds, indexByTurnId } = args;
	return collectCanonicalReferencesFromCompatData({
		data: getCompatData(plugins),
		historyTurnIds,
		indexByTurnId,
	});
}

export function serializeCanonicalReferences(
	refs: Array<
		Pick<
			CanonicalReferencePayload,
			| "url"
			| "title"
			| "snippet"
			| "keyParagraph"
			| "bonus"
			| "messageIndex"
			| "turnId"
			| "toolCallId"
			| "visitedAt"
		>
	>,
): CompatReferencePayload[] {
	return refs.map((ref) => ({
		url: ref.url,
		title: ref.title,
		content: ref.snippet,
		keyExcerpt: ref.keyParagraph,
		bonus: ref.bonus ?? false,
		messageIndex: ref.turnId ? undefined : ref.messageIndex,
		turnId: ref.turnId,
		toolCallId: ref.toolCallId,
		visitedAt: ref.visitedAt ?? null,
	}));
}

export function writeCompatPluginEnvelope(args: {
	plugins: CompatPluginsMap | undefined;
	refs: Array<
		Pick<
			CanonicalReferencePayload,
			| "url"
			| "title"
			| "snippet"
			| "keyParagraph"
			| "bonus"
			| "messageIndex"
			| "turnId"
			| "toolCallId"
			| "visitedAt"
		>
	>;
}): CompatPluginsMap {
	const { plugins, refs } = args;
	const references = serializeCanonicalReferences(refs);
	const nextPlugins = { ...(plugins || {}) };
	const existingCompat = nextPlugins[_RAG_COMPAT_KEY];
	const existingData =
		existingCompat?.data &&
		typeof existingCompat.data === "object" &&
		!Array.isArray(existingCompat.data)
			? existingCompat.data
			: {};
	const { retrievals: _deprecatedRetrievals, ...restData } = existingData;

	nextPlugins[_RAG_COMPAT_KEY] = {
		kind: _RAG_COMPAT_KEY,
		version: existingCompat?.version || "1.0",
		data: { ...restData, references },
	};
	return nextPlugins;
}
