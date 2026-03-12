// Public API for the plugin component registry.

export {
	getExplorerExtensions,
	registerExplorerExtension,
	resetExplorerExtensions,
} from "./ExplorerExtensions";
export type {
	ExplorerCellProps,
	ExplorerColumnExtension,
	ExplorerExtension,
	ExplorerFilterExtension,
} from "./ExplorerExtensions";
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
