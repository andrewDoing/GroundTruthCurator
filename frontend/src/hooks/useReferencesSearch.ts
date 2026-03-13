import { useCallback, useEffect, useRef, useState } from "react";
import { shouldUseDemoProvider } from "../config/demo";
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
	const activeControllerRef = useRef<AbortController | null>(null);
	const requestIdRef = useRef(0);

	useEffect(() => {
		return () => {
			activeControllerRef.current?.abort();
		};
	}, []);

	const runSearch = useCallback(async () => {
		const q = (query || getSeedQuery() || "").trim();
		activeControllerRef.current?.abort();

		if (!q) {
			setSearching(false);
			setSearchResults([]);
			return;
		}

		const controller = new AbortController();
		activeControllerRef.current = controller;
		const requestId = ++requestIdRef.current;
		setSearching(true);

		try {
			const results = shouldUseDemoProvider()
				? await mockAiSearch(q, controller.signal)
				: await searchReferences(q, 10, controller.signal);
			if (requestId !== requestIdRef.current || controller.signal.aborted)
				return;
			setSearchResults(results);
		} catch (error) {
			if (controller.signal.aborted) return;
			throw error;
		} finally {
			if (requestId === requestIdRef.current && !controller.signal.aborted) {
				setSearching(false);
			}
		}
	}, [query, getSeedQuery]);

	const clearResults = useCallback(() => {
		activeControllerRef.current?.abort();
		setSearching(false);
		setSearchResults([]);
	}, []);

	return { query, setQuery, searching, searchResults, runSearch, clearResults };
}
