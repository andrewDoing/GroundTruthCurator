// Public API for the plugin component registry.
//
// Phase 1 exports type definitions only.  The concrete registry
// implementation is added in Phase 2 (FieldComponentRegistry).

export type {
	ComponentRegistration,
	EditorProps,
	FieldComponentRegistryAPI,
	RenderContext,
	ViewerProps,
} from "./types";
