import {
	AlertCircle,
	CheckCircle,
	MessageCircle,
	UserCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import useTags from "../../../hooks/useTags";
import type {
	ConversationTurn,
	GroundTruthItem,
} from "../../../models/groundTruth";
import { validateConversationPattern } from "../../../models/validators";
import TagChip from "../../common/TagChip";
import ConversationTurnComponent from "./ConversationTurn";
import TagsModal from "./TagsModal";

type Props = {
	current: GroundTruthItem | null;
	readOnly?: boolean;
	onUpdateHistory: (history: ConversationTurn[]) => void;
	onDeleteTurn: (messageIndex: number) => void;
	canEdit: boolean;
	onUpdateTags: (tags: string[]) => void;
};

export default function MultiTurnEditor({
	current,
	readOnly = false,
	onUpdateHistory,
	onDeleteTurn,
	canEdit,
	onUpdateTags,
}: Props) {
	const [managingGroundTruthTags, setManagingGroundTruthTags] = useState(false);

	const history = current?.history || [];

	// Backend-provided global tags (cached via useTags)
	const { allTags: availableTags, refresh: refreshTags } = useTags();

	// Any turn type can be added at any position (agentic workflows allow
	// consecutive agent turns such as orchestrator → sub-agent or RCA).
	const canAddUser = true;
	const canAddAgent = true;

	const handleAddUserTurn = () => {
		if (!canAddUser) return;
		const newHistory: ConversationTurn[] = [
			...history,
			{ role: "user", content: "" },
		];
		onUpdateHistory(newHistory);
	};

	const handleAddAgentTurn = () => {
		if (!canAddAgent) return;
		const newHistory: ConversationTurn[] = [
			...history,
			{ role: "agent", content: "" },
		];
		onUpdateHistory(newHistory);
	};

	const handleUpdateTurn = (index: number, content: string) => {
		const newHistory = [...history];
		newHistory[index] = { ...newHistory[index], content };
		onUpdateHistory(newHistory);
	};

	const handleRemoveTurn = (index: number) => {
		const turn = history[index];
		if (!turn) return;

		if (window.confirm("Are you sure you want to delete this turn?")) {
			onDeleteTurn(index);
		}
	};

	// Validate conversation pattern for visual feedback
	const patternValidation = useMemo(
		() => validateConversationPattern(history),
		[history],
	);

	if (!current) {
		return (
			<div className="flex h-full items-center justify-center text-slate-400">
				No item selected
			</div>
		);
	}

	return (
		<div className="flex h-full flex-col">
			{/* Conversation timeline */}
			<div className="flex-1 overflow-auto">
				<div className="mb-2 flex items-center justify-between">
					<div className="text-sm font-medium text-slate-700">
						Conversation History ({history.length} turns)
					</div>
					{history.length > 0 && (
						<div className="flex items-center gap-1.5 text-xs">
							{patternValidation.valid ? (
								<>
									<CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
									<span className="text-emerald-700">Valid pattern</span>
								</>
							) : (
								<>
									<AlertCircle className="h-3.5 w-3.5 text-amber-600" />
									<span
										className="text-amber-700"
										title={patternValidation.errors.join("; ")}
									>
										Pattern issues
									</span>
								</>
							)}
						</div>
					)}
				</div>
				<div className="space-y-0">
					{history.length === 0 ? (
						<div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
							<p className="text-sm text-slate-600">
								No conversation turns yet. Start by adding a user turn.
							</p>
						</div>
					) : (
						history.map((turn, idx) => {
							const turnKey =
								turn.turnId || turn.stepId || `${turn.role}-${String(idx)}`;
							return (
								<ConversationTurnComponent
									key={turnKey}
									turn={turn}
									index={idx}
									isLast={idx === history.length - 1}
									onUpdate={(content) => handleUpdateTurn(idx, content)}
									onDelete={() => handleRemoveTurn(idx)}
									canEdit={canEdit && !readOnly}
								/>
							);
						})
					)}
				</div>
			</div>

			{/* Add turn buttons */}
			{!readOnly && canEdit && (
				<div className="mt-4 flex gap-2 border-t border-slate-200 pt-4">
					<button
						type="button"
						onClick={handleAddUserTurn}
						disabled={!canAddUser}
						title="Add a new user turn"
						className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-blue-50"
					>
						<UserCircle className="h-4 w-4" />
						Add User Turn
					</button>
					<button
						type="button"
						onClick={handleAddAgentTurn}
						disabled={!canAddAgent}
						title="Add a new agent turn"
						className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-violet-50"
					>
						<MessageCircle className="h-4 w-4" />
						Add Agent Turn
					</button>
				</div>
			)}

			{/* Ground Truth Tags Section - Hide in read-only mode */}
			{!readOnly && (
				<div className="mt-4 border-t border-slate-200 pt-4">
					<div className="mb-2 flex items-center justify-between">
						<div className="text-sm font-medium text-slate-700">Tags</div>
						{canEdit && (
							<button
								type="button"
								onClick={() => setManagingGroundTruthTags(true)}
								className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-50"
							>
								Manage Tags
							</button>
						)}
					</div>
					{(current?.computedTags?.length || 0) +
						(current?.manualTags?.length || 0) >
					0 ? (
						<div className="flex flex-wrap gap-2">
							{current?.computedTags?.map((tag) => (
								<TagChip key={`computed-${tag}`} tag={tag} isComputed />
							))}
							{current?.manualTags?.map((tag) => (
								<TagChip key={`manual-${tag}`} tag={tag} />
							))}
						</div>
					) : (
						<p className="text-sm text-slate-500">No tags added yet</p>
					)}
				</div>
			)}

			{/* Ground Truth Tags Modal */}
			{managingGroundTruthTags && current && (
				<TagsModal
					isOpen={true}
					onClose={() => setManagingGroundTruthTags(false)}
					messageIndex={undefined}
					tags={current.manualTags || []}
					computedTags={current.computedTags}
					availableTags={availableTags}
					onUpdateTags={onUpdateTags}
					onRefreshTags={refreshTags}
				/>
			)}
		</div>
	);
}
