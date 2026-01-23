import { X } from "lucide-react";
import { useEffect, useState } from "react";
import useModalKeys from "../../hooks/useModalKeys";
import type { GroundTruthItem } from "../../models/groundTruth";
import { getGroundTruth } from "../../services/groundTruths";
import { getRuntimeConfig } from "../../services/runtimeConfig";
import { validateReferenceUrl } from "../../utils/urlValidation";
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
	const [trustedReferenceDomains, setTrustedReferenceDomains] = useState<
		string[]
	>([]);

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
			return;
		}

		// Load trusted domains for reference opening
		getRuntimeConfig()
			.then((cfg) => {
				setTrustedReferenceDomains(cfg.trustedReferenceDomains ?? []);
			})
			.catch(() => {
				setTrustedReferenceDomains([]);
			});

		// Always fetch fresh data to ensure we get complete conversation history
		// (List endpoint returns truncated data for performance, but individual endpoint has complete history)
		setIsLoading(true);
		setLoadError(null);

		(async () => {
			try {
				// Validate required fields before API call
				if (!item.datasetName || !item.bucket || !item.id) {
					setLoadError("Missing required item identifiers");
					setCompleteItem(item);
					setIsLoading(false);
					return;
				}

				// Fetch complete item data from individual endpoint
				const completeItemData = await getGroundTruth(
					item.datasetName || "",
					item.bucket || "",
					item.id,
				);

				if (!completeItemData) {
					setLoadError("Item not found");
					setCompleteItem(item); // Fallback to original
					return;
				}

				setCompleteItem(completeItemData);
			} catch (error) {
				const message =
					error instanceof Error
						? error.message
						: "Failed to load complete item data";
				setLoadError(message);
				// Fallback to original item
				setCompleteItem(item);
			}
		})().finally(() => {
			setIsLoading(false);
		});
	}, [isOpen, item]);

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
									{item.id}
								</div>
							</div>
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Status
								</div>
								<div className="flex gap-2">
									<span
										className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${
											item.status === "draft"
												? "bg-amber-100 text-amber-900"
												: item.status === "approved"
													? "bg-emerald-100 text-emerald-900"
													: item.status === "skipped"
														? "bg-slate-200 text-slate-800"
														: "bg-rose-100 text-rose-900"
										}`}
									>
										{item.status}
									</span>
									{item.deleted && item.status !== "deleted" && (
										<span className="inline-block rounded-full bg-rose-100 px-3 py-1 text-sm font-medium text-rose-900">
											deleted
										</span>
									)}
								</div>
							</div>
						</div>
						{/* Dataset and Bucket */}
						{(item.datasetName || item.bucket) && (
							<div className="grid grid-cols-2 gap-4">
								{item.datasetName && (
									<div>
										<div className="mb-1 text-xs font-medium text-slate-600">
											Dataset
										</div>
										<div className="rounded-lg border bg-slate-50 p-2 text-sm text-slate-800">
											{item.datasetName}
										</div>
									</div>
								)}
								{item.bucket && (
									<div>
										<div className="mb-1 text-xs font-medium text-slate-600">
											Bucket
										</div>
										<div className="rounded-lg border bg-slate-50 p-2 text-sm text-slate-800">
											{item.bucket}
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
							<div className="rounded-lg border bg-white min-h-[200px]">
								{isLoading ? (
									<div className="flex items-center justify-center p-8">
										<div className="text-sm text-slate-600">
											Loading complete conversation...
										</div>
									</div>
								) : loadError ? (
									<div className="flex items-center justify-center p-8">
										<div className="text-sm text-red-600">{loadError}</div>
									</div>
								) : (
									<MultiTurnEditor
										current={displayItem}
										readOnly={true}
										canEdit={false}
										onUpdateHistory={() => {}}
										onDeleteTurn={() => {}}
										onGenerate={() =>
											Promise.resolve({ ok: false, error: "Read-only mode" })
										}
										onUpdateReference={() => {}}
										onRemoveReference={() => {}}
										// Secure reference opening with validation and user confirmation
										onOpenReference={(ref) => {
											if (!validateReferenceUrl(ref.url)) {
												alert(
													"This reference contains an unsafe URL and cannot be opened.",
												);
												return;
											}

											// For external or untrusted URLs, show user confirmation
											const parsedUrl = new URL(ref.url);
											const hostname = parsedUrl.hostname.toLowerCase();
											const sameOrigin = hostname === window.location.hostname;
											const isTrusted =
												trustedReferenceDomains.includes(hostname);
											const isExternal = !sameOrigin && !isTrusted;

											if (isExternal) {
												const confirmed = confirm(
													`You are about to visit an external website:\n\n${parsedUrl.hostname}\n\nDo you want to continue?`,
												);
												if (!confirmed) {
													return;
												}
											}

											// Open with security attributes
											window.open(
												ref.url,
												"_blank",
												"noopener,noreferrer,nofollow",
											);
										}}
										onUpdateTags={() => {}}
									/>
								)}
							</div>
						</div>{" "}
						{/* Tags */}
						{((item.manualTags && item.manualTags.length > 0) ||
							(item.computedTags && item.computedTags.length > 0)) && (
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Tags
								</div>
								<div className="flex flex-wrap gap-2">
									{item.computedTags?.map((tag) => (
										<TagChip key={`computed-${tag}`} tag={tag} isComputed />
									))}
									{item.manualTags?.map((tag) => (
										<TagChip key={`manual-${tag}`} tag={tag} />
									))}
								</div>
							</div>
						)}
						{/* Comment */}
						{item.comment && (
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Comment
								</div>
								<div className="rounded-lg border bg-white p-3 text-sm text-slate-700 whitespace-pre-wrap">
									{item.comment}
								</div>
							</div>
						)}
						{/* Metadata */}
						{item.reviewedAt && (
							<div>
								<div className="mb-1 text-xs font-medium text-slate-600">
									Reviewed At
								</div>
								<div className="rounded-lg border bg-slate-50 p-2 text-sm text-slate-800">
									{new Date(item.reviewedAt).toLocaleString()}
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
