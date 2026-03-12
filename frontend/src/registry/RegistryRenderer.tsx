import { fieldComponentRegistry } from "./FieldComponentRegistry";
import CodeBlockFallback from "./fallbacks/CodeBlockFallback";
import JsonFallback from "./fallbacks/JsonFallback";
import KVDictFallback from "./fallbacks/KVDictFallback";
import { PluginErrorBoundary } from "./PluginErrorBoundary";
import type { RenderContext, ViewerProps } from "./types";

type RegistryRendererProps = {
	discriminator: string;
	data: unknown;
	context: RenderContext;
	mode: "viewer" | "editor";
	onChange?: (data: unknown) => void;
	onValidate?: (data: unknown) => string[];
};

/**
 * Select the appropriate fallback component based on the shape of `data`.
 */
function FallbackFor({ data, context }: ViewerProps) {
	if (typeof data === "string") {
		return <CodeBlockFallback data={data} context={context} />;
	}
	if (data !== null && typeof data === "object" && !Array.isArray(data)) {
		return <KVDictFallback data={data} context={context} />;
	}
	return <JsonFallback data={data} context={context} />;
}

/**
 * Top-level wrapper that resolves a field component from the registry,
 * wraps it in an error boundary, and falls back gracefully when no
 * registration exists or when the plugin component throws.
 */
export function RegistryRenderer({
	discriminator,
	data,
	context,
	mode,
	onChange,
	onValidate,
}: RegistryRendererProps) {
	const Resolved = fieldComponentRegistry.resolve(discriminator, mode);

	const fallback = <FallbackFor data={data} context={context} />;

	if (!Resolved) {
		return fallback;
	}

	// Build props for the resolved component.  Editor props are a superset of
	// viewer props, so we always start with viewer props and extend.
	const props =
		mode === "editor" && onChange
			? { data, context, onChange, onValidate }
			: { data, context };

	return (
		<PluginErrorBoundary fallback={fallback}>
			{/* biome-ignore lint/suspicious/noExplicitAny: resolved component is typed at registration time */}
			<Resolved {...(props as any)} />
		</PluginErrorBoundary>
	);
}
