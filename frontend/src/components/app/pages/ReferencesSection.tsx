import { useRef, useState } from "react";
import type { Reference } from "../../../models/groundTruth";
import { urlToTitle } from "../../../models/utils";
import ReferencesTabs from "../../app/ReferencesPanel/ReferencesTabs";

export default function ReferencesSection({
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

	return (
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
					window.confirm(`Remove reference "${name}"? You can Undo for 8s.`)
				) {
					onRemoveReference(refId);
				}
			}}
			onOpenReference={onOpenReference}
			isMultiTurn={isMultiTurn}
		/>
	);
}
