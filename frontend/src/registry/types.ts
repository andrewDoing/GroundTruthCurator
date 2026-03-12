// Plugin component registry type definitions
//
// Discriminator-based component lookup for plugin-contributed renderers and
// editors.  Discriminators follow the pattern "category:kind"
// (e.g., "toolCall:retrieval", "plugin:rag-compat", "feedback:sentiment").

import type { ComponentType } from "react";

// ---------------------------------------------------------------------------
// Render context
// ---------------------------------------------------------------------------

/** Ambient context passed to every viewer and editor component. */
export type RenderContext = {
	/** Ground-truth item id that owns the data being rendered. */
	itemId: string;
	/** Dot-path to the field within the item (e.g. "plugins.rag-compat"). */
	fieldPath: string;
	/** Optional plugin kind when the component was contributed by a plugin. */
	pluginKind?: string;
	/** When true the component must not allow edits. */
	readOnly: boolean;
};

// ---------------------------------------------------------------------------
// Component props
// ---------------------------------------------------------------------------

/** Props for read-only viewer components. */
export type ViewerProps = {
	data: unknown;
	context: RenderContext;
};

/** Props for editable components. Extends viewer props with mutation hooks. */
export type EditorProps = ViewerProps & {
	onChange: (data: unknown) => void;
	onValidate?: (data: unknown) => string[];
};

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/** A single component registration bound to a discriminator string. */
export type ComponentRegistration = {
	/** Lookup key following "category:kind" convention. */
	discriminator: string;
	/** Read-only renderer for the data. */
	viewer: ComponentType<ViewerProps>;
	/** Optional editing component.  When absent the data is view-only. */
	editor?: ComponentType<EditorProps>;
	/** Human-readable label shown in registry listings / debug surfaces. */
	displayName: string;
};

// ---------------------------------------------------------------------------
// Registry interface
// ---------------------------------------------------------------------------

/** Public contract for the field component registry. */
export type FieldComponentRegistryAPI = {
	/** Register a component for a discriminator.  Throws on duplicate. */
	register(registration: ComponentRegistration): void;
	/**
	 * Look up the viewer or editor for a discriminator string.
	 * Returns `undefined` when no registration exists (caller should use fallback).
	 */
	resolve(
		discriminator: string,
		mode: "viewer" | "editor",
	): ComponentType<ViewerProps> | ComponentType<EditorProps> | undefined;
	/** Return all current registrations (useful for debug / startup validation). */
	registrations(): ReadonlyArray<ComponentRegistration>;
	/** Check whether a discriminator has a registration. */
	has(discriminator: string): boolean;
};
