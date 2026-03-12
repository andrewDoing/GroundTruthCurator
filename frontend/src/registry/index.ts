// Public API for the plugin component registry.

export {
	FieldComponentRegistry,
	fieldComponentRegistry,
} from "./FieldComponentRegistry";
export {
	CodeBlockFallback,
	JsonFallback,
	KVDictFallback,
} from "./fallbacks";
export { PluginErrorBoundary } from "./PluginErrorBoundary";
export { RegistryRenderer } from "./RegistryRenderer";
export type {
	ComponentRegistration,
	EditorProps,
	FieldComponentRegistryAPI,
	RenderContext,
	ViewerProps,
} from "./types";
