import type { ViewerProps } from "../types";

/**
 * Fallback renderer for string data shown as a `<pre><code>` block.
 *
 * Non-string data is serialised to JSON before display.
 */
export default function CodeBlockFallback({ data }: ViewerProps) {
	const text =
		typeof data === "string"
			? data
			: (JSON.stringify(data, null, 2) ?? "undefined");

	return (
		<pre className="overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-64">
			<code>{text}</code>
		</pre>
	);
}
