import {
	Check,
	ChevronDown,
	ChevronRight,
	Edit2,
	Trash2,
	X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ConversationTurn } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";
import MarkdownRenderer from "../../common/MarkdownRenderer";

type Props = {
	turn: ConversationTurn;
	index: number;
	isLast: boolean;
	onUpdate: (content: string) => void;
	onDelete: () => void;
	canEdit?: boolean;
};

export default function ConversationTurnComponent({
	turn,
	index,
	isLast,
	onUpdate,
	onDelete,
	canEdit = true,
}: Props) {
	const [isEditing, setIsEditing] = useState(false);
	const [isCollapsed, setIsCollapsed] = useState(false);
	const [editContent, setEditContent] = useState(turn.content);

	// Calculate pair-based turn number (each user+agent pair is one turn)
	const turnNumber = Math.floor(index / 2) + 1;

	const toggleEditMode = () => {
		if (!canEdit) return;
		if (isEditing) {
			setEditContent(turn.content); // reset on cancel
		}
		// Ensure expanded when entering edit mode
		if (!isEditing && isCollapsed) setIsCollapsed(false);
		setIsEditing(!isEditing);
	};

	const handleSave = () => {
		if (!canEdit) return;
		onUpdate(editContent);
		setIsEditing(false);
	};

	const handleCancel = () => {
		if (!canEdit) return;
		setEditContent(turn.content);
		setIsEditing(false);
	};

	const isUser = turn.role === "user";
	const isAgent = turn.role !== "user";
	// Display label: "Agent" for generic "agent" role, capitalize for others
	const roleLabel = isUser
		? "User"
		: turn.role === "agent"
			? "Agent"
			: turn.role;

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
						{roleLabel}
					</span>
					<span className="text-xs text-slate-600">Turn #{turnNumber}</span>
					<button
						type="button"
						onClick={() => setIsCollapsed((c) => !c)}
						title={isCollapsed ? "Expand turn" : "Collapse turn"}
						aria-expanded={!isCollapsed}
						className="ml-1 flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
						disabled={!canEdit || isEditing}
					>
						{isCollapsed ? (
							<ChevronRight className="h-4 w-4" />
						) : (
							<ChevronDown className="h-4 w-4" />
						)}
						<span>{isCollapsed ? "Open" : "Close"}</span>
					</button>
				</div>
				<div className="flex items-center gap-1">
					{canEdit && !isEditing && (
						<>
							<button
								type="button"
								onClick={toggleEditMode}
								title="Edit turn"
								className="flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
							>
								<Edit2 className="h-4 w-4" />
								<span>Edit</span>
							</button>
							<button
								type="button"
								onClick={onDelete}
								title="Delete turn"
								className="flex items-center gap-1 rounded-lg border border-rose-200 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
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

			{!isCollapsed &&
				(isEditing ? (
					<textarea
						aria-label={`${roleLabel} turn ${index + 1} content`}
						className="w-full rounded-lg border border-slate-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
						value={editContent}
						onChange={(e) => setEditContent(e.target.value)}
						rows={6}
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
				))}
		</div>
	);
}
