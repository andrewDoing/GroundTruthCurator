import {
	ExternalLink,
	Search as SearchIcon,
	Trash2,
	Upload,
	X,
} from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useToasts } from "../../../hooks/useToasts";
import type { Reference } from "../../../models/groundTruth";
import { cn, normalizeUrl, urlToTitle } from "../../../models/utils";
import { getCachedConfig } from "../../../services/runtimeConfig";
import ModalPortal from "../../modals/ModalPortal";

type Props = {
	isOpen: boolean;
	onClose: () => void;
	messageIndex: number;
	references: Reference[];
	onUpdateReference: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference: (refId: string) => void;
	onOpenReference: (ref: Reference) => void;
	readOnly?: boolean;
	// Search props (optional)
	query?: string;
	setQuery?: (q: string) => void;
	searching?: boolean;
	searchResults?: Reference[];
	onRunSearch?: () => void;
	onAddSearchResult?: (ref: Reference) => void;
};

export default function TurnReferencesModal({
	isOpen,
	onClose,
	messageIndex,
	references,
	onUpdateReference,
	onRemoveReference,
	onOpenReference,
	readOnly = false,
	query = "",
	setQuery = () => {},
	searching = false,
	searchResults = [],
	onRunSearch = () => {},
	onAddSearchResult = () => {},
}: Props) {
	const titleId = useId();
	const searchInputRef = useRef<HTMLInputElement | null>(null);
	const [selectedSearchIds, setSelectedSearchIds] = useState<Set<string>>(
		new Set(),
	);

	const config = getCachedConfig();
	const requireVisit = config?.requireReferenceVisit ?? true;
	const requireKeyPara = config?.requireKeyParagraph ?? false;
	const { toasts, showToast, dismiss } = useToasts();
	const undoTimerRef = useRef<number | null>(null);

	// Clear selections when modal closes
	useEffect(() => {
		if (!isOpen) {
			setSelectedSearchIds(new Set());
		}
	}, [isOpen]);

	// Cleanup undo timer on unmount
	useEffect(() => {
		return () => {
			if (undoTimerRef.current) {
				window.clearTimeout(undoTimerRef.current);
			}
		};
	}, []);

	// Optional: do not autofocus; keep logic if needed later
	// useEffect(() => {
	// 	if (isOpen && searchInputRef.current) {
	// 		searchInputRef.current.focus();
	// 	}
	// }, [isOpen]);

	if (!isOpen) return null;

	// Filter references for this specific turn only
	const turnRefs = references.filter((r) => r.messageIndex === messageIndex);

	// References already added to this turn (by URL for duplicate prevention)
	const urlsInTurn = new Set(turnRefs.map((r) => normalizeUrl(r.url)));

	const handleSearchSubmit = () => {
		const q = (query || "").trim();
		if (!q || searching) return;
		onRunSearch();
	};

	const handleToggleSearchSelect = (id: string, checked: boolean) => {
		setSelectedSearchIds((prev) => {
			const next = new Set(prev);
			if (checked) next.add(id);
			else next.delete(id);
			return next;
		});
	};

	const handleAddSearchResult = (ref: Reference, silent = false) => {
		// Assign messageIndex automatically
		onAddSearchResult({ ...ref, messageIndex });
		setSelectedSearchIds((prev) => {
			const next = new Set(prev);
			next.delete(ref.id);
			return next;
		});
		if (!silent) {
			showToast(
				"success",
				`Added "${ref.title || urlToTitle(ref.url)}" to Turn #${messageIndex + 1}`,
			);
		}
	};

	const handleAddSelectedSearchResults = () => {
		const chosen = (searchResults || []).filter((r) =>
			selectedSearchIds.has(r.id),
		);
		chosen.forEach((r) => {
			onAddSearchResult({ ...r, messageIndex });
		});
		setSelectedSearchIds(new Set());
		showToast(
			"success",
			`Added ${chosen.length} reference${chosen.length !== 1 ? "s" : ""} to Turn #${messageIndex + 1}`,
		);
	};

	const handleRemoveReference = (ref: Reference) => {
		const refName = ref.title || urlToTitle(ref.url);

		// Store the reference for undo
		const undoData = { ...ref };

		// Remove the reference
		onRemoveReference(ref.id);

		// Show toast with undo action
		const toastId = showToast("info", `Removed "${refName}"`, {
			duration: 8000,
			actionLabel: "Undo",
			onAction: () => {
				// Re-add the reference using the add handler (silent to avoid double toast)
				onAddSearchResult(undoData);
				showToast("success", `Restored "${refName}"`);
				if (undoTimerRef.current) {
					window.clearTimeout(undoTimerRef.current);
				}
			},
		});

		// Clear undo timer if exists
		if (undoTimerRef.current) {
			window.clearTimeout(undoTimerRef.current);
		}

		undoTimerRef.current = window.setTimeout(() => {
			dismiss(toastId);
		}, 8000) as unknown as number;
	};

	const renderSearchResult = (r: Reference) => {
		const already = urlsInTurn.has(normalizeUrl(r.url));
		return (
			<div
				key={r.id}
				className={cn(
					"rounded-lg border bg-white p-3 text-xs",
					already && "opacity-60",
					selectedSearchIds.has(r.id) && !already && "ring-2 ring-violet-300",
				)}
			>
				<div className="flex items-start justify-between gap-2">
					<div className="min-w-0 flex-1">
						<div
							className="truncate font-medium"
							title={r.title || urlToTitle(r.url)}
						>
							{r.title || urlToTitle(r.url)}
						</div>
						<a
							className="inline-flex max-w-full items-center gap-1 truncate text-[11px] text-violet-700 underline"
							onClick={(e) => {
								e.preventDefault();
								onOpenReference(r);
							}}
							href={normalizeUrl(r.url)}
							target="_blank"
							rel="noreferrer"
						>
							<ExternalLink className="h-3 w-3" /> {normalizeUrl(r.url)}
						</a>
					</div>
					<div className="flex flex-none items-center gap-2">
						<label
							className="flex items-center gap-1"
							title="Select for bulk add"
						>
							<input
								type="checkbox"
								checked={selectedSearchIds.has(r.id)}
								onChange={(e) =>
									handleToggleSearchSelect(r.id, e.target.checked)
								}
								disabled={already}
							/>
							<span className="text-[11px]">Select</span>
						</label>
						<button
							type="button"
							className={cn(
								"rounded-md border px-2 py-1 text-[11px]",
								already
									? "border-slate-200 text-slate-400 cursor-not-allowed"
									: "border-violet-300 text-violet-700 hover:bg-violet-50",
							)}
							onClick={() => !already && handleAddSearchResult(r)}
							disabled={already}
							title={
								already ? "Already added to this turn" : "Add to this turn"
							}
						>
							{already ? "Added" : "Add"}
						</button>
					</div>
				</div>
			</div>
		);
	};

	const renderReferenceCard = (r: Reference, index: number) => {
		const len = r.keyParagraph?.trim().length || 0;

		return (
			<div key={r.id} className="rounded-xl border p-3">
				<div className="flex items-start justify-between gap-2">
					<div className="min-w-0 flex-1">
						<div className="break-words text-sm font-medium">
							[{index + 1}] {r.title || urlToTitle(r.url)}
						</div>
						<a
							className="inline-flex max-w-full items-center gap-1 truncate text-xs text-violet-700 underline"
							onClick={(e) => {
								e.preventDefault();
								onOpenReference(r);
							}}
							href={normalizeUrl(r.url)}
							target="_blank"
							rel="noreferrer"
						>
							<ExternalLink className="h-3.5 w-3.5" /> {normalizeUrl(r.url)}
						</a>
					</div>
					{!readOnly && (
						<div className="flex flex-none shrink-0 items-center gap-3">
							{/* Bonus toggle */}
							<label
								className="flex items-center gap-2 whitespace-nowrap text-xs"
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
								onClick={() => handleRemoveReference(r)}
							>
								<Trash2 className="h-4 w-4" />
							</button>
						</div>
					)}
					{readOnly && r.bonus && (
						<span className="flex-none whitespace-nowrap text-xs text-violet-700 bg-violet-100 px-2 py-1 rounded">
							Bonus
						</span>
					)}
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
						<div className="mt-3 flex items-center gap-2 text-xs font-medium">
							<span>Key paragraph {requireKeyPara ? "" : "(optional)"}</span>
							{!readOnly && (
								<span
									className={cn(
										"rounded-full px-2 py-0.5",
										len >= 40
											? "bg-emerald-100 text-emerald-900"
											: "bg-slate-100 text-slate-700",
									)}
								>
									{len}/40 (2000 max)
								</span>
							)}
						</div>
						<textarea
							className={cn(
								"mt-1 w-full rounded-xl border p-2 text-sm",
								readOnly
									? "bg-slate-50 text-slate-700 cursor-default"
									: "focus:outline-none focus:ring-2 focus:ring-violet-300",
							)}
							placeholder={
								readOnly
									? ""
									: "Summarize the most relevant passage in your own words… (may be required based on configuration)"
							}
							value={r.keyParagraph || ""}
							onChange={
								readOnly
									? undefined
									: (e) =>
											onUpdateReference(r.id, { keyParagraph: e.target.value })
							}
							readOnly={readOnly}
							rows={
								readOnly
									? Math.max(1, Math.ceil((r.keyParagraph || "").length / 60))
									: 4
							}
						/>
					</>
				)}
			</div>
		);
	};

	return (
		<ModalPortal>
			<div
				className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
				role="presentation"
			>
				<button
					type="button"
					onClick={onClose}
					tabIndex={-1}
					className="absolute inset-0 h-full w-full cursor-pointer bg-transparent focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/60"
					aria-label="Close modal"
				>
					<span className="sr-only">Close modal</span>
				</button>
				<div
					className="relative z-10 max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl"
					onClick={(e) => e.stopPropagation()}
					onKeyDown={(e) => {
						// Allow Escape to close, but let other keys pass through
						if (e.key === "Escape") {
							e.stopPropagation();
							onClose();
						}
					}}
					role="dialog"
					aria-modal="true"
					aria-labelledby={titleId}
				>
					{/* Header */}
					<div className="flex items-center justify-between border-b border-slate-200 p-4">
						<div>
							<h2 id={titleId} className="text-lg font-semibold text-slate-900">
								References for Turn #{messageIndex + 1}
							</h2>
							<p className="text-sm text-slate-600">
								{turnRefs.length} reference{turnRefs.length > 1 ? "s" : ""}
							</p>
						</div>
						<button
							type="button"
							onClick={onClose}
							className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
							title="Close"
						>
							<X className="h-5 w-5" />
						</button>
					</div>

					{/* Content */}
					<div className="max-h-[calc(90vh-8rem)] overflow-auto p-4 space-y-6">
						{/* Search Section - Hide in read-only mode */}
						{!readOnly && (
							<div className="rounded-xl border bg-violet-50 p-4">
								<div className="mb-2 flex items-center gap-2">
									<SearchIcon className="h-4 w-4 text-violet-700" />
									<div className="text-sm font-medium text-violet-800">
										Add References via Search
									</div>
								</div>
								<div className="flex items-center gap-2">
									<input
										ref={searchInputRef}
										value={query}
										onChange={(e) => setQuery(e.target.value)}
										onKeyDown={(e) => {
											if (e.key === "Enter") {
												e.preventDefault();
												handleSearchSubmit();
											}
										}}
										placeholder="Search for documents"
										className="flex-1 rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
									/>
									<button
										type="button"
										onClick={handleSearchSubmit}
										disabled={searching}
										className="inline-flex items-center gap-2 rounded-xl border border-violet-300 bg-violet-600 px-3 py-2 text-sm text-white shadow hover:bg-violet-700 disabled:opacity-50"
									>
										<Upload className="h-4 w-4" /> Search
									</button>
								</div>
								{searchResults.length > 0 && (
									<div className="mt-3 space-y-2">
										<div className="flex items-center justify-between">
											<div className="text-xs font-medium text-violet-800">
												Search Results ({searchResults.length})
											</div>
											<button
												type="button"
												className="rounded-lg border border-violet-300 bg-white px-2 py-1 text-[11px] font-medium text-violet-700 hover:bg-violet-50 disabled:opacity-40"
												onClick={handleAddSelectedSearchResults}
												disabled={selectedSearchIds.size === 0}
												title="Add all selected results to this turn"
											>
												Add {selectedSearchIds.size || 0} Selected
											</button>
										</div>
										<div className="max-h-[28vh] space-y-2 overflow-auto pr-1">
											{searchResults.map((r) => renderSearchResult(r))}
										</div>
									</div>
								)}
								{searchResults.length === 0 && query.trim() && !searching && (
									<div className="mt-3 text-xs text-slate-600">
										No results. Try refining your query.
									</div>
								)}
								{!query.trim() && (
									<div className="mt-3 text-[11px] text-slate-600">
										Type a query and press Enter to search. Added references
										will appear below.
									</div>
								)}
							</div>
						)}

						{/* References List */}
						{turnRefs.length === 0 ? (
							<div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center">
								<p className="text-sm text-slate-600">
									No references for this turn yet. Use search above to add
									references.
								</p>
							</div>
						) : (
							<div className="space-y-3">
								{/* Turn-specific references */}
								{turnRefs.map((r, i) => renderReferenceCard(r, i))}
							</div>
						)}
					</div>

					{/* Footer */}
					<div className="border-t border-slate-200 bg-violet-50 p-3">
						<p className="text-xs text-slate-700">
							To approve: ensure all references are properly configured.
							{requireVisit && " All references must be visited."}
							{requireKeyPara &&
								" Key paragraphs required for selected references."}
							{!requireVisit &&
								!requireKeyPara &&
								" Visit status and key paragraphs are optional."}
						</p>
					</div>

					{/* Toasts - positioned within modal */}
					{toasts.length > 0 && (
						<div className="pointer-events-none absolute bottom-4 right-4 z-10 space-y-2">
							{toasts.map((t) => (
								<div
									key={t.id}
									className={cn(
										"pointer-events-auto flex min-w-[260px] items-center justify-between gap-3 rounded-xl border bg-white px-3 py-2 shadow-lg",
										t.kind === "success" && "border-emerald-300",
										t.kind === "error" && "border-rose-300",
										t.kind === "info" && "border-violet-300",
									)}
								>
									<div className="text-sm">{t.msg}</div>
									{t.actionLabel && t.onAction && (
										<button
											type="button"
											className="rounded-lg border border-violet-300 px-2 py-1 text-xs text-violet-700 hover:bg-violet-50"
											onClick={() => {
												t.onAction?.();
												dismiss(t.id);
											}}
										>
											{t.actionLabel}
										</button>
									)}
								</div>
							))}
						</div>
					)}
				</div>
			</div>
		</ModalPortal>
	);
}
