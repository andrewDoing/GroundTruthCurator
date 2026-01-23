/**
 * Utility for managing filter state in URL search parameters
 * Enables bookmarkable filtered views and filter persistence across page reloads
 */

import type { FilterState } from "../types/filters";

// Valid filter values for type safety
const VALID_STATUS_VALUES = [
	"all",
	"draft",
	"approved",
	"skipped",
	"deleted",
] as const;
const VALID_SORT_COLUMNS = ["refs", "reviewedAt", "hasAnswer"] as const;
const VALID_SORT_DIRECTIONS = ["asc", "desc"] as const;

/**
 * Parse filter state from URL search parameters with validation
 * Returns default state if parameters are invalid
 */
export function parseFilterStateFromUrl(search: string): Partial<FilterState> {
	const params = new URLSearchParams(search);
	const filterState: Partial<FilterState> = {};

	// Parse status
	const status = params.get("status");
	if (status && (VALID_STATUS_VALUES as readonly string[]).includes(status)) {
		filterState.status = status as FilterState["status"];
	}

	// Parse dataset
	const dataset = params.get("dataset");
	if (dataset) {
		filterState.dataset = dataset;
	}

	// Parse tags (comma-separated for include, excludeTags for exclude)
	const includeTagsParam = params.get("tags");
	const excludeTagsParam = params.get("excludeTags");

	if (includeTagsParam || excludeTagsParam) {
		filterState.tags = {
			include: includeTagsParam
				? includeTagsParam
						.split(",")
						.map((tag) => tag.trim())
						.filter((tag) => tag.length > 0)
				: [],
			exclude: excludeTagsParam
				? excludeTagsParam
						.split(",")
						.map((tag) => tag.trim())
						.filter((tag) => tag.length > 0)
				: [],
		};
	}

	// Parse itemId
	const itemId = params.get("itemId");
	if (itemId) {
		filterState.itemId = itemId;
	}

	// Parse refUrl
	const refUrl = params.get("refUrl");
	if (refUrl) {
		filterState.refUrl = decodeURIComponent(refUrl);
	}

	// Parse keyword (using 'q' as the URL parameter per spec)
	const keyword = params.get("q");
	if (keyword) {
		filterState.keyword = decodeURIComponent(keyword);
	}

	// Parse sort column
	const sortColumn = params.get("sortColumn");
	if (
		sortColumn &&
		(VALID_SORT_COLUMNS as readonly string[]).includes(sortColumn)
	) {
		filterState.sortColumn = sortColumn as FilterState["sortColumn"];
	}

	// Parse sort direction
	const sortDirection = params.get("sortDirection");
	if (
		sortDirection &&
		(VALID_SORT_DIRECTIONS as readonly string[]).includes(sortDirection)
	) {
		filterState.sortDirection = sortDirection as FilterState["sortDirection"];
	}

	return filterState;
}

/**
 * Convert filter state to URL search parameters
 * Omits default values to keep URLs clean
 */
export function filterStateToUrlParams(
	filters: FilterState,
	defaults: FilterState,
): URLSearchParams {
	const params = new URLSearchParams();

	// Only add parameters that differ from defaults
	if (filters.status !== defaults.status && filters.status !== "all") {
		params.set("status", filters.status);
	}

	if (filters.dataset !== defaults.dataset && filters.dataset !== "all") {
		params.set("dataset", filters.dataset);
	}

	if (
		filters.tags &&
		(filters.tags.include.length > 0 || filters.tags.exclude.length > 0) &&
		(defaults.tags?.include?.length ?? 0) === 0 &&
		(defaults.tags?.exclude?.length ?? 0) === 0
	) {
		if (filters.tags.include.length > 0) {
			params.set("tags", filters.tags.include.join(","));
		}
		if (filters.tags.exclude.length > 0) {
			params.set("excludeTags", filters.tags.exclude.join(","));
		}
	}

	if (filters.itemId !== defaults.itemId && filters.itemId) {
		params.set("itemId", filters.itemId);
	}

	if (filters.refUrl !== defaults.refUrl && filters.refUrl) {
		params.set("refUrl", encodeURIComponent(filters.refUrl));
	}

	if (filters.keyword !== defaults.keyword && filters.keyword) {
		params.set("q", encodeURIComponent(filters.keyword));
	}

	if (filters.sortColumn !== defaults.sortColumn && filters.sortColumn) {
		params.set("sortColumn", filters.sortColumn);
	}

	if (filters.sortDirection !== defaults.sortDirection) {
		params.set("sortDirection", filters.sortDirection);
	}

	return params;
}

/**
 * Update browser URL without causing a page reload
 * Uses history API for smooth navigation
 */
export function updateUrlWithoutReload(search: string): void {
	// Handle the search parameter correctly
	// If search is empty, no query string needed
	// If search doesn't start with ?, add it
	// If search already starts with ?, use as-is
	const queryString =
		!search || search === ""
			? ""
			: search.startsWith("?")
				? search
				: `?${search}`;
	const newUrl = `${window.location.pathname}${queryString}`;
	window.history.replaceState({ ...window.history.state }, "", newUrl);
}

/**
 * Get current URL search string
 */
export function getCurrentSearch(): string {
	return window.location.search;
}
