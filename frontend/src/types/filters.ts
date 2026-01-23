/**
 * Shared types for filter state
 */

export type FilterType = "all" | "draft" | "approved" | "skipped" | "deleted";
export type SortColumn = "refs" | "reviewedAt" | "hasAnswer" | null;
export type SortDirection = "asc" | "desc";

export interface FilterState {
	status: FilterType;
	dataset: string;
	tags: string[];
	itemId: string;
	refUrl: string;
	keyword: string;
	sortColumn: SortColumn;
	sortDirection: SortDirection;
}
