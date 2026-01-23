import { client } from "../api/client";
import type { components } from "../api/generated";

type TagSchema = components["schemas"]["TagSchemaResponse"];

/** Response structure with separate manual and computed tags */
interface TagsWithComputed {
	manualTags: string[];
	computedTags: string[];
}

/**
 * Fetch tag schema from backend with retry logic.
 * Returns null if unable to fetch after retries.
 */
export async function fetchTagSchema(): Promise<TagSchema | null> {
	const maxRetries = 3;
	const initialRetryDelayMs = 200;

	for (let attempt = 1; attempt <= maxRetries; attempt++) {
		try {
			const { data, error } = await client.GET("/v1/tags/schema", {});
			if (error) {
				if (attempt === maxRetries) {
					console.warn("Failed to fetch tag schema after retries:", error);
					return null;
				}
				const delay = initialRetryDelayMs * 2 ** (attempt - 1);
				await new Promise((resolve) => setTimeout(resolve, delay));
				continue;
			}
			return data as TagSchema;
		} catch (err) {
			if (attempt === maxRetries) {
				console.warn("Failed to fetch tag schema after retries:", err);
				return null;
			}
			const delay = initialRetryDelayMs * 2 ** (attempt - 1);
			await new Promise((resolve) => setTimeout(resolve, delay));
		}
	}
	return null;
}

/**
 * Get the set of exclusive tag group names.
 * Fetches schema on-demand if not already loaded.
 */
async function getExclusiveGroups(): Promise<Set<string>> {
	// Try to ensure schema is loaded
	const schema = await fetchTagSchema();

	if (schema?.groups) {
		const exclusiveGroups = schema.groups
			.filter((g) => g.exclusive)
			.map((g) => g.name);
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

/**
 * Fetch tags with separate manual and computed arrays.
 * GET /v1/tags now returns { tags: [...], computedTags: [...] }
 */
export async function fetchTagsWithComputed(): Promise<TagsWithComputed> {
	try {
		const { data, error } = await client.GET("/v1/tags", {});
		if (error) throw error;
		const response = data as unknown as
			| { tags?: string[]; computedTags?: string[] }
			| undefined;
		const manualTags = [...(response?.tags ?? [])].sort((a, b) =>
			a.localeCompare(b),
		);
		const computedTags = [...(response?.computedTags ?? [])].sort((a, b) =>
			a.localeCompare(b),
		);
		return { manualTags, computedTags };
	} catch {
		// No-op; return empty
	}
	return { manualTags: [], computedTags: [] };
}

/**
 * Fetch all available tags (manual + computed merged).
 * For backward compatibility with existing callers.
 */
export async function fetchAvailableTags(): Promise<string[]> {
	const { manualTags, computedTags } = await fetchTagsWithComputed();
	const merged = [...new Set([...manualTags, ...computedTags])];
	return merged.sort((a, b) => a.localeCompare(b));
}

/** Add tags to the global tags collection. Returns the updated list. */
export async function addTags(tags: string[]): Promise<string[]> {
	const unique = Array.from(new Set(tags.map((t) => t.trim()).filter(Boolean)));
	if (!unique.length) return [];
	const { data, error } = await client.POST("/v1/tags", {
		body: {
			tags: unique,
		} as unknown as components["schemas"]["AddTagsRequest"],
	});
	if (error) throw error;
	const response = data as unknown as { tags?: string[] } | undefined;
	const list = response?.tags || [];
	return [...list].sort((a, b) => a.localeCompare(b));
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
}

/** Delete a custom tag definition */
export async function deleteTagDefinition(tagKey: string): Promise<void> {
	const { error } = await client.DELETE("/v1/tags/definitions/{tag_key}", {
		params: { path: { tag_key: tagKey } },
	});
	if (error) throw error;
}
