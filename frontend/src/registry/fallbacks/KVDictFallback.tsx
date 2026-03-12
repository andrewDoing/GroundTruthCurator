import type { ViewerProps } from "../types";

/**
 * Fallback renderer for `Record<string, unknown>` data.
 *
 * Renders key-value pairs using the same visual pattern as TracePanel's
 * KVDict component.  Falls back to JSON for non-object data.
 */
export default function KVDictFallback({ data }: ViewerProps) {
	if (data === null || typeof data !== "object" || Array.isArray(data)) {
		return (
			<pre className="overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-64">
				{JSON.stringify(data, null, 2)}
			</pre>
		);
	}

	const entries = Object.entries(data as Record<string, unknown>);

	if (entries.length === 0) {
		return <span className="text-xs italic text-slate-400">empty object</span>;
	}

	return (
		<div className="space-y-0.5">
			{entries.map(([k, v]) => (
				<div key={k} className="flex items-start gap-2 text-xs">
					<span className="font-mono text-slate-500 shrink-0">{k}:</span>
					<span className="text-slate-700 break-all">
						{typeof v === "object" ? JSON.stringify(v) : String(v)}
					</span>
				</div>
			))}
		</div>
	);
}
