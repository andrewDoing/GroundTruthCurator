import {
	fieldComponentRegistry,
	toolCallExtensions,
} from "./FieldComponentRegistry";
import { PluginErrorBoundary } from "./PluginErrorBoundary";
import type { RenderContext, ToolCallActionProps, ViewerProps } from "./types";

type RegistryRendererProps = {
	discriminator: string;
	data: unknown;
	context: RenderContext;
	mode: "viewer" | "editor";
	onChange?: (data: unknown) => void;
	onValidate?: (data: unknown) => string[];
};

function FallbackFor({ data, context }: ViewerProps) {
	if (typeof data === "string") {
		return (
			<pre className="max-h-64 overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700">
				{data}
			</pre>
		);
	}
	if (data !== null && typeof data === "object" && !Array.isArray(data)) {
		return (
			<div className="grid gap-2 text-xs text-slate-700">
				{Object.entries(data as Record<string, unknown>).map(([key, value]) => (
					<div key={key} className="rounded-md bg-slate-50 p-2">
						<div className="font-medium text-slate-500">{key}</div>
						<div className="mt-1 break-all">
							{typeof value === "string" ? value : JSON.stringify(value)}
						</div>
					</div>
				))}
			</div>
		);
	}
	return (
		<pre className="max-h-64 overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700">
			{JSON.stringify({ data, fieldPath: context.fieldPath }, null, 2)}
		</pre>
	);
}

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
