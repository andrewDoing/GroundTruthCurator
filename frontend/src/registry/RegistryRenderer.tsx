import { toolCallExtensions } from "./FieldComponentRegistry";
import { PluginErrorBoundary } from "./PluginErrorBoundary";
import type { ToolCallActionProps } from "./types";

/**
 * Renders all matching tool call extension components for a given tool call.
 * Returns null when no extensions match, so the caller can skip rendering.
 */
export function ToolCallExtensionRenderer(props: ToolCallActionProps) {
	const matches = toolCallExtensions.resolveAll(props.toolCall);

	if (matches.length === 0) return null;

	return (
		<>
			{matches.map((reg) => {
				const Comp = reg.component;
				return (
					<PluginErrorBoundary key={reg.discriminator} fallback={null}>
						<Comp {...props} />
					</PluginErrorBoundary>
				);
			})}
		</>
	);
}
