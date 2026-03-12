// Tool call extension registry type definitions
//
// Discriminator-based component lookup for plugin-contributed tool call
// action components.  Discriminators follow the pattern "category:kind"
// (e.g., "toolCall:retrieval", "toolCall:search").

import type { ComponentType } from "react";
import type {
	GroundTruthItem,
	Reference,
	ToolCallRecord,
} from "../models/groundTruth";

// ---------------------------------------------------------------------------
// Tool call action context & props
// ---------------------------------------------------------------------------

/** Context passed to every tool call action component. */
export type ToolCallActionContext = {
	/** The ground-truth item that owns this tool call. */
	item: GroundTruthItem;
	/** When true the component must not allow edits. */
	readOnly: boolean;
};

/** Props for tool call action components rendered inside ToolCallDetailView. */
export type ToolCallActionProps = {
	/** The tool call record this action applies to. */
	toolCall: ToolCallRecord;
	/** Ambient context (item, read-only flag). */
	context: ToolCallActionContext;
	/** Existing references associated with this tool call. */
	references: Reference[];
	/** Callback to add new references for this tool call. */
	onAddReferences?: (refs: Reference[]) => void;
	/** Callback to open a reference (e.g. navigate to URL). */
	onOpenReference?: (ref: Reference) => void;
	/** Callback to update a reference. */
	onUpdateReference?: (refId: string, partial: Partial<Reference>) => void;
	/** Callback to remove a reference. */
	onRemoveReference?: (refId: string) => void;
};

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/** A single tool call extension registration bound to a discriminator. */
export type ToolCallExtensionRegistration = {
	/** Lookup key following "category:kind" convention (e.g. "toolCall:retrieval"). */
	discriminator: string;
	/** Component rendered inside the expanded tool call detail view. */
	component: ComponentType<ToolCallActionProps>;
	/** Human-readable label shown in registry listings / debug surfaces. */
	displayName: string;
	/**
	 * Optional predicate for fine-grained matching beyond the discriminator.
	 * When provided, the component is only rendered if this returns true.
	 */
	matches?: (toolCall: ToolCallRecord) => boolean;
};

// ---------------------------------------------------------------------------
// Registry interface
// ---------------------------------------------------------------------------

/** Public contract for the tool call extension registry. */
export type ToolCallExtensionRegistryAPI = {
	/** Register an extension for a discriminator. Replaces existing in dev. */
	register(registration: ToolCallExtensionRegistration): void;
	/**
	 * Find all extensions that match a given tool call.
	 * Uses discriminator prefix matching and optional predicate.
	 */
	resolveAll(
		toolCall: ToolCallRecord,
	): ReadonlyArray<ToolCallExtensionRegistration>;
	/** Return all current registrations (useful for debug / startup validation). */
	registrations(): ReadonlyArray<ToolCallExtensionRegistration>;
	/** Check whether any extension matches a tool call. */
	hasMatch(toolCall: ToolCallRecord): boolean;
};
