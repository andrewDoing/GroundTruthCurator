/**
 * ReferencesSection — generic right-pane container.
 *
 * Phase 4 redesign: this component is now a generic right-pane host rather
 * than a purely retrieval-specific panel.  It renders:
 *
 *  1. Evidence & Trace panel (TracePanel) — always shown when the current item
 *     has generic agentic data (toolCalls, traceIds, metadata, feedback,
 *     expectedTools).  This is the primary Phase 4 evidence surface.
 *
 *  2. RAG compatibility panel (ReferencesTabs) — shown as an opt-in section
 *     when the item has references OR when in single-turn mode.  This surface
 *     keeps retrieval-specific review alive without it defining the host layout.
 *
 * Passing `item` is optional; when omitted only the ReferencesTabs section
 * is rendered (backward-compatible with the existing single-turn surface).
 */

import { useRef, useState } from "react";
import type { GroundTruthItem, Reference } from "../../../models/groundTruth";
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
}: {
	/** Optional: current ground truth item.  When present the evidence panel
	 *  is rendered at the top of the right pane. */
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
}) {
	const [rightTab, setRightTab] = useState<"search" | "selected">("search");
	const [searchSelected, setSearchSelected] = useState<Set<string>>(new Set());
	const searchInputRef = useRef<HTMLInputElement | null>(null);

	// RAG compat surface: show ReferencesTabs when not in multi-turn mode OR
	// when the item still carries references (legacy/compat items).
	const showRagCompat = !isMultiTurn || references.length > 0;

	// Evidence panel: show TracePanel when item has generic agentic data.
	const showEvidence = !!item && hasEvidenceData(item);

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

	// Nothing to show
	if (!showEvidence && !showRagCompat) {
		return (
			<aside className="self-start h-[calc(100vh-5.5rem)] rounded-2xl border bg-slate-50 p-4 flex items-center justify-center text-sm text-slate-400 shadow-sm">
				No evidence or references available.
			</aside>
		);
	}

	return (
		<aside
			className={cn(
				"self-start h-[calc(100vh-5.5rem)] rounded-2xl border bg-white shadow-sm flex flex-col overflow-hidden",
			)}
		>
			{/* Evidence & Trace panel (generic agentic data) */}
			{showEvidence && item && (
				<div className="flex-none overflow-y-auto border-b p-3 max-h-[50%]">
					<TracePanel item={item} />
				</div>
			)}

			{/* RAG compatibility panel — retrieval search and selected references */}
			{showRagCompat && (
				<div className="flex flex-col flex-1 min-h-0">
					{/* Section label when both panels are visible */}
					{showEvidence && (
						<div className="flex items-center gap-2 border-b px-3 py-2 text-xs font-medium text-slate-500 bg-slate-50">
							<span className="rounded-full bg-slate-200 px-2 py-0.5">
								RAG References
							</span>
							<span className="text-slate-400">compatibility surface</span>
						</div>
					)}
					<div className="flex-1 min-h-0 overflow-hidden">
						<ReferencesTabs
							rightTab={rightTab}
							setRightTab={setRightTab}
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
							isMultiTurn={isMultiTurn}
						/>
					</div>
				</div>
			)}
		</aside>
	);
}
