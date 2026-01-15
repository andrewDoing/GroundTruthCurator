import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getDatasetCurationInstructions } from "../services/datasets";

/**
 * Hook to retrieve dataset-level curation instructions (markdown) with a per-session cache.
 * - Returns cached value immediately if present.
 * - Fetches when datasetName changes and differs from last fetched.
 * - Exposes loading/error and a manual refresh().
 */
function useCurationInstructions(datasetName?: string | null) {
	const ds = (datasetName || "").trim();
	const cacheRef = useRef<Record<string, string>>({});
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [version, setVersion] = useState(0); // bump to force recompute when cache changes

	// biome-ignore lint/correctness/useExhaustiveDependencies(version): suppress dependency version
	const value = useMemo(() => {
		if (!ds) return undefined;
		// Accessing ref doesn't need to be in deps; we trigger recompute by bumping version in state
		return cacheRef.current[ds];
	}, [ds, version]);

	const refresh = useCallback(async () => {
		if (!ds) return;
		setLoading(true);
		setError(null);
		try {
			const doc = await getDatasetCurationInstructions(ds);
			const md = doc?.instructions || "";
			cacheRef.current[ds] = md;
			setVersion((v) => v + 1);
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			setError(msg);
		} finally {
			setLoading(false);
		}
	}, [ds]);

	// Auto fetch when dataset changes and not in cache yet
	useEffect(() => {
		if (!ds) return;
		if (typeof cacheRef.current[ds] === "undefined") {
			void refresh();
		}
	}, [ds, refresh]);

	return { markdown: value, loading, error, refresh } as const;
}

export default useCurationInstructions;
