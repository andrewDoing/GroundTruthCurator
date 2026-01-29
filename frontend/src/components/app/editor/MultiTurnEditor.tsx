import {
	AlertCircle,
	CheckCircle,
	MessageCircle,
	UserCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { AgentGenerationResult } from "../../../hooks/useGroundTruth";
import { useReferencesSearch } from "../../../hooks/useReferencesSearch";
import useTags from "../../../hooks/useTags";
import type {
	ConversationTurn,
	ExpectedBehavior,
	GroundTruthItem,
	Reference,
} from "../../../models/groundTruth";
import { validateConversationPattern } from "../../../models/validators";
import TagChip from "../../common/TagChip";
import ConversationTurnComponent from "./ConversationTurn";
import TagsModal from "./TagsModal";
import TurnReferencesModal from "./TurnReferencesModal";

type Props = {
	current: GroundTruthItem | null;
	readOnly?: boolean;
	onUpdateHistory: (history: ConversationTurn[]) => void;
	onDeleteTurn: (messageIndex: number) => void;
	onGenerate: (messageIndex: number) => Promise<AgentGenerationResult>;
	canEdit: boolean;
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (ref: Reference) => void;
	onAddReferences?: (refs: Reference[]) => void;
	onUpdateTags: (tags: string[]) => void;
};

export default function MultiTurnEditor({
	current,
	readOnly = false,
	onUpdateHistory,
	onDeleteTurn,
	onGenerate,
	canEdit,
	onUpdateReference,
	onRemoveReference,
	onOpenReference,
	onAddReferences,
	onUpdateTags,
}: Props) {
	const [isGenerating, setIsGenerating] = useState(false);
	const [generatingMessageIndex, setGeneratingMessageIndex] = useState<
		number | null
	>(null);
	const [agentError, setAgentError] = useState<string | null>(null);
	const [viewingReferencesForTurn, setViewingReferencesForTurn] = useState<
		number | null
	>(null);
	const [managingGroundTruthTags, setManagingGroundTruthTags] = useState(false);

	// Search functionality for references modal
	const { query, setQuery, searching, searchResults, runSearch, clearResults } =
		useReferencesSearch({
			getSeedQuery: () => current?.question,
		});

	useEffect(() => {
		if (!current) {
			setAgentError(null);
			setIsGenerating(false);
			setGeneratingMessageIndex(null);
			clearResults();
			return;
		}
		setAgentError(null);
		setIsGenerating(false);
		setGeneratingMessageIndex(null);
	}, [current, clearResults]);

	const history = current?.history || [];
	const references = current?.references || [];

	// Backend-provided global tags (cached via useTags)
	const { allTags: availableTags, refresh: refreshTags } = useTags();

	// Calculate reference counts per turn
	const referenceCounts = useMemo(() => {
		const counts = new Map<number, number>();
		references.forEach((ref) => {
			if (typeof ref.messageIndex === "number") {
				counts.set(ref.messageIndex, (counts.get(ref.messageIndex) || 0) + 1);
			}
		});
		return counts;
	}, [references]);

	// Determine which turn types can be added next
	const lastTurn = history.length > 0 ? history[history.length - 1] : null;
	const canAddUser = !lastTurn || lastTurn.role === "agent";
	const canAddAgent = lastTurn?.role === "user";

	const handleAddUserTurn = () => {
		if (!canAddUser || isGenerating) return;
		const newHistory: ConversationTurn[] = [
			...history,
			{ role: "user", content: "" },
		];
		onUpdateHistory(newHistory);
	};

	const handleAddAgentTurn = () => {
		if (!canAddAgent || isGenerating) return;
		// Create empty agent turn placeholder - user will manually trigger generation
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

	const handleUpdateExpectedBehavior = (
		index: number,
		expectedBehavior: ExpectedBehavior[],
	) => {
		const newHistory = [...history];
		newHistory[index] = { ...newHistory[index], expectedBehavior };
		onUpdateHistory(newHistory);
	};

	const handleRemoveTurn = (index: number) => {
		if (isGenerating) return;

		const turn = history[index];
		if (!turn) return;

		// Validation: Check if deleting this turn would break conversation flow
		// If this is a user turn and the next turn is an agent turn, warn the user
		if (turn.role === "user" && index < history.length - 1) {
			const nextTurn = history[index + 1];
			if (nextTurn?.role === "agent") {
				if (
					!window.confirm(
						"Deleting this user turn will also require deleting the following agent turn to maintain conversation flow. Delete both turns?",
					)
				) {
					return;
				}
				// Delete both the user turn and the following agent turn
				onDeleteTurn(index);
				// After deleting index, the next turn shifts down, so delete at same index
				onDeleteTurn(index);
				return;
			}
		}

		// Standard confirmation for single turn deletion
		if (window.confirm("Are you sure you want to delete this turn?")) {
			onDeleteTurn(index);
		}
	};

	const handleRegenerate = async (index: number) => {
		if (isGenerating) return;

		// Confirmation check
		if (
			!window.confirm(
				"Run Agent will perform a full agent workflow with tools and search. This will replace both the answer and references for this turn. Continue?",
			)
		) {
			return;
		}

		setAgentError(null);
		setIsGenerating(true);
		setGeneratingMessageIndex(index);
		try {
			const result = await onGenerate(index);
			if (!result.ok && result.error) setAgentError(result.error);
		} catch (err) {
			const message =
				err instanceof Error ? err.message : "Agent request failed.";
			setAgentError(message);
		} finally {
			setIsGenerating(false);
			setGeneratingMessageIndex(null);
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
								No conversation turns yet. Start by adding a user turn, then
								alternate between user and agent turns.
							</p>
						</div>
					) : (
						history.map((turn, index) => (
							<ConversationTurnComponent
								// Use a composite key instead of the raw array index
								key={`${turn.role}-${index}`}
								turn={turn}
								index={index}
								isLast={index === history.length - 1}
								onUpdate={(content) => handleUpdateTurn(index, content)}
								onUpdateExpectedBehavior={
									turn.role === "agent"
										? (behaviors) =>
												handleUpdateExpectedBehavior(index, behaviors)
										: undefined
								}
								onDelete={() => handleRemoveTurn(index)}
								onRegenerate={
									turn.role === "agent"
										? () => {
												void handleRegenerate(index);
											}
										: undefined
								}
								isGenerating={isGenerating && generatingMessageIndex === index}
								canEdit={canEdit && !readOnly}
								referenceCount={
									turn.role === "agent" ? referenceCounts.get(index) : undefined
								}
								onViewReferences={
									turn.role === "agent"
										? () => setViewingReferencesForTurn(index)
										: undefined
								}
							/>
						))
					)}
					{isGenerating && generatingMessageIndex === history.length && (
						<ConversationTurnComponent
							key={`pending-agent-${history.length}`}
							turn={{ role: "agent", content: "" }}
							index={history.length}
							isLast
							onUpdate={() => {}}
							onDelete={() => {}}
							canEdit={false}
							isGenerating
						/>
					)}
				</div>
			</div>

			{agentError && (
				<div
					className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"
					role="alert"
				>
					{agentError}
				</div>
			)}

			{/* Add turn buttons */}
			{!readOnly && canEdit && (
				<div className="mt-4 flex gap-2 border-t border-slate-200 pt-4">
					<button
						type="button"
						onClick={handleAddUserTurn}
						disabled={!canAddUser || isGenerating}
						title={
							!canAddUser
								? "Can only add user turn after agent turn or as first turn"
								: "Add a new user turn"
						}
						className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-blue-50"
					>
						<UserCircle className="h-4 w-4" />
						Add User Turn
					</button>
					<button
						type="button"
						onClick={handleAddAgentTurn}
						disabled={!canAddAgent || isGenerating}
						title={
							!canAddAgent
								? "Can only add agent turn after user turn"
								: "Add a new agent turn"
						}
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

			{/* Turn References Modal */}
			{viewingReferencesForTurn !== null && (
				<TurnReferencesModal
					isOpen={true}
					onClose={() => setViewingReferencesForTurn(null)}
					messageIndex={viewingReferencesForTurn}
					references={references}
					onUpdateReference={onUpdateReference}
					onRemoveReference={onRemoveReference}
					onOpenReference={onOpenReference}
					readOnly={readOnly}
					query={query}
					setQuery={setQuery}
					searching={searching}
					searchResults={searchResults}
					onRunSearch={runSearch}
					onAddSearchResult={(ref) => {
						if (onAddReferences) {
							onAddReferences([ref]);
						}
					}}
				/>
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
