/**
 * ToolCallReferencesAction — rag-compat plugin action for retrieval tool calls.
 *
 * Renders a reference count badge / "Add reference" button inside the
 * expanded ToolCallDetailView. Clicking toggles an inline references list.
 */

import { ExternalLink, Paperclip, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { normalizeUrl, urlToTitle } from "../../../models/utils";
import type { ToolCallActionProps } from "../../../registry/types";

export default function ToolCallReferencesAction({
	toolCall,
	context,
	references,
	onOpenReference,
	onRemoveReference,
}: ToolCallActionProps) {
	const [expanded, setExpanded] = useState(false);

	// References scoped to this tool call
	const toolCallRefs = useMemo(
		() => references.filter((r) => r.toolCallId === toolCall.id),
		[references, toolCall.id],
	);

	const count = toolCallRefs.length;
	const readOnly = context.readOnly;

	return (
		<div className="border-t border-slate-100">
			{/* Badge / toggle button */}
			<button
				type="button"
				onClick={() => setExpanded((v) => !v)}
				className="flex w-full items-center gap-2 px-3 py-2 text-xs hover:bg-slate-50"
			>
				<Paperclip className="h-3 w-3 text-violet-600" />
				{count > 0 ? (
					<span className="font-medium text-violet-700">
						{count} reference{count !== 1 ? "s" : ""}
					</span>
				) : (
					<span className="font-medium text-violet-700">Add reference</span>
				)}
				<span className="ml-auto text-slate-400">{expanded ? "▾" : "▸"}</span>
			</button>

			{/* Inline references list */}
			{expanded && (
				<div className="border-t border-slate-100 px-3 py-2 space-y-2">
					{toolCallRefs.length === 0 && (
						<p className="text-xs text-slate-500">
							No references for this tool call yet.
						</p>
					)}
					{toolCallRefs.map((ref, i) => (
						<div
							key={ref.id}
							className="flex items-start justify-between gap-2 rounded-lg border border-slate-200 p-2 text-xs"
						>
							<div className="min-w-0 flex-1">
								<div className="truncate font-medium text-slate-700">
									[{i + 1}] {ref.title || urlToTitle(ref.url)}
								</div>
								<a
									className="inline-flex max-w-full items-center gap-1 truncate text-[11px] text-violet-700 underline"
									onClick={(e) => {
										e.preventDefault();
										onOpenReference?.(ref);
									}}
									href={normalizeUrl(ref.url)}
									target="_blank"
									rel="noopener noreferrer"
								>
									<ExternalLink className="h-3 w-3" />
									{normalizeUrl(ref.url)}
								</a>
								{ref.bonus && (
									<span className="ml-2 rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700">
										Bonus
									</span>
								)}
							</div>
							{!readOnly && onRemoveReference && (
								<button
									type="button"
									title="Remove reference"
									className="flex-none rounded border border-rose-200 p-1 text-rose-600 hover:bg-rose-50"
									onClick={() => onRemoveReference(ref.id)}
								>
									<Trash2 className="h-3 w-3" />
								</button>
							)}
						</div>
					))}
				</div>
			)}
		</div>
	);
}
