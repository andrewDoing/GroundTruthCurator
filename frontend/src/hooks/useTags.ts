import { useCallback, useEffect, useState } from "react";
import { fetchAvailableTags } from "../services/tags";

function useTags() {
	const [allTags, setAllTags] = useState<string[]>([]);
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const tags = await fetchAvailableTags();
			if (Array.isArray(tags)) setAllTags(tags);
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			setError(msg);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		refresh();
	}, [refresh]);

	const ensureTag = useCallback(async (tag: string) => {
		const t = (tag || "").trim();
		if (!t) return;
		// Optimistic add locally; do not POST yet — defer until item save
		setAllTags((prev) => (prev.includes(t) ? prev : [...prev, t].sort()));
	}, []);

	const filter = useCallback(
		(q: string) => {
			const s = (q || "").toLowerCase();
			if (!s) return allTags;
			return allTags.filter((t) => t.toLowerCase().includes(s));
		},
		[allTags],
	);

	return { allTags, loading, error, refresh, ensureTag, filter };
}

export default useTags;
