import { Check, RefreshCw, Save, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

// Determine if it's appropriate to move focus into the editor
function shouldStealFocus(): boolean {
	const ae = typeof document !== "undefined" ? document.activeElement : null;
	if (!ae) return true;
	// If focus is already on an editable control, don't steal.
	if (ae instanceof HTMLElement) {
		const tag = ae.tagName.toLowerCase();
		if (tag === "input" || tag === "textarea" || ae.isContentEditable) {
			return false;
		}
	}
	return true;
}

function moveCaretToEnd(el: HTMLTextAreaElement) {
	const len = el.value?.length ?? 0;
	try {
		el.selectionStart = len;
		el.selectionEnd = len;
		// Ensure scroll position shows the end if content overflows
		el.scrollTop = el.scrollHeight;
	} catch {
		// Some environments may not support selection APIs; ignore.
	}
}

import useCurationInstructions from "../../../hooks/useCurationInstructions";
import type { AgentGenerationResult } from "../../../hooks/useGroundTruth";
import type {
	ConversationTurn,
	GroundTruthItem,
	Reference,
} from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import { validateConversationPattern } from "../../../models/validators";
import TagsEditor from "../../app/editor/TagsEditor";
import InstructionsPane from "../../app/InstructionsPane";
import defaultCurateMd from "../defaultCurateInstructions.md?raw";
import MultiTurnEditor from "../editor/MultiTurnEditor";

export default function CuratePane({
	current,
	canApprove,
	saving,
	onUpdateQuestion,
	onUpdateAnswer,
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
	onEditorModeChange,
	className,
}: {
	current: GroundTruthItem | null | undefined;
	canApprove: boolean;
	saving: boolean;
	onUpdateQuestion: (v: string) => void;
	onUpdateAnswer: (v: string) => void;
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
	onEditorModeChange?: (mode: "single" | "multi") => void;
	className?: string;
}) {
	// Ref to the Question textarea for autofocus on item load/selection
	const questionRef = useRef<HTMLTextAreaElement | null>(null);

	// Multi-turn mode: always default to multi-turn mode (single-turn mode is disabled)
	// editorMode is fixed to "multi" - keeping state for potential future use
	const [editorMode] = useState<"single" | "multi">("multi");

	// NOTE: Mode toggle disabled - refs and handler removed
	// const userOverrideRef = useRef(false);
	// const lastItemIdRef = useRef<string | null>(null);

	// NOTE: Auto-switching logic disabled - always stay in multi-turn mode
	// Update mode when current item changes based on whether it has history
	// Only auto-switch if the user hasn't manually overridden the mode for the current item
	// useEffect(() => {
	// 	if (!current) return;
	//
	// 	// If we switched to a different item, reset the override flag
	// 	if (current.id !== lastItemIdRef.current) {
	// 		userOverrideRef.current = false;
	// 		lastItemIdRef.current = current.id;
	// 	}
	//
	// 	// Don't auto-switch if user manually overrode the mode
	// 	if (userOverrideRef.current) return;
	//
	// 	// If item has history (multi-turn), switch to multi-turn mode
	// 	if (isMultiTurn(current) && editorMode === "single") {
	// 		setEditorMode("multi");
	// 	}
	// 	// If item lacks history (single-turn), switch to single-turn mode
	// 	else if (!isMultiTurn(current) && editorMode === "multi") {
	// 		setEditorMode("single");
	// 	}
	// }, [current, editorMode]);

	// Notify parent when editor mode changes
	useEffect(() => {
		onEditorModeChange?.(editorMode);
	}, [editorMode, onEditorModeChange]);

	// NOTE: Mode toggle handler disabled, code kept for potential future use
	// const handleModeToggle = (mode: "single" | "multi") => {
	// 	// Mark that the user manually changed the mode
	// 	userOverrideRef.current = true;
	//
	// 	// If switching from single to multi and there's no history yet, initialize with current Q&A
	// 	if (mode === "multi" && current && !isMultiTurn(current)) {
	// 		const initialHistory: ConversationTurn[] = [];
	// 		if (current.question?.trim()) {
	// 			initialHistory.push({ role: "user", content: current.question.trim() });
	// 		}
	// 		if (current.answer?.trim()) {
	// 			initialHistory.push({ role: "agent", content: current.answer.trim() });
	// 		}
	// 		if (initialHistory.length > 0) {
	// 			onUpdateHistory(initialHistory);
	//
	// 			// Assign existing references (those without messageIndex) to the first agent turn (index 1)
	// 			// This ensures references from single-turn mode are properly associated with the agent turn
	// 			if (current.references && current.references.length > 0 && onUpdateReference) {
	// 				const agentMessageIndex = 1; // First agent turn is at index 1 (after user turn at 0)
	// 				current.references.forEach(ref => {
	// 					if (ref.messageIndex === undefined) {
	// 						onUpdateReference(ref.id, { messageIndex: agentMessageIndex });
	// 					}
	// 				});
	// 			}
	// 		}
	// 	}
	//
	// 	setEditorMode(mode);
	// 	localStorage.setItem("gtc-editor-mode", mode);
	// };

	// Dataset-specific curation instructions (fallback to per-item or local default)
	const datasetName = current?.datasetName;
	const { markdown: datasetMd, error: dsError } =
		useCurationInstructions(datasetName);

	// Focus the Question textarea when a current item becomes available or changes
	useEffect(() => {
		if (!current?.id) return;
		const el = questionRef.current;
		if (!el) return;
		if (!shouldStealFocus()) return;
		// Focus and place caret at end for natural appending
		el.focus();
		moveCaretToEnd(el);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [current?.id]);

	return (
		<section className={cn("space-y-3", className)}>
			{current?.deleted && (
				<div className="rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
					This ground truth is marked as deleted. You can restore it or leave it
					deleted. It will remain visible in the sidebar and exports.
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

			{/* Mode Toggle - DISABLED: Always use multi-turn mode */}
			{/* <div className="flex items-center gap-2 rounded-2xl border bg-white p-2">
				<button
					type="button"
					onClick={() => handleModeToggle("single")}
					className={cn(
						"flex-1 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
						editorMode === "single"
							? "bg-violet-600 text-white shadow"
							: "text-slate-600 hover:bg-slate-100",
					)}
				>
					Single-turn
				</button>
				<button
					type="button"
					onClick={() => handleModeToggle("multi")}
					className={cn(
						"flex-1 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
						editorMode === "multi"
							? "bg-violet-600 text-white shadow"
							: "text-slate-600 hover:bg-slate-100",
					)}
				>
					Multi-turn
				</button>
			</div> */}

			{/* Editor: Single-turn or Multi-turn */}
			{editorMode === "single" ? (
				<>
					<div className="rounded-2xl border bg-white p-4 shadow-sm">
						<div className="mb-3 text-sm font-medium">Question</div>
						<textarea
							ref={questionRef}
							aria-label="Question"
							className="h-24 w-full resize-y rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-violet-300"
							value={current?.question || ""}
							onChange={(e) => onUpdateQuestion(e.target.value)}
						/>
					</div>

					<div className="rounded-2xl border bg-white p-4 shadow-sm">
						<div className="mb-3 text-sm font-medium">Answer</div>
						<textarea
							aria-label="Answer"
							className="h-48 w-full resize-y rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-violet-300"
							value={current?.answer || ""}
							onChange={(e) => onUpdateAnswer(e.target.value)}
						/>
					</div>
				</>
			) : (
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
			)}

			{editorMode === "single" && (
				<TagsEditor
					selected={current?.manualTags || []}
					computedTags={current?.computedTags}
					onChange={onUpdateTags}
					title="Tags"
				/>
			)}

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
						{editorMode === "multi" ? (
							<>
								{(() => {
									// Validate conversation pattern
									const patternValidation = validateConversationPattern(
										current.history,
									);
									if (!patternValidation.valid) {
										return (
											<>
												{patternValidation.errors.map((error) => (
													<p key={error} className="flex items-start gap-2">
														<span className="mt-0.5 flex-shrink-0">✗</span>
														<span>
															<strong>Conversation pattern error:</strong>{" "}
															{error}
														</span>
													</p>
												))}
											</>
										);
									}
									return null;
								})()}
								{(() => {
									// Check that all agent turns have expected behavior
									const agentTurns = (current.history || []).filter(
										(turn) => turn.role === "agent",
									);
									const agentTurnsWithoutBehavior = agentTurns.filter(
										(turn) =>
											!turn.expectedBehavior ||
											turn.expectedBehavior.length === 0,
									);
									if (agentTurnsWithoutBehavior.length > 0) {
										return (
											<p className="flex items-start gap-2">
												<span className="mt-0.5 flex-shrink-0">✗</span>
												<span>
													<strong>Missing expected behavior:</strong>{" "}
													{agentTurnsWithoutBehavior.length} agent turn
													{agentTurnsWithoutBehavior.length !== 1 ? "s" : ""}{" "}
													need at least one expected behavior selected
												</span>
											</p>
										);
									}
									return null;
								})()}
							</>
						) : (
							<>
								{(() => {
									const hasSelected = current.references.length > 0;
									if (!hasSelected) {
										return (
											<p className="flex items-start gap-2">
												<span className="mt-0.5 flex-shrink-0">✗</span>
												<span>
													<strong>No references:</strong> Select at least one
													reference
												</span>
											</p>
										);
									}
									return null;
								})()}
								{(() => {
									const unvisitedRefs = (current.references || []).filter(
										(r) => !r.visitedAt,
									);
									if (unvisitedRefs.length > 0) {
										return (
											<p className="flex items-start gap-2">
												<span className="mt-0.5 flex-shrink-0">✗</span>
												<span>
													<strong>Unvisited references:</strong>{" "}
													{unvisitedRefs.length} reference
													{unvisitedRefs.length !== 1 ? "s" : ""} need to be
													opened and reviewed
												</span>
											</p>
										);
									}
									return null;
								})()}
							</>
						)}
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
	);
}
