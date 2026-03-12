import { useState } from "react";
import type { ViewerProps } from "../types";

/** Character threshold above which the JSON block starts collapsed. */
const COLLAPSE_THRESHOLD = 500;

/**
 * Fallback renderer that formats any data as a JSON `<pre>` block.
 *
 * Includes a collapse / expand toggle when the serialised payload exceeds
 * ~500 characters.
 */
export default function JsonFallback({ data }: ViewerProps) {
	const text = JSON.stringify(data, null, 2) ?? "undefined";
	const isLong = text.length > COLLAPSE_THRESHOLD;
	const [expanded, setExpanded] = useState(!isLong);

	return (
		<div>
			{isLong && (
				<button
					type="button"
					className="mb-1 text-xs text-blue-600 hover:underline"
					onClick={() => setExpanded((prev) => !prev)}
				>
					{expanded ? "Collapse" : "Expand"}
				</button>
			)}

			{expanded ? (
				<pre className="overflow-auto rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-64">
					{text}
				</pre>
			) : (
				<pre className="overflow-hidden rounded-md bg-slate-100 p-2 text-xs text-slate-700 max-h-16">
					{text.slice(0, COLLAPSE_THRESHOLD)}…
				</pre>
			)}
		</div>
	);
}
