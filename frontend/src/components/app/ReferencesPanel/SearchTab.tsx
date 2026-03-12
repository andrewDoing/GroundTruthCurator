import { Search as SearchIcon, Upload } from "lucide-react";
import type React from "react";
import type { Reference } from "../../../models/groundTruth";
import {
	cn,
	normalizeUrl,
	truncateMiddle,
	urlToTitle,
} from "../../../models/utils";

type Props = {
	query: string;
	setQuery: (q: string) => void;
	searching: boolean;
	results: Reference[];
	selectedIds: Set<string>;
	onRunSearch: () => void;
	onToggleSelect: (id: string, checked: boolean) => void;
	onAddSelected: () => void;
	onAddSingle: (ref: Reference) => void;
	inputRef: React.RefObject<HTMLInputElement | null>;
	existingReferences: Reference[];
};

export default function SearchTab({
	query,
	setQuery,
	searching,
	results,
	selectedIds,
	onRunSearch,
	onToggleSelect,
	onAddSelected,
	onAddSingle,
	inputRef,
	existingReferences,
}: Props) {
	return (
		<div className="flex flex-col gap-4 p-4">
			<div className="flex items-center gap-2">
				<SearchIcon className="h-4 w-4" />
				<input
					ref={inputRef}
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							const q = (query || "").trim();
							if (!q || searching) return;
							e.preventDefault();
							onRunSearch();
						}
					}}
					placeholder="Search for supporting evidence…"
					className="flex-1 rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
				/>
				<button
					type="button"
					onClick={onRunSearch}
					disabled={searching}
					className="inline-flex items-center gap-2 rounded-xl border border-violet-300 bg-violet-600 px-3 py-2 text-sm text-white shadow hover:bg-violet-700 disabled:opacity-50"
				>
					<Upload className="h-4 w-4" /> Search
				</button>
			</div>

			<div className="text-xs text-slate-600">
				Use search when this host surface still owns retrieval. Multi-turn and
				plugin workflows can attach their own acquisition UI elsewhere.
			</div>

			{results.length > 0 && (
				<div className="rounded-xl border bg-violet-50 p-3">
					<div className="mb-2 text-sm font-medium">Search Results</div>
					<div className="max-h-[40vh] space-y-2 overflow-auto pr-1">
						{results.map((r) => {
							const already = existingReferences.some((x) => x.url === r.url);
							return (
								<div key={r.id} className="rounded-lg border bg-white p-2">
									<div className="flex items-start justify-between gap-2">
										<div className="min-w-0 max-w-full">
											<div
												className="text-sm font-medium break-anywhere line-clamp-2 leading-snug"
												title={r.title || urlToTitle(r.url)}
											>
												{r.title || urlToTitle(r.url)}
											</div>
											<div
												className="truncate text-xs text-slate-500 break-anywhere"
												title={normalizeUrl(r.url)}
											>
												{truncateMiddle(normalizeUrl(r.url), 70)}
											</div>
										</div>
										<label
											className="flex items-center gap-1 text-xs select-none focus-within:ring-2 focus-within:ring-violet-300 rounded-md px-1"
											htmlFor={`select-${r.id}`}
										>
											<input
												id={`select-${r.id}`}
												type="checkbox"
												className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
												checked={selectedIds.has(r.id)}
												onChange={(e) => onToggleSelect(r.id, e.target.checked)}
												onClick={(e) => e.stopPropagation()}
												disabled={already}
											/>
											<span className={already ? "text-slate-400" : ""}>
												Select
											</span>
										</label>
									</div>
									<div className="mt-2 flex gap-2">
										<button
											type="button"
											className={cn(
												"rounded-lg border px-2 py-1 text-xs",
												already
													? "cursor-not-allowed border-slate-200 text-slate-400"
													: "border-violet-300 text-violet-700 hover:bg-violet-50",
											)}
											onClick={() => !already && onAddSingle(r)}
											disabled={already}
										>
											{already ? "Added" : "Attach"}
										</button>
									</div>
								</div>
							);
						})}
					</div>
					<div className="mt-2 text-xs text-slate-600">
						Attach evidence one row at a time or bulk-select multiple results.
					</div>
				</div>
			)}

			<div className="sticky bottom-0 border-t bg-white/95 p-3 backdrop-blur">
				<div className="flex items-center justify-end">
					<button
						type="button"
						className="inline-flex items-center gap-2 rounded-lg border border-violet-300 bg-violet-600 px-3 py-2 text-sm text-white shadow hover:bg-violet-700 disabled:opacity-50"
						onClick={onAddSelected}
						disabled={selectedIds.size === 0}
					>
						Attach {selectedIds.size || 0} selected result
						{selectedIds.size === 1 ? "" : "s"}
					</button>
				</div>
			</div>
		</div>
	);
}
