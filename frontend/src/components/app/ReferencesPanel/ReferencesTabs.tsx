import type { RefObject } from "react";
import type { Reference } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import SearchTab from "./SearchTab";
import SelectedTab from "./SelectedTab";

type Props = {
	query: string;
	setQuery: (q: string) => void;
	searching: boolean;
	searchResults: Reference[];
	searchSelected: Set<string>;
	onRunSearch: () => void;
	onToggleSearchSelect: (id: string, checked: boolean) => void;
	onAddSelectedFromResults: () => void;
	onAddSingleResult: (ref: Reference) => void;
	searchInputRef: RefObject<HTMLInputElement | null>;
	references: Reference[];
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (r: Reference) => void;
	showSearch?: boolean;
	readOnly?: boolean;
};

export default function ReferencesTabs({
	query,
	setQuery,
	searching,
	searchResults,
	searchSelected,
	onRunSearch,
	onToggleSearchSelect,
	onAddSelectedFromResults,
	onAddSingleResult,
	searchInputRef,
	references,
	onUpdateReference,
	onRemoveReference,
	onOpenReference,
	showSearch = true,
	readOnly = false,
}: Props) {
	return (
		<aside
			className={cn(
				"self-start h-[calc(100vh-5.5rem)] rounded-2xl border bg-white shadow-sm overflow-hidden",
			)}
		>
			<div className="flex h-full flex-col overflow-hidden">
				<div className="border-b px-4 py-3">
					<div className="text-sm font-medium text-slate-800">
						Evidence Review
					</div>
					<p className="mt-1 text-xs text-slate-600">
						Review attached evidence here. Search stays available only on
						surfaces that still own retrieval acquisition.
					</p>
				</div>

				<div className="flex-1 overflow-y-auto p-4 space-y-4">
					{showSearch ? (
						<section className="rounded-xl border border-slate-200 bg-slate-50">
							<div className="border-b border-slate-200 px-4 py-3">
								<div className="text-sm font-medium text-slate-800">
									Search Evidence
								</div>
								<p className="mt-1 text-xs text-slate-600">
									Search and attach sources for single-turn compatibility flows.
								</p>
							</div>
							<SearchTab
								query={query}
								setQuery={setQuery}
								searching={searching}
								results={searchResults}
								selectedIds={searchSelected}
								onRunSearch={onRunSearch}
								onToggleSelect={onToggleSearchSelect}
								onAddSelected={onAddSelectedFromResults}
								onAddSingle={onAddSingleResult}
								inputRef={searchInputRef}
								existingReferences={references}
							/>
						</section>
					) : (
						<div className="rounded-xl border border-violet-200 bg-violet-50 p-3 text-xs text-violet-800">
							Retrieval search is owned by per-turn or plugin-specific evidence
							surfaces for this workflow. This panel stays focused on evidence
							review.
						</div>
					)}

					<section className="rounded-xl border border-slate-200 bg-white">
						<div className="border-b border-slate-200 px-4 py-3">
							<div className="text-sm font-medium text-slate-800">
								Review Attached Evidence ({references.length})
							</div>
							<p className="mt-1 text-xs text-slate-600">
								Evidence can come from plugin-owned retrieval, per-turn
								research, or compatibility projections.
							</p>
						</div>
						<SelectedTab
							references={references}
							onUpdateReference={onUpdateReference}
							onRemoveReference={onRemoveReference}
							onOpenReference={onOpenReference}
							readOnly={readOnly}
						/>
					</section>
				</div>
			</div>
		</aside>
	);
}
