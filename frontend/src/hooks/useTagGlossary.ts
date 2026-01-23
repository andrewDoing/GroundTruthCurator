import { useEffect, useState } from "react";
import type { components } from "../api/generated";

type GlossaryResponse = components["schemas"]["GlossaryResponse"];

export interface TagGlossary {
	[tagKey: string]: string | undefined;
}

/**
 * Fetches the tag glossary from the API and transforms it into a lookup map
 * of tag key -> description.
 */
export function useTagGlossary() {
	const [glossary, setGlossary] = useState<TagGlossary>({});
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);

	useEffect(() => {
		let cancelled = false;

		async function fetchGlossary() {
			try {
				setLoading(true);
				const response = await fetch("/v1/tags/glossary");
				if (!response.ok) {
					throw new Error("Failed to fetch tag glossary");
				}
				const data: GlossaryResponse = await response.json();

				if (cancelled) return;

				// Build lookup map: tag key -> description
				const glossaryMap: TagGlossary = {};
				for (const group of data.groups || []) {
					for (const tag of group.tags || []) {
						if (tag.key && tag.description) {
							glossaryMap[tag.key] = tag.description;
						}
					}
				}

				setGlossary(glossaryMap);
				setError(null);
			} catch (err) {
				if (!cancelled) {
					setError(err instanceof Error ? err : new Error(String(err)));
				}
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		}

		fetchGlossary();

		return () => {
			cancelled = true;
		};
	}, []);

	return { glossary, loading, error };
}

/**
 * Returns the description for a given tag key.
 */
export function useTagDescription(tagKey: string): string | undefined {
	const { glossary } = useTagGlossary();
	return glossary[tagKey];
}
