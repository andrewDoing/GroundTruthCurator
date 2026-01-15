import { ExternalLink, Trash2 } from "lucide-react";
import type { Reference } from "../../../models/groundTruth";
import { normalizeUrl, urlToTitle } from "../../../models/utils";
import { getCachedConfig } from "../../../services/runtimeConfig";

type Props = {
	references: Reference[];
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (r: Reference) => void;
	readOnly?: boolean;
};

export default function SelectedTab({
	references,
	onUpdateReference,
	onRemoveReference,
	onOpenReference,
	readOnly = false,
}: Props) {
	const config = getCachedConfig();
	const requireVisit = config?.requireReferenceVisit ?? true;
	const requireKeyPara = config?.requireKeyParagraph ?? false;

	return (
		<div className="flex h-full flex-col p-4">
			<div className="mb-1 text-sm font-medium">
				References ({references.length})
			</div>
			<div className="mb-2 text-xs text-slate-600">
				Each row shows visit status and an optional key paragraph.
			</div>
			<div className="max-h-[60vh] space-y-3 overflow-auto pr-1">
				{references.map((r, i) => {
					const len = r.keyParagraph?.trim().length || 0;
					return (
						<div
							key={r.id}
							className="rounded-xl border p-3"
							data-ref-turn-index={
								typeof r.messageIndex === "number" ? r.messageIndex : -1
							}
						>
							<div className="flex items-start justify-between gap-2">
								<div className="flex-1 min-w-0">
									<div className="text-sm font-medium break-words">
										[{i + 1}] {r.title || urlToTitle(r.url)}
										{typeof r.messageIndex === "number" && (
											<span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-700">
												Turn #{r.messageIndex + 1}
											</span>
										)}
									</div>
									<a
										className="inline-flex max-w-full items-center gap-1 text-xs text-violet-700 underline truncate"
										onClick={(e) => {
											e.preventDefault();
											onOpenReference(r);
										}}
										href={normalizeUrl(r.url)}
										target="_blank"
										rel="noreferrer"
									>
										<ExternalLink className="h-3.5 w-3.5" />{" "}
										{normalizeUrl(r.url)}
									</a>
								</div>
								<div className="flex items-center gap-3 flex-none shrink-0">
									{/* Bonus toggle */}
									<label
										className="flex items-center gap-2 text-xs whitespace-nowrap"
										title="Mark this reference as bonus context"
									>
										<input
											type="checkbox"
											checked={!!r.bonus}
											onChange={(e) =>
												onUpdateReference(r.id, { bonus: e.target.checked })
											}
										/>
										Bonus
									</label>
									<button
										type="button"
										title="Remove reference"
										className="rounded-lg border border-rose-200 p-1 text-rose-700 hover:bg-rose-50"
										onClick={() => onRemoveReference(r.id)}
									>
										<Trash2 className="h-4 w-4" />
									</button>
								</div>
							</div>

							<div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
								{r.visitedAt && (
									<span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-900">
										✓ Visited {new Date(r.visitedAt).toLocaleString()}
									</span>
								)}
								{!r.visitedAt && requireVisit && (
									<>
										<button
											type="button"
											className="rounded-lg border px-2 py-1 hover:bg-violet-50"
											onClick={() => onOpenReference(r)}
										>
											Open
										</button>
										<span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">
											Needs visit
										</span>
									</>
								)}
								{!r.visitedAt && !requireVisit && (
									<button
										type="button"
										className="rounded-lg border px-2 py-1 hover:bg-violet-50"
										onClick={() => onOpenReference(r)}
									>
										Open
									</button>
								)}
							</div>
							{/* Key paragraph section - hide when empty in read-only mode */}
							{(!readOnly ||
								(r.keyParagraph && r.keyParagraph.trim().length > 0)) && (
								<>
									<div className="mt-2 flex items-center gap-2 text-xs font-medium">
										<span>
											Key paragraph {requireKeyPara ? "" : "(optional)"}
										</span>
										{!readOnly && (
											<span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">
												{len} chars
											</span>
										)}
									</div>
									<textarea
										className={
											readOnly
												? "mt-1 w-full rounded-xl border p-2 text-sm bg-slate-50 text-slate-700 cursor-default"
												: "mt-1 w-full rounded-xl border p-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
										}
										placeholder={
											readOnly
												? ""
												: "Summarize the most relevant passage in your own words… (optional)"
										}
										value={r.keyParagraph || ""}
										onChange={
											readOnly
												? undefined
												: (e) =>
														onUpdateReference(r.id, {
															keyParagraph: e.target.value,
														})
										}
										readOnly={readOnly}
										rows={
											readOnly
												? Math.max(
														1,
														Math.ceil((r.keyParagraph || "").length / 60),
													)
												: 4
										}
									/>
								</>
							)}
						</div>
					);
				})}
				{references.length === 0 && (
					<div className="rounded-lg border bg-white p-3 text-xs text-slate-600">
						No references added yet. Use the Search tab to add references.
					</div>
				)}
			</div>

			<div className="mt-3 rounded-lg bg-violet-50 p-2 text-xs text-slate-700">
				To approve: add at least one reference.
				{requireVisit && " All references must be visited."}
				{requireKeyPara && " Key paragraphs required for all references."}
				{!requireVisit &&
					!requireKeyPara &&
					" Visit status and key paragraphs are optional."}
			</div>
		</div>
	);
}
