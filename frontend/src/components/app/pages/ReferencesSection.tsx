/**
 * ReferencesSection — generic evidence and review host.
 *
 * The right pane now prioritizes generic evidence/review surfaces first, with
 * retrieval search kept as an explicit compatibility surface instead of the
 * host's defining mental model.
 */

import { useRef, useState } from "react";
import type {
	ContextEntry,
	ExpectedTools,
	GroundTruthItem,
	Reference,
} from "../../../models/groundTruth";
import { hasEvidenceData } from "../../../models/groundTruth";
import { cn, urlToTitle } from "../../../models/utils";
import ReferencesTabs from "../../app/ReferencesPanel/ReferencesTabs";
import TracePanel from "../../app/TracePanel";

export default function ReferencesSection({
	item,
	query,
	setQuery,
	searching,
	searchResults,
	onRunSearch,
	onAddRefs,
	references,
	onUpdateReference,
	onRemoveReference,
	onOpenReference,
	isMultiTurn,
	onUpdateContextEntries,
	onUpdateExpectedTools,
}: {
	item?: GroundTruthItem | null;
	query: string;
	setQuery: (q: string) => void;
	searching: boolean;
	searchResults: Reference[];
	onRunSearch: () => void;
	onAddRefs: (refs: Reference[]) => void;
	references: Reference[];
	onUpdateReference: (id: string, partial: Partial<Reference>) => void;
	onRemoveReference: (id: string) => void;
	onOpenReference: (ref: Reference) => void;
	isMultiTurn?: boolean;
	onUpdateContextEntries?: (entries: ContextEntry[]) => void;
	onUpdateExpectedTools?: (tools: ExpectedTools) => void;
}) {
	const [searchSelected, setSearchSelected] = useState<Set<string>>(new Set());
	const searchInputRef = useRef<HTMLInputElement | null>(null);

	const showSearchSurface = !isMultiTurn;
	const showEvidence = !!item && hasEvidenceData(item);
	const showEvidenceReview = references.length > 0 || showSearchSurface;

	async function runSearch() {
		try {
			await onRunSearch();
			setSearchSelected(new Set());
		} finally {
			searchInputRef.current?.focus();
		}
	}

	function addRefsFromResults(chosen: Reference[]) {
		onAddRefs(chosen);
		setSearchSelected((prev) => {
			const next = new Set(prev);
			chosen.forEach((c) => {
				next.delete(c.id);
			});
			return next;
		});
		searchInputRef.current?.focus();
	}

	function toggleSelectSearchResult(id: string, checked: boolean) {
		setSearchSelected((prev) => {
			const next = new Set(prev);
			if (checked) next.add(id);
			else next.delete(id);
			return next;
		});
	}

	function addSelectedFromResults() {
		if (!searchSelected.size) return;
		const chosen = (searchResults || []).filter((r) =>
			searchSelected.has(r.id),
		);
		if (!chosen.length) return;
		addRefsFromResults(chosen);
		searchInputRef.current?.focus();
	}

	if (!showEvidence && !showEvidenceReview) {
		return (
			<aside className="self-start h-[calc(100vh-5.5rem)] rounded-2xl border bg-slate-50 p-4 flex items-center justify-center text-sm text-slate-400 shadow-sm">
				No evidence or review surfaces are available for this item.
			</aside>
		);
	}

	return (
		<aside className="self-start flex h-[calc(100vh-5.5rem)] flex-col gap-3 overflow-hidden">
			{showEvidence && item && (
				<div
					className={cn(
						showEvidenceReview
							? "max-h-[55%] overflow-y-auto"
							: "flex-1 overflow-y-auto",
					)}
				>
					<TracePanel
						item={item}
						onUpdateContextEntries={onUpdateContextEntries}
						onUpdateExpectedTools={onUpdateExpectedTools}
					/>
				</div>
			)}

			{showEvidenceReview && (
				<div className="min-h-0 flex-1 overflow-hidden">
					<ReferencesTabs
						query={query}
						setQuery={setQuery}
						searching={searching}
						searchResults={searchResults}
						searchSelected={searchSelected}
						onRunSearch={runSearch}
						onToggleSearchSelect={toggleSelectSearchResult}
						onAddSelectedFromResults={addSelectedFromResults}
						onAddSingleResult={(ref) => addRefsFromResults([ref])}
						searchInputRef={searchInputRef}
						references={references}
						onUpdateReference={onUpdateReference}
						onRemoveReference={(refId) => {
							const r = (references || []).find((x) => x.id === refId);
							const name = r?.title || (r ? urlToTitle(r.url) : "reference");
							if (
								window.confirm(
									`Remove reference "${name}"? You can Undo for 8s.`,
								)
							) {
								onRemoveReference(refId);
							}
						}}
						onOpenReference={onOpenReference}
						showSearch={showSearchSurface}
					/>
				</div>
			)}
		</aside>
	);
}
