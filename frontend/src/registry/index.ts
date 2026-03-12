// Public API for the plugin component registry.

// Side-effect imports: self-registering extensions
import "./ragCompatToolCallExtension";

export type {
	ExplorerCellProps,
	ExplorerColumnExtension,
	ExplorerExtension,
	ExplorerFilterExtension,
} from "./ExplorerExtensions";
export {
	getExplorerExtensions,
	registerExplorerExtension,
	resetExplorerExtensions,
} from "./ExplorerExtensions";
export {
	ToolCallExtensions,
	toolCallDiscriminator,
	toolCallExtensions,
} from "./FieldComponentRegistry";
export { PluginErrorBoundary } from "./PluginErrorBoundary";
export { ToolCallExtensionRenderer } from "./RegistryRenderer";
export type {
	ToolCallActionContext,
	ToolCallActionProps,
	ToolCallExtensionRegistration,
	ToolCallExtensionRegistryAPI,
} from "./types";
