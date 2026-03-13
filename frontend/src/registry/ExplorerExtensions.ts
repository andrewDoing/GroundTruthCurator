// Explorer extension types for plugin-contributed columns and filters.
//
// Plugin packs register ExplorerExtension objects that QuestionsExplorer
// reads at render time to add dynamic columns and filter dimensions.

import type { ComponentType } from "react";
import type { GroundTruthItem } from "../models/groundTruth";

// ---------------------------------------------------------------------------
// Column extension
// ---------------------------------------------------------------------------

/** Props passed to custom cell renderers registered by plugins. */
export type ExplorerCellProps = {
	item: GroundTruthItem;
};

/** A single column contributed by a plugin pack. */
export type ExplorerColumnExtension = {
	/** Unique key used for sorting and identification. */
	key: string;
	/** Header label displayed in the explorer table. */
	header: string;
	/** Custom cell renderer. When absent, `getValue` is rendered as text. */
	cellRenderer?: ComponentType<ExplorerCellProps>;
	/** Extract a sortable/displayable value from an item (used when no cellRenderer). */
	getValue: (item: GroundTruthItem) => string | number | null;
	/** Column width hint (CSS value, e.g. "80px" or "6rem"). */
	width?: string;
	/** Whether this column supports client-side sorting. Default true. */
	sortable?: boolean;
};

// ---------------------------------------------------------------------------
// Filter extension
// ---------------------------------------------------------------------------

/** A single filter dimension contributed by a plugin pack. */
export type ExplorerFilterExtension = {
	/** Unique key for URL-sync and state management. */
	key: string;
	/** Human-readable label. */
	label: string;
	/** Compute the set of distinct filter options from the current items. */
	getOptions: (items: GroundTruthItem[]) => string[];
	/** Return true when an item matches the selected filter value. */
	matches: (item: GroundTruthItem, selectedValue: string) => boolean;
};

// ---------------------------------------------------------------------------
// Aggregate extension registration
// ---------------------------------------------------------------------------

/** A complete explorer extension bundle registered by a plugin pack. */
export type ExplorerExtension = {
	/** Plugin pack name that owns this extension. */
	packName: string;
	/** Additional columns to render in the explorer table. */
	columns?: ExplorerColumnExtension[];
	/** Additional filter dimensions for the filter bar. */
	filters?: ExplorerFilterExtension[];
};

// ---------------------------------------------------------------------------
// Registry (module-level singleton)
// ---------------------------------------------------------------------------

const _extensions: ExplorerExtension[] = [];

/** Register an explorer extension (typically called at app startup). */
export function registerExplorerExtension(ext: ExplorerExtension): void {
	const existing = _extensions.find((e) => e.packName === ext.packName);
	if (existing) {
		// Replace in-place to support hot-reload during development.
		const idx = _extensions.indexOf(existing);
		_extensions[idx] = ext;
		return;
	}
	_extensions.push(ext);
}

/** Return all registered explorer extensions. */
export function getExplorerExtensions(): ReadonlyArray<ExplorerExtension> {
	return _extensions;
}

/** Clear all registrations (for testing). */
export function resetExplorerExtensions(): void {
	_extensions.length = 0;
}

// ---------------------------------------------------------------------------
// Built-in RAG compat extension (reference count column)
// ---------------------------------------------------------------------------

import { getItemReferences } from "../models/groundTruth";

registerExplorerExtension({
	packName: "rag-compat",
	columns: [
		{
			key: "referenceCount",
			header: "Refs",
			width: "60px",
			sortable: true,
			getValue: (item) => getItemReferences(item).length,
		},
	],
	filters: [
		{
			key: "hasReferences",
			label: "Has References",
			getOptions: () => ["yes", "no"],
			matches: (item, value) => {
				const hasRefs = getItemReferences(item).length > 0;
				return value === "yes" ? hasRefs : !hasRefs;
			},
		},
	],
});
