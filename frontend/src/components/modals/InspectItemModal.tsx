import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { useGroundTruthCache } from "../../hooks/useGroundTruthCache";
import useModalKeys from "../../hooks/useModalKeys";
import type { GroundTruthItem } from "../../models/groundTruth";
import { getGroundTruth } from "../../services/groundTruths";
import MultiTurnEditor from "../app/editor/MultiTurnEditor";
import type { QuestionsExplorerItem } from "../app/QuestionsExplorer";
import TagChip from "../common/TagChip";

type Props = {
	isOpen: boolean;
	item: QuestionsExplorerItem | null;
	onClose: () => void;
};

export default function InspectItemModal({ isOpen, item, onClose }: Props) {
	const [completeItem, setCompleteItem] = useState<GroundTruthItem | null>(
		null,
	);
	const [isLoading, setIsLoading] = useState(false);
	const [loadError, setLoadError] = useState<string | null>(null);

	const cache = useGroundTruthCache();

	useModalKeys({
		enabled: isOpen,
		onClose,
		onConfirm: onClose,
		busy: isLoading,
	});

	// Fetch complete item data when modal opens
	useEffect(() => {
		if (!isOpen || !item) {
			setCompleteItem(null);
			setLoadError(null);
			setIsLoading(false);
			return;
		}

		// Validate required fields before proceeding
		if (!item.datasetName || !item.bucket || !item.id) {
			setLoadError("Missing required item identifiers");
			setCompleteItem(item);
			setIsLoading(false);
			return;
		}

		const { datasetName, bucket, id } = item;

		// Check cache first (FR-001: in-memory session cache)
		const cachedItem = cache.get(datasetName, bucket, id);

		if (cachedItem) {
			// Use cached data to avoid redundant network call
			setCompleteItem(cachedItem);
			setLoadError(null);
			setIsLoading(false);
			return;
		}

		// Fetch fresh data if not in cache
		// (List endpoint returns truncated data for performance, but individual endpoint has complete history)
		const controller = new AbortController();
		setCompleteItem(null);
		setIsLoading(true);
		setLoadError(null);

		(async () => {
			try {
				// Fetch complete item data from individual endpoint
				const completeItemData = await getGroundTruth(
					datasetName,
					bucket,
					id,
					controller.signal,
				);

				if (controller.signal.aborted) return;

				if (!completeItemData) {
					setLoadError("Item not found");
					setCompleteItem(item); // Fallback to original
					return;
				}

				// Store in cache for future inspections (FR-001)
				cache.set(datasetName, bucket, id, completeItemData);

				setCompleteItem(completeItemData);
			} catch (error) {
				if (controller.signal.aborted) return;
				const message =
					error instanceof Error
						? error.message
						: "Failed to load complete item data";
				setLoadError(message);
				// Fallback to original item
				setCompleteItem(item);
			}
		})().finally(() => {
			if (!controller.signal.aborted) {
				setIsLoading(false);
			}
		});

		return () => {
			controller.abort();
		};
	}, [isOpen, item, cache]);

	if (!isOpen || !item) return null;

	// Use completeItem if available, otherwise fall back to original item
	const displayItem = completeItem || item;

	return (
		<div className="fixed inset-0 z-20 grid place-items-center bg-black/40 p-4">
			<div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl border bg-white shadow-xl flex flex-col">
				{/* Header */}
				<div className="flex items-center justify-between border-b p-4 flex-shrink-0">
					<div className="text-lg font-semibold">Inspect Ground Truth Item</div>
					<button
						type="button"
						onClick={onClose}
						className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
						aria-label="Close"
					>
						<X className="h-5 w-5" />
					</button>
				</div>

				{/* Content */}
				<div className="flex-1 overflow-auto">
					<div className="space-y-4 p-6">
						{/* ID and Status */}
						<div className="grid grid-cols-2 gap-4">
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									ID
								</div>
								<div className="rounded-lg border bg-slate-50 p-2 font-mono text-sm text-slate-800">
									{displayItem.id}
								</div>
							</div>
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Status
								</div>
								<div className="flex gap-2">
									<span
										className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${
											displayItem.status === "draft"
												? "bg-amber-100 text-amber-900"
												: displayItem.status === "approved"
													? "bg-emerald-100 text-emerald-900"
													: displayItem.status === "skipped"
														? "bg-slate-200 text-slate-800"
														: "bg-rose-100 text-rose-900"
										}`}
									>
										{displayItem.status}
									</span>
									{displayItem.deleted && displayItem.status !== "deleted" && (
										<span className="inline-block rounded-full bg-rose-100 px-3 py-1 text-sm font-medium text-rose-900">
											deleted
										</span>
									)}
								</div>
							</div>
						</div>
						{/* Dataset and Bucket */}
						{(displayItem.datasetName || displayItem.bucket) && (
							<div className="grid grid-cols-2 gap-4">
								{displayItem.datasetName && (
									<div>
										<div className="mb-1 text-xs font-medium text-slate-600">
											Dataset
										</div>
										<div className="rounded-lg border bg-slate-50 p-2 text-sm text-slate-800">
											{displayItem.datasetName}
										</div>
									</div>
								)}
								{displayItem.bucket && (
									<div>
										<div className="mb-1 text-xs font-medium text-slate-600">
											Bucket
										</div>
										<div className="rounded-lg border bg-slate-50 p-2 text-sm text-slate-800">
											{displayItem.bucket}
										</div>
									</div>
								)}
							</div>
						)}
						{/* Conversation Display */}
						<div>
							<div className="mb-1 text-xs font-medium text-slate-600">
								Conversation
							</div>
							{!isLoading && loadError && (
								<div
									role="alert"
									className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
								>
									{loadError}
								</div>
							)}
							<div className="rounded-lg border bg-white min-h-[200px]">
								{isLoading ? (
									<div className="flex items-center justify-center p-8">
										<div className="text-sm text-slate-600">
											Loading complete conversation...
										</div>
									</div>
								) : (
									<MultiTurnEditor
										current={displayItem}
										readOnly={true}
										canEdit={false}
										onUpdateHistory={() => {}}
										onDeleteTurn={() => {}}
										onUpdateTags={() => {}}
									/>
								)}
							</div>
						</div>{" "}
						{/* Tags */}
						{((displayItem.manualTags && displayItem.manualTags.length > 0) ||
							(displayItem.computedTags &&
								displayItem.computedTags.length > 0)) && (
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Tags
								</div>
								<div className="flex flex-wrap gap-2">
									{displayItem.computedTags?.map((tag) => (
										<TagChip key={`computed-${tag}`} tag={tag} isComputed />
									))}
									{displayItem.manualTags?.map((tag) => (
										<TagChip key={`manual-${tag}`} tag={tag} />
									))}
								</div>
							</div>
						)}
						{/* Comment */}
						{displayItem.comment && (
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Comment
								</div>
								<div className="rounded-lg border bg-white p-3 text-sm text-slate-700 whitespace-pre-wrap">
									{displayItem.comment}
								</div>
							</div>
						)}
						{/* Metadata */}
						{displayItem.reviewedAt && (
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Reviewed At
								</div>
								<div className="rounded-lg border bg-slate-50 p-2 text-sm text-slate-800">
									{new Date(displayItem.reviewedAt).toLocaleString()}
								</div>
							</div>
						)}
					</div>
				</div>

				{/* Footer */}
				<div className="border-t p-4 flex justify-end flex-shrink-0">
					<button
						type="button"
						onClick={onClose}
						className="rounded-lg bg-violet-600 px-6 py-2 text-sm font-medium text-white shadow hover:bg-violet-700 transition-colors"
					>
						Close
					</button>
				</div>
			</div>
		</div>
	);
}
