/**
 * Shared types for filter state
 */

export type FilterType = "all" | "draft" | "approved" | "skipped" | "deleted";
export type SortColumn = "refs" | "reviewedAt" | "hasAnswer" | "tagCount" | null;
export type SortDirection = "asc" | "desc";

export interface TagFilterState {
	include: string[];
	exclude: string[];
}

export interface FilterState {
	status: FilterType;
	dataset: string;
	tags: TagFilterState;
	itemId: string;
	refUrl: string;
	keyword: string;
	sortColumn: SortColumn;
	sortDirection: SortDirection;
}
