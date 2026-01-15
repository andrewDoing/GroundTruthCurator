import {
	Bot,
	Check,
	ChevronDown,
	ChevronRight,
	Edit2,
	Loader2,
	Paperclip,
	Trash2,
	X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type {
	ConversationTurn,
	ExpectedBehavior,
} from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import MarkdownRenderer from "../../common/MarkdownRenderer";
import ExpectedBehaviorSelector from "./ExpectedBehaviorSelector";

type Props = {
	turn: ConversationTurn;
	index: number;
	isLast: boolean;
	onUpdate: (content: string) => void;
	onUpdateExpectedBehavior?: (behaviors: ExpectedBehavior[]) => void; // only for agent turns
	onDelete: () => void;
	onRegenerate?: () => void; // only for agent turns - regenerates with full agent (tools + search)
	canEdit?: boolean;
	isGenerating?: boolean;
	referenceCount?: number;
	onViewReferences?: () => void;
};

export default function ConversationTurnComponent({
	turn,
	index,
	isLast,
	onUpdate,
	onUpdateExpectedBehavior,
	onDelete,
	onRegenerate,
	canEdit = true,
	isGenerating = false,
	referenceCount = 0,
	onViewReferences,
}: Props) {
	const [isEditing, setIsEditing] = useState(false);
	const [isCollapsed, setIsCollapsed] = useState(false);
	const [editContent, setEditContent] = useState(turn.content);
	const controlsEnabled = canEdit && !isGenerating;

	// Calculate pair-based turn number (each user+agent pair is one turn)
	const turnNumber = Math.floor(index / 2) + 1;

	const toggleEditMode = () => {
		if (!controlsEnabled) return;
		if (isEditing) {
			setEditContent(turn.content); // reset on cancel
		}
		// Ensure expanded when entering edit mode
		if (!isEditing && isCollapsed) setIsCollapsed(false);
		setIsEditing(!isEditing);
	};

	const handleSave = () => {
		if (!controlsEnabled) return;
		onUpdate(editContent);
		setIsEditing(false);
	};

	const handleCancel = () => {
		if (!controlsEnabled) return;
		setEditContent(turn.content);
		setIsEditing(false);
	};

	const isUser = turn.role === "user";
	const isAgent = turn.role === "agent";

	// Sync editContent when turn.content changes (e.g., when switching queue items)
	useEffect(() => {
		setEditContent(turn.content);
		// Reset edit mode when content changes (item switched)
		setIsEditing(false);
	}, [turn.content]);

	// Auto-enter edit mode for a newly added user turn (assumed last)
	// Only do this once when the turn is first created (empty content)
	const hasAutoEntered = useRef(false);
	useEffect(() => {
		if (isUser && isLast && !turn.content && !hasAutoEntered.current) {
			// Ensure expanded and editing for new empty user turns
			setIsCollapsed(false);
			setIsEditing(true);
			hasAutoEntered.current = true;
		}
	}, [isUser, isLast, turn.content]);

	return (
		<div
			data-turn-index={index}
			data-last-turn={isLast ? "true" : "false"}
			className={cn(
				"mb-3 rounded-xl border p-4",
				isUser && "border-blue-200 bg-blue-50",
				isAgent && "border-violet-200 bg-violet-50",
			)}
			aria-busy={isGenerating ? "true" : undefined}
		>
			<div className="mb-2 flex items-center justify-between">
				<div className="flex items-center gap-2">
					<span
						className={cn(
							"rounded-full px-3 py-1 text-xs font-medium",
							isUser && "bg-blue-500 text-white",
							isAgent && "bg-violet-500 text-white",
						)}
					>
						{isUser ? "User" : "Agent"}
					</span>
					<span className="text-xs text-slate-600">Turn #{turnNumber}</span>
					<button
						type="button"
						onClick={() => setIsCollapsed((c) => !c)}
						title={isCollapsed ? "Expand turn" : "Collapse turn"}
						aria-expanded={!isCollapsed}
						className="ml-1 flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
						disabled={!controlsEnabled || isEditing}
					>
						{isCollapsed ? (
							<ChevronRight className="h-4 w-4" />
						) : (
							<ChevronDown className="h-4 w-4" />
						)}
						<span>{isCollapsed ? "Open" : "Close"}</span>
					</button>
					{isAgent &&
						typeof referenceCount === "number" &&
						referenceCount > 0 && (
							<button
								type="button"
								onClick={onViewReferences}
								className="flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700 transition-colors hover:bg-violet-200"
								title={`View ${referenceCount} reference${referenceCount !== 1 ? "s" : ""} for this turn`}
							>
								<Paperclip className="h-3 w-3" />
								{referenceCount} reference{referenceCount !== 1 ? "s" : ""}
							</button>
						)}
					{isAgent &&
						typeof referenceCount === "number" &&
						referenceCount === 0 && (
							<button
								type="button"
								onClick={onViewReferences}
								className="flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700 transition-colors hover:bg-violet-200"
								title="Add references for this turn"
							>
								<Paperclip className="h-3 w-3" />
								Add reference
							</button>
						)}
					{/** Inline spinner appears while generating */}
					{isAgent && isGenerating && (
						<span className="ml-1 flex items-center gap-1 rounded-lg border border-violet-200 px-2 py-1 text-xs font-medium text-violet-700">
							<Loader2 className="h-3 w-3 animate-spin" />
							<span>Running…</span>
						</span>
					)}
					{/* Removed inline tag badges to avoid overflow */}
				</div>
				<div className="flex items-center gap-1">
					{controlsEnabled && !isEditing && (
						<>
							{isAgent && onRegenerate && (
								<button
									type="button"
									onClick={onRegenerate}
									title="Run Agent - Performs full agent workflow with tools and search. Updates both answer and references."
									className="flex items-center gap-1 rounded-lg border border-violet-200 px-2 py-1 text-xs font-medium text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
									disabled={isGenerating}
								>
									<Bot className="h-4 w-4" />
									<span>Agent</span>
								</button>
							)}
							<button
								type="button"
								onClick={toggleEditMode}
								title="Edit turn"
								className="flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
								disabled={isGenerating}
							>
								<Edit2 className="h-4 w-4" />
								<span>Edit</span>
							</button>
							<button
								type="button"
								onClick={onDelete}
								title="Delete turn"
								className="flex items-center gap-1 rounded-lg border border-rose-200 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
								disabled={isGenerating}
							>
								<Trash2 className="h-4 w-4" />
								<span>Delete</span>
							</button>
						</>
					)}
					{isEditing && (
						<>
							<button
								type="button"
								onClick={handleSave}
								title="Save changes"
								className="flex items-center gap-1 rounded-lg border border-emerald-200 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50"
							>
								<Check className="h-4 w-4" />
								<span>Save</span>
							</button>
							<button
								type="button"
								onClick={handleCancel}
								title="Cancel editing"
								className="flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
							>
								<X className="h-4 w-4" />
								<span>Cancel</span>
							</button>
						</>
					)}
				</div>
			</div>

			{!isCollapsed && (
				<>
					{/* Expected behavior selector for agent turns - moved to top */}
					{isAgent && onUpdateExpectedBehavior && (
						<div
							className={cn(
								"mb-3 rounded-lg border p-3",
								!turn.expectedBehavior || turn.expectedBehavior.length === 0
									? "border-rose-200 bg-rose-50/50"
									: "border-violet-100 bg-violet-50/50",
							)}
						>
							<ExpectedBehaviorSelector
								selectedBehaviors={turn.expectedBehavior || []}
								onChange={onUpdateExpectedBehavior}
								disabled={!controlsEnabled || isGenerating}
							/>
						</div>
					)}

					{isEditing ? (
						<textarea
							className="w-full rounded-lg border border-slate-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
							value={editContent}
							onChange={(e) => setEditContent(e.target.value)}
							rows={6}
							disabled={isGenerating}
							placeholder={
								isUser
									? "Enter user message..."
									: "Enter agent response (Markdown supported)..."
							}
						/>
					) : (
						<MarkdownRenderer
							content={turn.content}
							compact
							className={cn(
								"rounded-lg px-1 py-0.5", // subtle padding within turn box
							)}
						/>
					)}
				</>
			)}
		</div>
	);
}
