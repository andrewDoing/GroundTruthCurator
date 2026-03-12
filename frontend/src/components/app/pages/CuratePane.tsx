import { Check, RefreshCw, Save, Trash2 } from "lucide-react";

import useCurationInstructions from "../../../hooks/useCurationInstructions";
import type { AgentGenerationResult } from "../../../hooks/useGroundTruth";
import type {
	ConversationTurn,
	GroundTruthItem,
	Reference,
} from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import {
	validateConversationPattern,
	validateExpectedTools,
} from "../../../models/validators";
import InstructionsPane from "../../app/InstructionsPane";
import defaultCurateMd from "../defaultCurateInstructions.md?raw";
import MultiTurnEditor from "../editor/MultiTurnEditor";

export default function CuratePane({
	current,
	canApprove,
	saving,
	onUpdateComment,
	onUpdateTags,
	onUpdateHistory,
	onDeleteTurn,
	onGenerateAgentTurn,
	onSaveDraft,
	onApprove,
	onSkip,
	onDelete,
	onRestore,
	onDuplicate,
	onUpdateReference,
	onRemoveReference,
	onOpenReference,
	onAddReferences,
	className,
}: {
	current: GroundTruthItem | null | undefined;
	canApprove: boolean;
	saving: boolean;
	onUpdateComment: (v: string) => void;
	onUpdateTags: (tags: string[]) => void;
	onUpdateHistory: (history: ConversationTurn[]) => void;
	onDeleteTurn: (messageIndex: number) => void;
	onGenerateAgentTurn: (messageIndex: number) => Promise<AgentGenerationResult>;
	onSaveDraft: () => void;
	onApprove: () => void;
	onSkip: () => void;
	onDelete: () => void;
	onRestore: () => void;
	onDuplicate: () => void;
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (ref: Reference) => void;
	onAddReferences?: (refs: Reference[]) => void;
	className?: string;
}) {
	// Dataset-specific curation instructions (fallback to per-item or local default)
	const datasetName = current?.datasetName;
	const { markdown: datasetMd, error: dsError } =
		useCurationInstructions(datasetName);

	return (
		<div className={cn("flex min-h-0 gap-3", className)}>
			{/* Left pane: conversation editor, approval, actions */}
			<section className="flex-1 min-w-0 space-y-3 overflow-y-auto min-h-0">
				{current?.deleted && (
					<div className="rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
						This ground truth is marked as deleted. You can restore it or leave
						it deleted. It will remain visible in the sidebar and exports.
					</div>
				)}
				<InstructionsPane
					className=""
					title="Curation Instructions"
					markdown={
						(datasetMd?.trim() ? datasetMd : current?.curationInstructions) ||
						(defaultCurateMd as unknown as string)
					}
				/>
				{dsError && datasetName && (
					<div className="-mt-2 text-xs text-amber-700">
						Using default instructions — couldn't load dataset instructions for
						<span className="ml-1 font-medium">{datasetName}</span>.
					</div>
				)}

				{/* Multi-turn conversation editor */}
				<div className="rounded-2xl border bg-white p-4 shadow-sm">
					<MultiTurnEditor
						current={current || null}
						onUpdateHistory={onUpdateHistory}
						onDeleteTurn={onDeleteTurn}
						onGenerate={onGenerateAgentTurn}
						canEdit={!current?.deleted}
						onUpdateReference={onUpdateReference}
						onRemoveReference={onRemoveReference}
						onOpenReference={onOpenReference}
						onAddReferences={onAddReferences}
						onUpdateTags={onUpdateTags}
					/>
				</div>

				{/* Comments Panel */}
				<div className="rounded-2xl border bg-white p-4 shadow-sm">
					<div className="mb-1 flex items-center gap-2">
						<div className="text-sm font-medium">Comments</div>
						<span className="ml-1 rounded-full border px-2 py-0.5 text-xs text-slate-500">
							Optional
						</span>
					</div>
					<textarea
						aria-label="Comments"
						placeholder="Add curator notes (optional)"
						className="h-28 w-full resize-y rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-violet-300"
						value={current?.comment || ""}
						onChange={(e) => onUpdateComment(e.target.value)}
					/>
				</div>

				{/* Approval Requirements Explanation */}
				{current && !canApprove && (
					<div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
						<h3 className="mb-2 text-sm font-semibold text-amber-900">
							⚠️ Issues Preventing Approval
						</h3>
						<div className="space-y-2 text-sm text-amber-800">
							{current.deleted && (
								<p className="flex items-start gap-2">
									<span className="mt-0.5 flex-shrink-0">✗</span>
									<span>
										<strong>Item is deleted:</strong> Restore the item before
										approving
									</span>
								</p>
							)}
							{validateConversationPattern(current.history).valid
								? null
								: validateConversationPattern(current.history).errors.map(
										(error) => (
											<p key={error} className="flex items-start gap-2">
												<span className="mt-0.5 flex-shrink-0">✗</span>
												<span>
													<strong>Conversation pattern error:</strong> {error}
												</span>
											</p>
										),
									)}
							{/* Expected tools gating: show missing required tools */}
							{validateExpectedTools(current).errors.map((error) => (
								<p key={error} className="flex items-start gap-2">
									<span className="mt-0.5 flex-shrink-0">✗</span>
									<span>
										<strong>Expected tool not called:</strong>{" "}
										{error
											.replace(/^Required tool /, "")
											.replace(/ was not called$/, "")}
									</span>
								</p>
							))}
						</div>
					</div>
				)}
				{current && canApprove && (
					<div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
						<h3 className="mb-2 text-sm font-semibold text-emerald-900">
							✓ Ready for Approval
						</h3>
						<p className="text-sm text-emerald-800">
							All requirements are met. You can approve this item.
						</p>
					</div>
				)}

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={onSaveDraft}
						disabled={saving}
						className="inline-flex items-center gap-2 rounded-2xl border bg-white px-4 py-2 hover:bg-violet-50 disabled:opacity-50"
					>
						<Save className="h-4 w-4" /> {saving ? "Saving…" : "Save Draft"}
					</button>
					<button
						type="button"
						onClick={onApprove}
						disabled={saving || !!current?.deleted || !canApprove}
						className="inline-flex items-center gap-2 rounded-2xl border border-violet-300 bg-violet-600 px-4 py-2 text-white shadow hover:bg-violet-700 disabled:opacity-50"
					>
						<Check className="h-4 w-4" /> {saving ? "Saving…" : "Approve"}
					</button>
					<button
						type="button"
						onClick={onDuplicate}
						disabled={!current || saving}
						className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
						title="Create a new draft rephrasing of this item"
					>
						{/* Using RefreshCw icon to indicate 'create a variant'; could be Copy icon if added */}
						<RefreshCw className="h-4 w-4" /> Duplicate
					</button>
					<button
						type="button"
						onClick={onSkip}
						className="inline-flex items-center gap-2 rounded-2xl border bg-white px-4 py-2 hover:bg-violet-50"
						title="Skip this ground truth (mark skipped) and move to the next"
					>
						Skip
					</button>
					{current && !current.deleted && (
						<button
							type="button"
							onClick={onDelete}
							className="ml-auto inline-flex items-center gap-2 rounded-2xl border border-rose-300 bg-white px-4 py-2 text-rose-700 hover:bg-rose-50"
							title="Soft delete this ground truth"
						>
							<Trash2 className="h-4 w-4" /> Delete
						</button>
					)}
					{current?.deleted && (
						<button
							type="button"
							onClick={onRestore}
							className="ml-auto inline-flex items-center gap-2 rounded-2xl border border-emerald-300 bg-white px-4 py-2 text-emerald-700 hover:bg-emerald-50"
							title="Restore this ground truth"
						>
							<RefreshCw className="h-4 w-4" /> Restore
						</button>
					)}
				</div>
			</section>
		</div>
	);
}
