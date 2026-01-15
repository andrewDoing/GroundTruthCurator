import { Lock } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { GroundTruthItem } from "../../models/groundTruth";
import { cn } from "../../models/utils";
import { fetchAvailableDatasets } from "../../services/datasets";
import type { GroundTruthListPagination } from "../../services/groundTruths";
import { listAllGroundTruths } from "../../services/groundTruths";
import { fetchTagsWithComputed } from "../../services/tags";

type FilterType = "all" | "draft" | "approved" | "skipped" | "deleted";
type SortColumn = "refs" | "reviewedAt" | "hasAnswer" | null;
type SortDirection = "asc" | "desc";

interface FilterState {
	status: FilterType;
	dataset: string;
	tags: string[];
	itemId: string;
	refUrl: string;
	sortColumn: SortColumn;
	sortDirection: SortDirection;
}

// Helper function for efficient array comparison (defined outside component for stability)
function areArraysEqual<T>(a: T[], b: T[]): boolean {
	if (a.length !== b.length) return false;
	const setA = new Set(a);
	return b.every((item) => setA.has(item));
}

export interface QuestionsExplorerItem extends GroundTruthItem {
	views?: number;
	reuses?: number;
	reviewedAt?: string | null;
}

interface QuestionsExplorerProps {
	items?: QuestionsExplorerItem[];
	onAssign: (item: QuestionsExplorerItem) => void | Promise<void>;
	onInspect: (item: QuestionsExplorerItem) => void;
	onDelete: (item: QuestionsExplorerItem) => Promise<void> | void;
	className?: string;
}

export default function QuestionsExplorer({
	items,
	onAssign,
	onInspect,
	onDelete,
	className,
}: QuestionsExplorerProps) {
	const datasetFilterId = useId();
	const itemsPerPageId = useId();

	// Use a ref to track the previous filter state to detect when filters change
	const previousFilterRef = useRef<FilterState | null>(null);

	// Filter state (unapplied)
	const [activeFilter, setActiveFilter] = useState<FilterType>("all");
	const [selectedDataset, setSelectedDataset] = useState<string>("all");
	const [selectedTags, setSelectedTags] = useState<string[]>([]);
	const [itemIdFilter, setItemIdFilter] = useState<string>("");
	const [referenceUrlFilter, setReferenceUrlFilter] = useState<string>("");
	const [sortColumn, setSortColumn] = useState<SortColumn>(null);
	const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
	const [itemsPerPage, setItemsPerPage] = useState(25);

	// Applied filter state (what was last sent to backend)
	const [appliedFilter, setAppliedFilter] = useState<FilterState>({
		status: "all",
		dataset: "all",
		tags: [],
		itemId: "",
		refUrl: "",
		sortColumn: null,
		sortDirection: "desc",
	});

	const [currentPage, setCurrentPage] = useState(1);
	const [fetchedItems, setFetchedItems] = useState<QuestionsExplorerItem[]>([]);
	const [pagination, setPagination] = useState<
		GroundTruthListPagination | undefined
	>(undefined);
	const [isLoading, setIsLoading] = useState(false);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [manualTags, setManualTags] = useState<string[]>([]);
	const [computedTags, setComputedTags] = useState<string[]>([]);
	const [availableDatasets, setAvailableDatasets] = useState<string[]>([]);
	const [expandedTagRows, setExpandedTagRows] = useState<Set<string>>(
		new Set(),
	);
	const [isTagFilterExpanded, setIsTagFilterExpanded] = useState(false);
	const [showItemIdInfo, setShowItemIdInfo] = useState(false);
	const [showUrlInfo, setShowUrlInfo] = useState(false);

	// Check if filters have changed from applied state (optimized with useMemo)
	const hasUnappliedChanges = useMemo(() => {
		return (
			activeFilter !== appliedFilter.status ||
			selectedDataset !== appliedFilter.dataset ||
			!areArraysEqual(selectedTags, appliedFilter.tags) ||
			itemIdFilter !== appliedFilter.itemId ||
			referenceUrlFilter !== appliedFilter.refUrl ||
			sortColumn !== appliedFilter.sortColumn ||
			sortDirection !== appliedFilter.sortDirection
		);
	}, [
		activeFilter,
		selectedDataset,
		selectedTags,
		itemIdFilter,
		referenceUrlFilter,
		appliedFilter,
		sortColumn,
		sortDirection,
	]);

	// Fetch available tags and datasets from backend
	useEffect(() => {
		let cancelled = false;

		Promise.all([fetchTagsWithComputed(), fetchAvailableDatasets()])
			.then(([tagsResult, datasets]) => {
				if (cancelled) return;
				setManualTags(tagsResult.manualTags);
				setComputedTags(tagsResult.computedTags);
				setAvailableDatasets(datasets);
			})
			.catch((error) => {
				if (cancelled) return;
				console.error("Failed to fetch tags or datasets:", error);
			});

		return () => {
			cancelled = true;
		};
	}, []);

	// Reset to page 1 when applied filters change (but not when page changes)
	useEffect(() => {
		// Check if this is a filter change (not initial mount)
		if (previousFilterRef.current !== null) {
			const prev = previousFilterRef.current;
			const filterChanged =
				prev.status !== appliedFilter.status ||
				prev.dataset !== appliedFilter.dataset ||
				prev.sortColumn !== appliedFilter.sortColumn ||
				prev.sortDirection !== appliedFilter.sortDirection ||
				JSON.stringify(prev.tags) !== JSON.stringify(appliedFilter.tags);

			if (filterChanged) {
				setCurrentPage(1);
			}
		}

		// Update the ref to track current filter
		previousFilterRef.current = appliedFilter;
	}, [appliedFilter]);

	// Fetch data from backend with applied filters
	useEffect(() => {
		if (items !== undefined) {
			setIsLoading(false);
			setLoadError(null);
			return;
		}

		let cancelled = false;
		setIsLoading(true);
		// Clear previous items when starting a new fetch to avoid showing stale data
		setFetchedItems([]);

		// Build API parameters from applied filters
		const sortByParam =
			appliedFilter.sortColumn === "refs"
				? "totalReferences"
				: appliedFilter.sortColumn;

		// Ensure page is at least 1
		const safePage = Math.max(1, currentPage);

		const params = {
			status: appliedFilter.status !== "all" ? appliedFilter.status : undefined,
			dataset:
				appliedFilter.dataset !== "all" ? appliedFilter.dataset : undefined,
			tags: appliedFilter.tags.length > 0 ? appliedFilter.tags : undefined,
			itemId: appliedFilter.itemId || undefined,
			refUrl: appliedFilter.refUrl || undefined,
			sortBy: sortByParam,
			sortOrder: sortByParam ? appliedFilter.sortDirection : undefined,
			page: safePage,
			limit: itemsPerPage,
		};

		listAllGroundTruths(params)
			.then(({ items: loadedItems, pagination: paginationData }) => {
				if (cancelled) return;
				setFetchedItems(loadedItems);
				setPagination(paginationData);
				setLoadError(null);
			})
			.catch((error) => {
				if (cancelled) return;
				const message =
					error instanceof Error
						? error.message
						: "Failed to load ground truths";
				setLoadError(message);
			})
			.finally(() => {
				if (cancelled) return;
				setIsLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [items, appliedFilter, currentPage, itemsPerPage]);

	const sourceItems = items ?? fetchedItems;
	const totalItemsCount = pagination?.total ?? sourceItems.length;

	const displayItems = useMemo(() => {
		// Server handles all sorting now, no client-side sorting needed
		return sourceItems;
	}, [sourceItems]);

	const handleFilterChange = (filter: FilterType) => {
		setActiveFilter(filter);
	};

	const handleDatasetChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
		setSelectedDataset(event.target.value);
	};

	const handleTagToggle = (tag: string) => {
		setSelectedTags((prev) =>
			prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
		);
	};

	const handleApplyFilters = () => {
		const newFilter: FilterState = {
			status: activeFilter,
			dataset: selectedDataset,
			tags: [...selectedTags],
			itemId: itemIdFilter,
			refUrl: referenceUrlFilter,
			sortColumn,
			sortDirection,
		};

		setAppliedFilter(newFilter);
		// Page reset is handled by useEffect that watches appliedFilter
	};

	const handleSort = (column: "refs" | "reviewedAt" | "hasAnswer") => {
		if (sortColumn === column) {
			// If already sorting by this column, toggle direction
			if (sortDirection === "desc") {
				setSortDirection("asc");
			} else {
				// If ascending, clear sort
				setSortColumn(null);
				setSortDirection("desc");
			}
		} else {
			// New column, start with descending
			setSortColumn(column);
			setSortDirection("desc");
		}
	};

	const handleItemsPerPageChange = (
		event: React.ChangeEvent<HTMLSelectElement>,
	) => {
		const newItemsPerPage = Number.parseInt(event.target.value, 10);
		setItemsPerPage(newItemsPerPage);
		setCurrentPage(1); // Reset to first page when changing items per page
		// Items per page is typically an immediate action, so no need to wait for Apply
	};

	const toggleTagsExpanded = (itemId: string) => {
		setExpandedTagRows((prev) => {
			const next = new Set(prev);
			if (next.has(itemId)) {
				next.delete(itemId);
			} else {
				next.add(itemId);
			}
			return next;
		});
	};

	// Pagination calculations - use backend pagination if available
	const totalPages =
		pagination?.totalPages ??
		Math.max(1, Math.ceil(totalItemsCount / itemsPerPage));

	useEffect(() => {
		setCurrentPage((prev) => Math.min(prev, totalPages));
	}, [totalPages]);

	const handlePreviousPage = () => {
		setCurrentPage((prev) => Math.max(1, prev - 1));
	};

	const handleNextPage = () => {
		setCurrentPage((prev) => Math.min(totalPages, prev + 1));
	};

	const handleGoToPage = (page: number) => {
		setCurrentPage(Math.min(Math.max(page, 1), totalPages));
	};

	return (
		<div className={cn("flex h-full flex-col gap-4", className)}>
			{/* Header Section */}
			<div className="space-y-3 flex-none">
				<h2 className="text-2xl font-bold text-slate-800">
					Ground Truths Explorer
				</h2>
				<p className="text-sm text-slate-600">
					Explore all ground truths with filtering, sorting, and bulk actions.
				</p>
				{/* Dataset Selector - Now first and prominent */}
				{availableDatasets.length > 0 && (
					<div className="flex items-center gap-3">
						<label
							htmlFor={datasetFilterId}
							className="text-base font-semibold text-slate-800"
						>
							Dataset:
						</label>
						<select
							id={datasetFilterId}
							value={selectedDataset}
							onChange={handleDatasetChange}
							className="rounded-lg border-2 border-slate-300 bg-white px-4 py-2 text-base font-medium text-slate-800 shadow-sm hover:border-violet-400 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-colors"
						>
							<option value="all">All Datasets</option>
							{availableDatasets.map((dataset) => (
								<option key={dataset} value={dataset}>
									{dataset}
								</option>
							))}
						</select>
					</div>
				)}
				{/* Item ID and Reference URL Filters - Horizontal Layout */}
				<div className="flex items-start gap-4 flex-wrap">
					{/* Item ID Filter */}
					<div className="flex-1 min-w-[300px]">
						<div className="flex items-center gap-2 mb-2">
							<label
								htmlFor="itemIdFilter"
								className="text-base font-semibold text-slate-800"
							>
								Item ID:
							</label>
							<div className="relative">
								<button
									type="button"
									onClick={() => setShowItemIdInfo(!showItemIdInfo)}
									className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-600 hover:bg-slate-300 hover:text-slate-800 transition-colors text-xs font-bold"
									title="Click for search information"
									aria-label="Item ID search information"
									aria-expanded={showItemIdInfo}
								>
									?
								</button>
								{showItemIdInfo && (
									<div className="absolute left-0 top-7 z-20 w-80 rounded-lg border border-slate-300 bg-white p-3 shadow-lg">
										<div className="flex items-start justify-between gap-2 mb-2">
											<h3 className="text-sm font-semibold text-slate-800">
												Item ID Search
											</h3>
											<button
												type="button"
												onClick={() => setShowItemIdInfo(false)}
												className="text-slate-400 hover:text-slate-600 transition-colors"
												aria-label="Close"
											>
												✕
											</button>
										</div>
										<div className="space-y-2 text-xs text-slate-600">
											<p>
												<strong className="text-slate-800">Exact match:</strong>{" "}
												Enter the complete item ID (e.g.,{" "}
												<code className="bg-slate-100 px-1 py-0.5 rounded">
													item-123
												</code>
												)
											</p>
											<p>
												<strong className="text-slate-800">
													Prefix match:
												</strong>{" "}
												Enter the start of an ID to find all matching items
												(e.g.,{" "}
												<code className="bg-slate-100 px-1 py-0.5 rounded">
													item-
												</code>{" "}
												matches{" "}
												<code className="bg-slate-100 px-1 py-0.5 rounded">
													item-123
												</code>
												,{" "}
												<code className="bg-slate-100 px-1 py-0.5 rounded">
													item-456
												</code>
												, etc.)
											</p>
											<p>
												<strong className="text-slate-800">
													Case sensitivity:
												</strong>{" "}
												Search is case sensitive (e.g., item id: ITEM-123 will
												not be found with a search on item-123)
											</p>
										</div>
									</div>
								)}
							</div>
						</div>
						<div className="flex items-center gap-2">
							<input
								id="itemIdFilter"
								type="text"
								value={itemIdFilter}
								onChange={(e) => setItemIdFilter(e.target.value)}
								placeholder="Enter item ID to search..."
								className="flex-1 rounded-lg border-2 border-slate-300 bg-white px-4 py-2 text-base text-slate-800 shadow-sm hover:border-violet-400 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-colors"
							/>
							{itemIdFilter && (
								<button
									type="button"
									onClick={() => setItemIdFilter("")}
									className="rounded-lg bg-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-300 transition-colors"
									title="Clear Item ID filter"
								>
									Clear
								</button>
							)}
						</div>
					</div>

					{/* Reference URL Filter */}
					<div className="flex-1 min-w-[300px]">
						<div className="flex items-center gap-2 mb-2">
							<label
								htmlFor="referenceUrlFilter"
								className="text-base font-semibold text-slate-800"
							>
								Reference URL:
							</label>
							<div className="relative">
								<button
									type="button"
									onClick={() => setShowUrlInfo(!showUrlInfo)}
									className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-600 hover:bg-slate-300 hover:text-slate-800 transition-colors text-xs font-bold"
									title="Click for search information"
									aria-label="Reference URL search information"
									aria-expanded={showUrlInfo}
								>
									?
								</button>
								{showUrlInfo && (
									<div className="absolute left-0 top-7 z-20 w-80 rounded-lg border border-slate-300 bg-white p-3 shadow-lg">
										<div className="flex items-start justify-between gap-2 mb-2">
											<h3 className="text-sm font-semibold text-slate-800">
												Reference URL Search
											</h3>
											<button
												type="button"
												onClick={() => setShowUrlInfo(false)}
												className="text-slate-400 hover:text-slate-600 transition-colors"
												aria-label="Close"
											>
												✕
											</button>
										</div>
										<div className="space-y-2 text-xs text-slate-600">
											<p>
												<strong className="text-slate-800">
													Partial match:
												</strong>{" "}
												Enter the reference url or part of it (e.g.,{" "}
												<code className="bg-slate-100 px-1 py-0.5 rounded">
													CS123456
												</code>
												)
											</p>

											<p>
												<strong className="text-slate-800">
													Case sensitivity:
												</strong>{" "}
												Search is case sensitive (e.g., reference url: cs123456
												will not be found with a search on CS123456)
											</p>
										</div>
									</div>
								)}
							</div>
						</div>
						<div className="flex items-center gap-2">
							<input
								id="referenceUrlFilter"
								type="text"
								value={referenceUrlFilter}
								onChange={(e) => setReferenceUrlFilter(e.target.value)}
								placeholder="Enter the reference URL to search..."
								className="flex-1 rounded-lg border-2 border-slate-300 bg-white px-4 py-2 text-base text-slate-800 shadow-sm hover:border-violet-400 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-colors"
								title="Filter items that contain references (item-level or turn-level) matching this URL substring"
							/>
							{referenceUrlFilter && (
								<button
									type="button"
									onClick={() => setReferenceUrlFilter("")}
									className="rounded-lg bg-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-300 transition-colors"
									title="Clear Reference URL filter"
								>
									Clear
								</button>
							)}
						</div>
					</div>
				</div>{" "}
				{/* Status Filter Buttons */}
				<div className="flex items-center gap-2 flex-wrap">
					<span className="text-sm font-medium text-slate-700 mr-1">
						Status:
					</span>
					<button
						type="button"
						onClick={() => handleFilterChange("all")}
						className={cn(
							"rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
							activeFilter === "all"
								? "bg-violet-600 text-white shadow"
								: "bg-slate-100 text-slate-700 hover:bg-slate-200",
						)}
					>
						All
					</button>
					<button
						type="button"
						onClick={() => handleFilterChange("draft")}
						className={cn(
							"rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
							activeFilter === "draft"
								? "bg-amber-600 text-white shadow"
								: "bg-amber-100 text-amber-800 hover:bg-amber-200",
						)}
					>
						Draft
					</button>
					<button
						type="button"
						onClick={() => handleFilterChange("approved")}
						className={cn(
							"rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
							activeFilter === "approved"
								? "bg-emerald-600 text-white shadow"
								: "bg-emerald-100 text-emerald-800 hover:bg-emerald-200",
						)}
					>
						Approved
					</button>
					<button
						type="button"
						onClick={() => handleFilterChange("skipped")}
						className={cn(
							"rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
							activeFilter === "skipped"
								? "bg-slate-600 text-white shadow"
								: "bg-slate-100 text-slate-800 hover:bg-slate-200",
						)}
					>
						Skipped
					</button>
					<button
						type="button"
						onClick={() => handleFilterChange("deleted")}
						className={cn(
							"rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
							activeFilter === "deleted"
								? "bg-rose-600 text-white shadow"
								: "bg-rose-100 text-rose-800 hover:bg-rose-200",
						)}
					>
						Deleted
					</button>
				</div>
				{/* Tag Filter Section */}
				{(manualTags.length > 0 || computedTags.length > 0) && (
					<div className="mt-3 space-y-2">
						<div className="flex items-center gap-2">
							<button
								type="button"
								onClick={() => setIsTagFilterExpanded(!isTagFilterExpanded)}
								className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-900 transition-colors"
								aria-expanded={isTagFilterExpanded}
								aria-label={
									isTagFilterExpanded
										? "Collapse tag filters"
										: "Expand tag filters"
								}
							>
								<span className="text-base">
									{isTagFilterExpanded ? "▼" : "▶"}
								</span>
								<span>Filter by Tags</span>
								{selectedTags.length > 0 && (
									<span className="inline-flex items-center justify-center rounded-full bg-violet-600 px-2 py-0.5 text-xs font-semibold text-white">
										{selectedTags.length}
									</span>
								)}
							</button>
							{selectedTags.length > 0 && (
								<button
									type="button"
									onClick={() => setSelectedTags([])}
									className="text-xs text-violet-600 hover:text-violet-800 underline"
								>
									Clear all
								</button>
							)}
						</div>
						{isTagFilterExpanded && (
							<div className="space-y-4">
								{/* Manual Tags Section */}
								{manualTags.length > 0 && (
									<div className="space-y-2">
										<h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
											Manual Tags
										</h4>
										<div className="flex flex-wrap gap-2">
											{manualTags.map((tag) => {
												const isSelected = selectedTags.includes(tag);
												return (
													<button
														key={tag}
														type="button"
														onClick={() => handleTagToggle(tag)}
														className={cn(
															"rounded-full px-3 py-1 text-xs font-medium transition-all border",
															isSelected
																? "bg-violet-600 text-white border-violet-600 shadow-sm"
																: "bg-white text-slate-700 border-slate-300 hover:border-violet-400 hover:bg-violet-50",
														)}
													>
														{tag}
														{isSelected && (
															<span className="ml-1.5 font-bold">×</span>
														)}
													</button>
												);
											})}
										</div>
									</div>
								)}
								{/* Computed Tags Section */}
								{computedTags.length > 0 && (
									<div className="space-y-2">
										<h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1">
											<Lock className="h-3 w-3" />
											Computed Tags
										</h4>
										<div className="flex flex-wrap gap-2">
											{computedTags.map((tag) => {
												const isSelected = selectedTags.includes(tag);
												return (
													<button
														key={tag}
														type="button"
														onClick={() => handleTagToggle(tag)}
														className={cn(
															"rounded-full px-3 py-1 text-xs font-medium transition-all border italic",
															isSelected
																? "bg-slate-600 text-white border-slate-600 shadow-sm"
																: "bg-slate-50 text-slate-600 border-slate-300 hover:border-slate-400 hover:bg-slate-100",
														)}
													>
														{tag}
														{isSelected && (
															<span className="ml-1.5 font-bold">×</span>
														)}
													</button>
												);
											})}
										</div>
									</div>
								)}
								{selectedTags.length > 0 && (
									<p className="text-xs text-slate-600">
										Showing items with{" "}
										{selectedTags.length === 1 ? "tag" : "all tags"}:{" "}
										<span className="font-medium">
											{selectedTags.join(", ")}
										</span>
									</p>
								)}
							</div>
						)}
					</div>
				)}
				{/* Apply Filters Button */}
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={handleApplyFilters}
						disabled={!hasUnappliedChanges || isLoading}
						className={cn(
							"rounded-lg px-6 py-2 text-sm font-semibold transition-all shadow-sm",
							hasUnappliedChanges && !isLoading
								? "bg-violet-600 text-white hover:bg-violet-700 hover:shadow-md"
								: "bg-slate-200 text-slate-400 cursor-not-allowed",
						)}
					>
						{isLoading ? "Loading..." : "Apply Filters"}
					</button>
					{hasUnappliedChanges && (
						<span className="text-xs text-amber-600 font-medium">
							Filters changed - click Apply to update results
						</span>
					)}
				</div>
			</div>

			{/* Table View */}
			<div className="flex-1 min-h-0">
				<div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
					<div className="h-full overflow-x-auto overflow-y-auto">
						<table className="w-full">
							<thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
								<tr className="text-xs font-semibold text-slate-700">
									<th className="px-3 py-3 text-left min-w-[100px]">ID</th>
									<th className="px-3 py-3 text-left min-w-[60px]">Status</th>
									<th className="px-3 py-3 text-left min-w-[200px]">
										Question
									</th>
									<th className="px-3 py-3 text-left min-w-[120px]">Tags</th>
									<th className="px-3 py-3 text-center min-w-[70px]">
										<button
											type="button"
											onClick={() => handleSort("hasAnswer")}
											className="inline-flex items-center gap-1 transition-colors hover:text-violet-700 w-full justify-center"
											aria-label="Sort by Has Answer"
										>
											Answer?
											{appliedFilter.sortColumn === "hasAnswer" && (
												<span className="text-violet-600">
													{appliedFilter.sortDirection === "desc" ? "↓" : "↑"}
												</span>
											)}
											{sortColumn === "hasAnswer" &&
												sortColumn !== appliedFilter.sortColumn && (
													<span className="text-amber-500 opacity-50">
														{sortDirection === "desc" ? "↓" : "↑"}
													</span>
												)}
										</button>
									</th>
									<th className="px-3 py-3 text-center min-w-[50px]">
										<button
											type="button"
											onClick={() => handleSort("refs")}
											className="inline-flex items-center gap-1 transition-colors hover:text-violet-700 w-full justify-center"
											aria-label="Sort by References"
											title="Total references (item-level + all turns)"
										>
											Refs
											{appliedFilter.sortColumn === "refs" && (
												<span className="text-violet-600">
													{appliedFilter.sortDirection === "desc" ? "↓" : "↑"}
												</span>
											)}
											{sortColumn === "refs" &&
												sortColumn !== appliedFilter.sortColumn && (
													<span className="text-amber-500 opacity-50">
														{sortDirection === "desc" ? "↓" : "↑"}
													</span>
												)}
										</button>
									</th>
									<th className="px-3 py-3 text-center min-w-[70px]">
										<button
											type="button"
											onClick={() => handleSort("reviewedAt")}
											className="inline-flex items-center gap-1 transition-colors hover:text-violet-700 w-full justify-center"
											aria-label="Sort by Reviewed Date"
										>
											Reviewed
											{appliedFilter.sortColumn === "reviewedAt" && (
												<span className="text-violet-600">
													{appliedFilter.sortDirection === "desc" ? "↓" : "↑"}
												</span>
											)}
											{sortColumn === "reviewedAt" &&
												sortColumn !== appliedFilter.sortColumn && (
													<span className="text-amber-500 opacity-50">
														{sortDirection === "desc" ? "↓" : "↑"}
													</span>
												)}
										</button>
									</th>
									<th className="px-3 py-3 text-right min-w-[240px]">
										Actions
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-slate-100">
								{loadError ? (
									<tr>
										<td
											colSpan={8}
											className="px-4 py-8 text-center text-sm text-rose-600"
										>
											Failed to load items: {loadError}
										</td>
									</tr>
								) : isLoading && sourceItems.length === 0 ? (
									<tr>
										<td
											colSpan={8}
											className="px-4 py-8 text-center text-sm text-slate-500"
										>
											Loading ground truths…
										</td>
									</tr>
								) : displayItems.length === 0 ? (
									<tr>
										<td
											colSpan={8}
											className="px-4 py-8 text-center text-sm text-slate-500"
										>
											No items to display
										</td>
									</tr>
								) : (
									displayItems.map((item) => (
										<tr
											key={item.id}
											className="transition-colors hover:bg-slate-50"
										>
											{/* ID */}
											<td className="px-3 py-3 text-xs">
												<div
													className="truncate font-mono text-slate-600"
													title={item.id}
												>
													{item.id}
												</div>
											</td>
											{/* Status */}
											<td className="px-3 py-3 text-xs">
												<div className="flex flex-wrap gap-1">
													<span
														className={cn(
															"inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
															item.status === "draft" &&
																"bg-amber-100 text-amber-900",
															item.status === "approved" &&
																"bg-emerald-100 text-emerald-900",
															item.status === "skipped" &&
																"bg-slate-200 text-slate-800",
															item.status === "deleted" &&
																"bg-rose-100 text-rose-900",
														)}
													>
														{item.status}
													</span>
													{item.deleted && item.status !== "deleted" && (
														<span className="inline-block rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-900 whitespace-nowrap">
															deleted
														</span>
													)}
												</div>
											</td>
											{/* Question */}
											<td className="px-3 py-3 text-sm">
												<div
													className="truncate font-medium text-slate-800 max-w-[300px]"
													title={item.question}
												>
													{item.question || "(no question)"}
												</div>
											</td>
											{/* Tags */}
											<td className="px-3 py-3">
												{(item.manualTags && item.manualTags.length > 0) ||
												(item.computedTags && item.computedTags.length > 0) ? (
													<div className="flex items-center gap-1">
														<button
															type="button"
															onClick={() => toggleTagsExpanded(item.id)}
															className="text-slate-500 hover:text-slate-700 transition-colors"
															aria-label={
																expandedTagRows.has(item.id)
																	? "Collapse tags"
																	: "Expand tags"
															}
														>
															{expandedTagRows.has(item.id) ? (
																<span className="text-sm">▼</span>
															) : (
																<span className="text-sm">▶</span>
															)}
														</button>
														{expandedTagRows.has(item.id) ? (
															<div className="flex flex-wrap gap-1 max-w-[150px]">
																{/* Computed tags */}
																{item.computedTags?.map((tag) => (
																	<span
																		key={`c-${tag}`}
																		className="inline-flex items-center gap-1 rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-xs text-slate-600 whitespace-nowrap"
																	>
																		<Lock className="h-2.5 w-2.5" />
																		{tag}
																	</span>
																))}
																{/* Manual tags */}
																{item.manualTags?.map((tag) => (
																	<span
																		key={`m-${tag}`}
																		className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800 whitespace-nowrap"
																	>
																		{tag}
																	</span>
																))}
															</div>
														) : (
															<span className="text-xs text-slate-600">
																{(item.manualTags?.length || 0) +
																	(item.computedTags?.length || 0)}{" "}
																tag
																{(item.manualTags?.length || 0) +
																	(item.computedTags?.length || 0) !==
																1
																	? "s"
																	: ""}
															</span>
														)}
													</div>
												) : (
													<span className="text-xs text-slate-400">—</span>
												)}
											</td>
											{/* Has Answer */}
											<td className="px-3 py-3 text-center text-sm font-medium">
												{item.answer && item.answer.trim().length > 0 ? (
													<span className="text-emerald-700">Yes</span>
												) : (
													<span className="text-slate-400">No</span>
												)}
											</td>
											{/* Refs */}
											<td className="px-3 py-3 text-center text-sm font-medium text-slate-700">
												{item.totalReferences ?? 0}
											</td>
											{/* Reviewed */}
											<td className="px-3 py-3 text-center text-xs text-slate-600">
												{item.reviewedAt
													? new Date(item.reviewedAt).toLocaleDateString(
															undefined,
															{
																month: "short",
																day: "numeric",
															},
														)
													: "-"}
											</td>
											{/* Actions */}
											<td className="px-3 py-3">
												<div className="flex items-center justify-end gap-2">
													<button
														type="button"
														onClick={() => onAssign(item)}
														className="rounded-lg border border-violet-300 bg-violet-600 px-3 py-1.5 text-xs text-white shadow-sm transition-colors hover:bg-violet-700 whitespace-nowrap"
														title="Assign this item"
														aria-label={`Assign ${item.id}`}
													>
														Assign
													</button>
													<button
														type="button"
														onClick={() => onInspect(item)}
														className="rounded-lg border border-slate-300 bg-slate-600 px-3 py-1.5 text-xs text-white shadow-sm transition-colors hover:bg-slate-700 whitespace-nowrap"
														title="Inspect this item"
														aria-label={`Inspect ${item.id}`}
													>
														Inspect
													</button>
													{item.deleted || item.status === "deleted" ? (
														<button
															type="button"
															onClick={() => {
																void (async () => {
																	try {
																		await onDelete(item);
																		// Reapply filters to refresh data after a mutation.
																		handleApplyFilters();
																	} catch (error) {
																		const message =
																			error instanceof Error
																				? error.message
																				: "Failed to restore item";
																		setLoadError(message);
																	}
																})();
															}}
															className="rounded-lg border border-emerald-300 bg-emerald-600 px-3 py-1.5 text-xs text-white shadow-sm transition-colors hover:bg-emerald-700 whitespace-nowrap"
															title="Restore this item to draft status"
															aria-label={`Restore ${item.id}`}
														>
															Restore
														</button>
													) : (
														<button
															type="button"
															onClick={() => {
																void (async () => {
																	try {
																		await onDelete(item);
																		// Reapply filters to refresh data after a mutation.
																		handleApplyFilters();
																	} catch (error) {
																		const message =
																			error instanceof Error
																				? error.message
																				: "Failed to delete item";
																		setLoadError(message);
																	}
																})();
															}}
															className="rounded-lg border border-rose-300 bg-rose-600 px-3 py-1.5 text-xs text-white shadow-sm transition-colors hover:bg-rose-700 whitespace-nowrap"
															title="Delete this item"
															aria-label={`Delete ${item.id}`}
														>
															Delete
														</button>
													)}
												</div>
											</td>
										</tr>
									))
								)}
							</tbody>
						</table>
					</div>
				</div>
			</div>

			{/* Pagination Controls */}
			{totalPages > 1 && (
				<div className="mt-4 flex flex-none items-center justify-between">
					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={handlePreviousPage}
							disabled={currentPage === 1}
							className={cn(
								"px-3 py-1 rounded border",
								currentPage === 1
									? "bg-gray-100 text-gray-400 cursor-not-allowed"
									: "bg-white text-gray-700 hover:bg-gray-50",
							)}
						>
							Previous
						</button>

						<div className="flex items-center gap-1">
							{Array.from({ length: totalPages }, (_, i) => i + 1).map(
								(pageNum) => (
									<button
										key={pageNum}
										type="button"
										onClick={() => handleGoToPage(pageNum)}
										className={cn(
											"px-3 py-1 rounded border",
											pageNum === currentPage
												? "bg-blue-500 text-white"
												: "bg-white text-gray-700 hover:bg-gray-50",
										)}
									>
										{pageNum}
									</button>
								),
							)}
						</div>

						<button
							type="button"
							onClick={handleNextPage}
							disabled={currentPage === totalPages}
							className={cn(
								"px-3 py-1 rounded border",
								currentPage === totalPages
									? "bg-gray-100 text-gray-400 cursor-not-allowed"
									: "bg-white text-gray-700 hover:bg-gray-50",
							)}
						>
							Next
						</button>
					</div>

					<div className="flex items-center gap-4">
						<div className="flex items-center gap-2">
							<label htmlFor={itemsPerPageId} className="text-sm text-gray-600">
								Items per page:
							</label>
							<select
								id={itemsPerPageId}
								value={itemsPerPage}
								onChange={handleItemsPerPageChange}
								className="px-2 py-1 border rounded bg-white text-gray-700 text-sm"
							>
								<option value={10}>10</option>
								<option value={25}>25</option>
								<option value={50}>50</option>
								<option value={100}>100</option>
							</select>
						</div>
						<div className="text-sm text-gray-600">
							Page {currentPage} of {totalPages}
						</div>
					</div>
				</div>
			)}

			{/* Item Count */}
			<div className="flex-none text-xs text-slate-500">
				{`Showing ${displayItems.length} of ${totalItemsCount} items`}
			</div>
		</div>
	);
}
