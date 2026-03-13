import { useCallback, useEffect, useRef, useState } from "react";
import { getDatasetCurationInstructions } from "../services/datasets";

const instructionsCache = new Map<string, string>();

/**
 * Hook to retrieve dataset-level curation instructions (markdown) with a per-session cache.
 * - Returns cached value immediately if present.
 * - Fetches when datasetName changes and differs from last fetched.
 * - Exposes loading/error and a manual refresh().
 */
function useCurationInstructions(datasetName?: string | null) {
	const ds = (datasetName || "").trim();
	const [markdown, setMarkdown] = useState<string | undefined>(() =>
		ds ? instructionsCache.get(ds) : undefined,
	);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const activeControllerRef = useRef<AbortController | null>(null);
	const requestIdRef = useRef(0);

	const loadInstructions = useCallback(
		async (forceRefresh = false) => {
			if (!ds) return;

			const cached = instructionsCache.get(ds);
			if (!forceRefresh && typeof cached !== "undefined") {
				setMarkdown(cached);
				setLoading(false);
				setError(null);
				return;
			}

			activeControllerRef.current?.abort();
			const controller = new AbortController();
			activeControllerRef.current = controller;
			const requestId = ++requestIdRef.current;
			setLoading(true);
			setError(null);

			try {
				const doc = await getDatasetCurationInstructions(ds, controller.signal);
				if (requestId !== requestIdRef.current || controller.signal.aborted) {
					return;
				}
				const nextMarkdown = doc?.instructions || "";
				instructionsCache.set(ds, nextMarkdown);
				setMarkdown(nextMarkdown);
			} catch (e) {
				if (controller.signal.aborted) return;
				const msg = e instanceof Error ? e.message : String(e);
				setError(msg);
			} finally {
				if (requestId === requestIdRef.current && !controller.signal.aborted) {
					setLoading(false);
				}
			}
		},
		[ds],
	);

	const refresh = useCallback(async () => {
		await loadInstructions(true);
	}, [loadInstructions]);

	useEffect(() => {
		if (!ds) {
			activeControllerRef.current?.abort();
			setMarkdown(undefined);
			setLoading(false);
			setError(null);
			return;
		}

		const cached = instructionsCache.get(ds);
		setMarkdown(cached);
		if (typeof cached !== "undefined") {
			setLoading(false);
			setError(null);
			return;
		}

		void loadInstructions();

		return () => {
			activeControllerRef.current?.abort();
		};
	}, [ds, loadInstructions]);

	useEffect(() => {
		return () => {
			activeControllerRef.current?.abort();
		};
	}, []);

	return { markdown, loading, error, refresh } as const;
}

export default useCurationInstructions;
