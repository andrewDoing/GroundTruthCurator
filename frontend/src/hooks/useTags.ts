import { useCallback, useEffect, useSyncExternalStore } from "react";
import {
	ensureTagCached,
	fetchTagsWithComputed,
	getTagMetadataSnapshot,
	subscribeToTagMetadata,
} from "../services/tags";

interface UseTagsOptions {
	enabled?: boolean;
}

function useTags(options?: UseTagsOptions) {
	const enabled = options?.enabled ?? true;
	const state = useSyncExternalStore(
		subscribeToTagMetadata,
		getTagMetadataSnapshot,
	);

	useEffect(() => {
		if (!enabled) {
			return;
		}

		fetchTagsWithComputed().catch(() => {
			// Service snapshot already captures the error state.
		});
	}, [enabled]);

	const refresh = useCallback(async () => {
		await fetchTagsWithComputed({ force: true });
	}, []);

	const ensureTag = useCallback((tag: string) => {
		ensureTagCached(tag);
	}, []);

	const filter = useCallback(
		(q: string) => {
			const search = (q || "").toLowerCase();
			if (!search) {
				return state.allTags;
			}

			return state.allTags.filter((tag) => tag.toLowerCase().includes(search));
		},
		[state.allTags],
	);

	return {
		allTags: state.allTags,
		manualTags: state.manualTags,
		computedTags: state.computedTags,
		loading: state.loading,
		error: state.error?.message ?? null,
		refresh,
		ensureTag,
		filter,
	};
}

export default useTags;
