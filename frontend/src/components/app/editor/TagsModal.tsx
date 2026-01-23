import { Lock, Plus, Tag, X } from "lucide-react";
import { useId, useState } from "react";
import useModalKeys from "../../../hooks/useModalKeys";
import { addTags, validateExclusiveTags } from "../../../services/tags";
import ModalPortal from "../../modals/ModalPortal";

type Props = {
	isOpen: boolean;
	onClose: () => void;
	messageIndex?: number; // optional - omitted for ground-truth-level tags
	tags: string[]; // current manual tags for this turn or ground truth
	computedTags?: string[]; // system-generated tags (read-only)
	availableTags?: string[]; // all known tags across item
	onUpdateTags: (tags: string[]) => void;
	onRefreshTags?: () => void | Promise<void>;
};

export default function TagsModal({
	isOpen,
	onClose,
	messageIndex,
	tags,
	computedTags = [],
	availableTags = [],
	onUpdateTags,
	onRefreshTags,
}: Props) {
	const titleId = useId();
	const [newTag, setNewTag] = useState("");
	const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
	const [validationError, setValidationError] = useState<string | null>(null);
	const [schemaError, setSchemaError] = useState<string | null>(null);

	// Handle keyboard shortcuts (Escape to close)
	useModalKeys({
		enabled: isOpen,
		onClose,
	});

	// Derive grouped tags by prefix before ':'
	const grouped = (() => {
		const groups: Record<string, string[]> = {};
		availableTags.forEach((tag) => {
			const [prefix, rest] = tag.includes(":")
				? tag.split(":", 2)
				: ["misc", tag];
			const key = prefix || "misc";
			if (!groups[key]) groups[key] = [];
			groups[key].push(rest);
		});
		// Sort each group's items
		for (const k of Object.keys(groups)) {
			groups[k].sort((a, b) => a.localeCompare(b));
		}
		return Object.entries(groups)
			.sort((a, b) => a[0].localeCompare(b[0]))
			.map(([group, names]) => ({ group, names }));
	})();

	// Toggle all groups in the same row (4-column grid) when one is clicked
	const toggleRowForGroup = (group: string) => {
		const index = grouped.findIndex((g) => g.group === group);
		if (index === -1) return;
		const row = Math.floor(index / 4);
		const rowGroups = grouped
			.filter((_, i) => Math.floor(i / 4) === row)
			.map((g) => g.group);
		setOpenGroups((prev) => {
			const allRowOpen = rowGroups.every((rg) => prev.has(rg));
			const next = new Set(prev);
			if (allRowOpen) {
				// close all in row
				rowGroups.forEach((rg) => {
					next.delete(rg);
				});
			} else {
				// open all in row
				rowGroups.forEach((rg) => {
					next.add(rg);
				});
			}
			return next;
		});
	};

	const isSelected = (fullTag: string) => tags.includes(fullTag);

	const handleToggleTag = async (prefix: string, name: string) => {
		const full = `${prefix}:${name}`;
		let updatedTags: string[];

		if (isSelected(full)) {
			updatedTags = tags.filter((t) => t !== full);
		} else {
			updatedTags = [...tags, full];
		}

		// Validate exclusive groups before applying
		try {
			const error = await validateExclusiveTags(updatedTags);
			if (error) {
				setValidationError(error);
				setSchemaError(null);
				return;
			}
			setValidationError(null);
			setSchemaError(null);
			onUpdateTags(updatedTags);
		} catch (err) {
			// Catch schema loading errors
			setSchemaError(
				err instanceof Error ? err.message : "Failed to load tag schema",
			);
			setValidationError(null);
		}
	};

	if (!isOpen) return null;

	const handleAddTag = async () => {
		const trimmed = newTag.trim();
		if (!trimmed) return;
		// If user enters prefix:name or just name
		const full = trimmed.includes(":") ? trimmed : `custom:${trimmed}`;
		if (tags.includes(full)) {
			setNewTag("");
			return;
		}

		const updatedTags = [...tags, full];
		// Validate exclusive groups before applying
		try {
			const error = await validateExclusiveTags(updatedTags);
			if (error) {
				setValidationError(error);
				setSchemaError(null);
				return;
			}

			setValidationError(null);
			setSchemaError(null);
			onUpdateTags(updatedTags);
			setNewTag("");

			// Add to global registry and refresh available tags
			try {
				await addTags([full]);
				if (onRefreshTags) {
					await onRefreshTags();
				}
			} catch (error) {
				console.error("Failed to add tag to global registry:", error);
			}
		} catch (err) {
			// Catch schema loading errors
			setSchemaError(
				err instanceof Error ? err.message : "Failed to load tag schema",
			);
			setValidationError(null);
		}
	};

	// Removed explicit remove handler (handled inline via checkbox toggle or Remove button)

	const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter") {
			e.preventDefault();
			handleAddTag();
		}
	};

	// Calculate pair-based turn number (each user+agent pair is one turn)
	const turnNumber =
		messageIndex !== undefined ? Math.floor(messageIndex / 2) + 1 : null;

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
					className="relative z-10 max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl"
					onClick={(e) => e.stopPropagation()}
					onKeyDown={(e) => e.stopPropagation()}
					role="dialog"
					aria-modal="true"
					aria-labelledby={titleId}
				>
					{/* Header */}
					<div className="flex items-center justify-between border-b border-slate-200 bg-violet-50 p-4">
						<div className="flex items-center gap-2">
							<Tag className="h-5 w-5 text-violet-700" />
							<div>
								<h2
									id={titleId}
									className="text-lg font-semibold text-slate-900"
								>
									Manage Tags
								</h2>
								{turnNumber !== null ? (
									<p className="text-sm text-slate-600">
										Agent Turn #{turnNumber} (index {messageIndex})
									</p>
								) : (
									<p className="text-sm text-slate-600">
										Ground Truth Level Tags
									</p>
								)}
							</div>
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
					<div className="max-h-[calc(90vh-12rem)] overflow-auto p-4">
						{/* Computed Tags - Read-only display */}
						{computedTags && computedTags.length > 0 && (
							<div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
								<div className="mb-2 text-sm font-medium text-slate-600 flex items-center gap-2">
									<Lock className="h-4 w-4" />
									Auto-generated Tags
								</div>
								<div className="flex flex-wrap gap-2">
									{computedTags.map((tag) => (
										<span
											key={tag}
											className="inline-flex items-center gap-1 rounded-full bg-white border border-slate-200 px-3 py-1 text-sm text-slate-600"
										>
											<Lock className="h-3 w-3 text-slate-400" />
											{tag}
										</span>
									))}
								</div>
								<p className="mt-2 text-xs text-slate-500">
									These tags are automatically generated and cannot be edited.
								</p>
							</div>
						)}

						{/* Add new tag */}
						<div className="mb-4 rounded-xl border bg-violet-50 p-4">
							<div className="mb-2 text-sm font-medium text-violet-800">
								Add Tag
							</div>
							<div className="flex items-center gap-2">
								<input
									type="text"
									value={newTag}
									onChange={(e) => setNewTag(e.target.value)}
									onKeyDown={handleKeyDown}
									placeholder="Enter tag name..."
									className="flex-1 rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
								/>
								<button
									type="button"
									onClick={handleAddTag}
									disabled={!newTag.trim()}
									className="inline-flex items-center gap-2 rounded-xl border border-violet-300 bg-violet-600 px-3 py-2 text-sm text-white shadow hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
									title="Add tag"
								>
									<Plus className="h-4 w-4" />
									Add
								</button>
							</div>
							<p className="mt-2 text-xs text-slate-600">
								Press Enter to add. Tags help categorize conversation turns for
								analysis and filtering.
							</p>
						</div>

						{/* Tag Groups & Selection */}
						<div className="mt-6">
							<div className="mb-2 text-sm font-medium text-slate-700 flex items-center justify-between">
								<span>All Tags ({availableTags.length})</span>
								<span className="text-xs text-slate-500">
									Click a group to expand; select tags to attach to this turn.
								</span>
							</div>
							{availableTags.length === 0 && (
								<div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center">
									<p className="text-sm text-slate-600">
										No existing tags found. Add custom tags above.
									</p>
								</div>
							)}
							{availableTags.length > 0 && (
								<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
									{grouped.map(({ group, names }) => {
										const open = openGroups.has(group);
										// Count selected tags within this group
										const selectedCount = names.reduce(
											(acc, n) => (isSelected(`${group}:${n}`) ? acc + 1 : acc),
											0,
										);
										return (
											<div
												key={group}
												className="rounded-xl border border-slate-200 bg-white"
											>
												<button
													type="button"
													className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium hover:bg-slate-50"
													onClick={() => toggleRowForGroup(group)}
													title="Toggle entire row"
													aria-expanded={open}
												>
													<span className="flex items-center gap-2">
														<Tag className="h-4 w-4 text-violet-600" />
														{group}
														{selectedCount > 0 && (
															<span
																className="ml-1 rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700"
																title={`${selectedCount} tag${selectedCount !== 1 ? "s" : ""} selected`}
															>
																{selectedCount}
															</span>
														)}
													</span>
													<span className="text-xs text-slate-500">
														{open ? "Hide" : "Show"} ({names.length})
													</span>
												</button>
												{open && (
													<div className="border-t border-slate-200 p-3 flex flex-wrap gap-2">
														{names.map((n) => {
															const full = `${group}:${n}`;
															const selected = isSelected(full);
															return (
																<button
																	key={full}
																	type="button"
																	onClick={() => handleToggleTag(group, n)}
																	className={
																		"rounded-full px-3 py-1 text-[11px] font-medium transition-colors border " +
																		(selected
																			? "bg-violet-600 text-white border-violet-600 hover:bg-violet-700"
																			: "bg-amber-100 text-amber-800 border-amber-200 hover:bg-amber-200")
																	}
																	title={
																		selected
																			? "Click to remove"
																			: "Click to add"
																	}
																>
																	{n}
																</button>
															);
														})}
													</div>
												)}
											</div>
										);
									})}
								</div>
							)}
						</div>
					</div>

					{/* Footer */}
					<div className="border-t border-slate-200 bg-violet-50 p-4">
						<div className="flex items-start justify-between gap-4">
							{/* Content column grows */}
							<div className="flex-1 min-w-0">
								{!validationError && !schemaError && (
									<p className="text-xs text-slate-700">
										Tags help organize and filter conversations by topic,
										intent, or category.
									</p>
								)}

								{validationError && (
									<div className="rounded border border-red-300 bg-red-50 p-3 mb-2 text-red-800">
										<strong>Invalid tag selection:</strong>
										<div className="mt-1">{validationError}</div>
									</div>
								)}

								{schemaError && (
									<div className="rounded border border-red-300 bg-red-50 p-3 mb-2 text-red-800">
										<strong>Error:</strong>
										<div className="mt-1">{schemaError}</div>
									</div>
								)}
							</div>

							{/* Button column does not grow */}
							<button
								type="button"
								onClick={onClose}
								className="flex-none rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
							>
								Done
							</button>
						</div>
					</div>
				</div>
			</div>
		</ModalPortal>
	);
}
