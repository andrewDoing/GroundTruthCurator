import { client } from "../api/client";
import type { components } from "../api/generated";

type TagSchema = components["schemas"]["TagSchemaResponse"];
type GlossaryResponse = components["schemas"]["GlossaryResponse"];

/** Response structure with separate manual and computed tags */
export interface TagsWithComputed {
	manualTags: string[];
	computedTags: string[];
}

interface TagMetadataSnapshot extends TagsWithComputed {
	allTags: string[];
	loading: boolean;
	error: Error | null;
}

export interface TagGlossary {
	[tagKey: string]: string | undefined;
}

const EMPTY_TAGS: TagsWithComputed = {
	manualTags: [],
	computedTags: [],
};

let tagsCache: TagsWithComputed | null = null;
let tagsInFlight: Promise<TagsWithComputed> | null = null;
let tagsLoading = false;
let tagsError: Error | null = null;
const tagListeners = new Set<() => void>();
let tagSnapshot: TagMetadataSnapshot = buildTagSnapshot();

let schemaCache: TagSchema | null = null;
let schemaInFlight: Promise<TagSchema | null> | null = null;

let glossaryCache: GlossaryResponse | null = null;
let glossaryInFlight: Promise<GlossaryResponse> | null = null;

function normalizeError(error: unknown, fallback: string): Error {
	if (error instanceof Error) {
		return error;
	}

	if (typeof error === "string" && error.trim()) {
		return new Error(error);
	}

	return new Error(fallback);
}

function sortTags(tags: string[]): string[] {
	return [...tags].sort((a, b) => a.localeCompare(b));
}

function normalizeTags(response?: {
	tags?: string[];
	computedTags?: string[];
}): TagsWithComputed {
	return {
		manualTags: sortTags(response?.tags ?? []),
		computedTags: sortTags(response?.computedTags ?? []),
	};
}

function getAllTags(tags: TagsWithComputed): string[] {
	return sortTags([...new Set([...tags.manualTags, ...tags.computedTags])]);
}

function buildTagSnapshot(): TagMetadataSnapshot {
	const cachedTags = tagsCache ?? EMPTY_TAGS;
	return {
		...cachedTags,
		allTags: getAllTags(cachedTags),
		loading: tagsLoading,
		error: tagsError,
	};
}

function updateTagSnapshot() {
	tagSnapshot = buildTagSnapshot();
	for (const listener of tagListeners) {
		listener();
	}
}

async function requestTagsWithComputed(): Promise<TagsWithComputed> {
	const { data, error } = await client.GET("/v1/tags", {});
	if (error) {
		throw normalizeError(error, "Failed to fetch tags");
	}

	const response = data as
		| { tags?: string[]; computedTags?: string[] }
		| undefined;
	return normalizeTags(response);
}

async function requestTagSchemaWithRetry(): Promise<TagSchema | null> {
	const maxRetries = 3;
	const initialRetryDelayMs = 200;

	for (let attempt = 1; attempt <= maxRetries; attempt++) {
		try {
			const { data, error } = await client.GET("/v1/tags/schema", {});
			if (error) {
				throw error;
			}

			return data as TagSchema;
		} catch (error) {
			if (attempt === maxRetries) {
				console.warn("Failed to fetch tag schema after retries:", error);
				return null;
			}

			const delay = initialRetryDelayMs * 2 ** (attempt - 1);
			await new Promise((resolve) => setTimeout(resolve, delay));
		}
	}

	return null;
}

export function subscribeToTagMetadata(listener: () => void) {
	tagListeners.add(listener);
	return () => {
		tagListeners.delete(listener);
	};
}

export function getTagMetadataSnapshot(): TagMetadataSnapshot {
	return tagSnapshot;
}

/**
 * Fetch tags with separate manual and computed arrays.
 * GET /v1/tags now returns { tags: [...], computedTags: [...] }
 */
export async function fetchTagsWithComputed(options?: {
	force?: boolean;
}): Promise<TagsWithComputed> {
	const force = options?.force ?? false;

	if (!force && tagsCache) {
		return tagsCache;
	}

	if (tagsInFlight) {
		return tagsInFlight;
	}

	tagsLoading = true;
	tagsError = null;
	updateTagSnapshot();

	tagsInFlight = requestTagsWithComputed()
		.then((tags) => {
			tagsCache = tags;
			tagsError = null;
			return tags;
		})
		.catch((error) => {
			tagsError = normalizeError(error, "Failed to fetch tags");
			return tagsCache ?? EMPTY_TAGS;
		})
		.finally(() => {
			tagsLoading = false;
			tagsInFlight = null;
			updateTagSnapshot();
		});

	return tagsInFlight;
}

export function ensureTagCached(tag: string) {
	const normalizedTag = tag.trim();
	if (!normalizedTag) {
		return;
	}

	const current = tagsCache ?? EMPTY_TAGS;
	if (
		current.manualTags.includes(normalizedTag) ||
		current.computedTags.includes(normalizedTag)
	) {
		return;
	}

	tagsCache = {
		manualTags: sortTags([...current.manualTags, normalizedTag]),
		computedTags: current.computedTags,
	};
	tagsError = null;
	updateTagSnapshot();
}

/**
 * Fetch all available tags (manual + computed merged).
 * For backward compatibility with existing callers.
 */
export async function fetchAvailableTags(options?: {
	force?: boolean;
}): Promise<string[]> {
	const tags = await fetchTagsWithComputed(options);
	return getAllTags(tags);
}

/**
 * Fetch tag schema from backend with retry logic.
 * Returns null if unable to fetch after retries.
 */
export async function fetchTagSchema(options?: {
	force?: boolean;
}): Promise<TagSchema | null> {
	const force = options?.force ?? false;

	if (!force && schemaCache) {
		return schemaCache;
	}

	if (schemaInFlight) {
		return schemaInFlight;
	}

	schemaInFlight = requestTagSchemaWithRetry()
		.then((schema) => {
			if (schema) {
				schemaCache = schema;
			}
			return schema;
		})
		.finally(() => {
			schemaInFlight = null;
		});

	return schemaInFlight;
}

/**
 * Get the set of exclusive tag group names.
 * Fetches schema on-demand if not already loaded.
 */
async function getExclusiveGroups(): Promise<Set<string>> {
	const schema = await fetchTagSchema();

	if (schema?.groups) {
		const exclusiveGroups = schema.groups
			.filter((group) => group.exclusive)
			.map((group) => group.name);
		return new Set(exclusiveGroups);
	}

	throw new Error(
		"Tag schema not available. Please check your connection and refresh the page.",
	);
}

/**
 * Validate that no exclusive tag group has multiple values selected.
 * Asynchronous to allow on-demand schema loading.
 */
export async function validateExclusiveTags(
	tags: string[],
): Promise<string | null> {
	const exclusiveGroups = await getExclusiveGroups();
	const byGroup = new Map<string, string[]>();

	for (const tag of tags) {
		const colonIndex = tag.indexOf(":");
		if (colonIndex === -1) continue;

		const group = tag.substring(0, colonIndex);
		const value = tag.substring(colonIndex + 1);

		if (exclusiveGroups.has(group)) {
			if (!byGroup.has(group)) {
				byGroup.set(group, []);
			}
			byGroup.get(group)?.push(value);
		}
	}

	for (const [group, values] of byGroup.entries()) {
		if (values.length > 1) {
			return `Group '${group}' is exclusive; only one value allowed, got: ${values.sort().join(", ")}`;
		}
	}

	return null;
}

export async function fetchTagGlossary(options?: {
	force?: boolean;
}): Promise<GlossaryResponse> {
	const force = options?.force ?? false;

	if (!force && glossaryCache) {
		return glossaryCache;
	}

	if (glossaryInFlight) {
		return glossaryInFlight;
	}

	glossaryInFlight = client
		.GET("/v1/tags/glossary", {})
		.then(({ data, error }) => {
			if (error) {
				throw normalizeError(error, "Failed to fetch tag glossary");
			}

			const glossary = data as GlossaryResponse;
			glossaryCache = glossary;
			return glossary;
		})
		.finally(() => {
			glossaryInFlight = null;
		});

	return glossaryInFlight;
}

export function buildTagGlossaryMap(glossary: GlossaryResponse): TagGlossary {
	const glossaryMap: TagGlossary = {};

	for (const group of glossary.groups || []) {
		for (const tag of group.tags || []) {
			if (tag.key && tag.description) {
				glossaryMap[tag.key] = tag.description;
			}
		}
	}

	return glossaryMap;
}

export function clearTagGlossaryCache() {
	glossaryCache = null;
	glossaryInFlight = null;
}

/** Add tags to the global tags collection. Returns the updated list. */
export async function addTags(tags: string[]): Promise<string[]> {
	const unique = Array.from(
		new Set(tags.map((tag) => tag.trim()).filter(Boolean)),
	);
	if (!unique.length) return [];

	const { data, error } = await client.POST("/v1/tags", {
		body: {
			tags: unique,
		} as unknown as components["schemas"]["AddTagsRequest"],
	});
	if (error) throw error;

	const response = data as unknown as { tags?: string[] } | undefined;
	const manualTags = sortTags(response?.tags || []);
	tagsCache = {
		manualTags,
		computedTags: tagsCache?.computedTags ?? [],
	};
	tagsError = null;
	updateTagSnapshot();

	return manualTags;
}

/** Create or update a custom tag definition */
export async function createTagDefinition(
	tagKey: string,
	description: string,
): Promise<void> {
	const { error } = await client.POST("/v1/tags/definitions", {
		body: {
			tag_key: tagKey,
			description,
		} as unknown as components["schemas"]["TagDefinitionRequest"],
	});
	if (error) throw error;
	clearTagGlossaryCache();
}

/** Delete a custom tag definition */
export async function deleteTagDefinition(tagKey: string): Promise<void> {
	const { error } = await client.DELETE("/v1/tags/definitions/{tag_key}", {
		params: { path: { tag_key: tagKey } },
	});
	if (error) throw error;
	clearTagGlossaryCache();
}
