import { useCallback, useState } from "react";
import DEMO_MODE from "../config/demo";
import type { Reference } from "../models/groundTruth";
import { mockAiSearch, searchReferences } from "../services/search";

type ReferencesSearchApi = {
	query: string;
	setQuery: (q: string) => void;
	searching: boolean;
	searchResults: Reference[];
	runSearch: () => Promise<void>;
	clearResults: () => void;
};

export function useReferencesSearch(options: {
	getSeedQuery: () => string | undefined;
}): ReferencesSearchApi {
	const { getSeedQuery } = options;
	const [query, setQuery] = useState("");
	const [searching, setSearching] = useState(false);
	const [searchResults, setSearchResults] = useState<Reference[]>([]);

	const runSearch = useCallback(async () => {
		const q = (query || getSeedQuery() || "").trim();
		if (!q) {
			setSearchResults([]);
			return;
		}
		setSearching(true);
		try {
			const results = DEMO_MODE
				? await mockAiSearch(q)
				: await searchReferences(q, 10);
			setSearchResults(results);
		} finally {
			setSearching(false);
		}
	}, [query, getSeedQuery]);

	const clearResults = useCallback(() => setSearchResults([]), []);

	return { query, setQuery, searching, searchResults, runSearch, clearResults };
}
