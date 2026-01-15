import type { RefObject } from "react";
import { useEffect } from "react";
import type { Reference } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import SearchTab from "./SearchTab";
import SelectedTab from "./SelectedTab";

export type RightTab = "search" | "selected";

type Props = {
	rightTab: RightTab;
	setRightTab: (tab: RightTab) => void;
	// search tab props
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
	// selected tab props
	references: Reference[];
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (r: Reference) => void;
	// multi-turn support
	isMultiTurn?: boolean;
	readOnly?: boolean;
};

export default function ReferencesTabs({
	rightTab,
	setRightTab,
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
	isMultiTurn = false,
	readOnly = false,
}: Props) {
	// Phase 2: In multi-turn mode, disable search tab and force 'selected' view
	if (isMultiTurn && rightTab !== "selected") {
		setRightTab("selected");
	}
	useEffect(() => {
		function onKeyDown(e: KeyboardEvent) {
			const target = e.target as HTMLElement | null;
			const tag = (target?.tagName || "").toLowerCase();
			if (tag === "input" || tag === "textarea" || target?.isContentEditable)
				return;
			const isMod = e.metaKey || e.ctrlKey;
			if (!isMod) return;
			if (e.key === "1") {
				e.preventDefault();
				setRightTab("search");
			} else if (e.key === "2") {
				e.preventDefault();
				setRightTab("selected");
			}
		}
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [setRightTab]);
	return (
		<aside
			className={cn(
				"self-start h-[calc(100vh-5.5rem)] rounded-2xl border bg-white p-0 shadow-sm flex flex-col overflow-hidden",
			)}
		>
			{/* Tabs Header */}
			<div className="flex items-center gap-2 border-b p-2">
				{!isMultiTurn && (
					<button
						type="button"
						className={cn(
							"rounded-lg px-3 py-1.5 text-sm",
							rightTab === "search"
								? "border border-violet-300 bg-violet-50"
								: "hover:bg-violet-50",
						)}
						onClick={() => setRightTab("search")}
						title="Search"
					>
						Search
					</button>
				)}
				<button
					type="button"
					className={cn(
						"rounded-lg px-3 py-1.5 text-sm",
						rightTab === "selected"
							? "border border-violet-300 bg-violet-50"
							: "hover:bg-violet-50",
					)}
					onClick={() => setRightTab("selected")}
					title="Selected references visible to the model"
				>
					Selected ({references.length})
				</button>
				{isMultiTurn && (
					<div className="ml-auto text-xs text-slate-600">
						Multi-turn mode: use per-turn modal
					</div>
				)}
			</div>

			{/* Tab Content */}
			{isMultiTurn ? (
				<>
					<SelectedTab
						references={references}
						onUpdateReference={onUpdateReference}
						onRemoveReference={onRemoveReference}
						onOpenReference={onOpenReference}
						readOnly={readOnly}
					/>
					<div className="mx-3 mb-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-[11px] text-violet-800">
						Per-turn reference management enabled. Open an agent turn and click
						"View References" to search & add references directly to that turn.
					</div>
				</>
			) : rightTab === "search" ? (
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
					isMultiTurn={false}
				/>
			) : (
				<SelectedTab
					references={references}
					onUpdateReference={onUpdateReference}
					onRemoveReference={onRemoveReference}
					onOpenReference={onOpenReference}
					readOnly={readOnly}
				/>
			)}
		</aside>
	);
}
