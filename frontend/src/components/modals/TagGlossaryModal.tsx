import { Edit2, Plus, Search, Tag as TagIcon, Trash2, X } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useTagGlossary } from "../../hooks/useTagGlossary";
import useModalKeys from "../../hooks/useModalKeys";
import { createTagDefinition, deleteTagDefinition } from "../../services/tags";

interface TagGlossaryModalProps {
	onClose: () => void;
}

export default function TagGlossaryModal({ onClose }: TagGlossaryModalProps) {
	const formId = useId();
	const { rawGlossary: glossary, loading, error, refresh } = useTagGlossary();
	const [searchQuery, setSearchQuery] = useState("");
	const [selectedType, setSelectedType] = useState<string>("all");
	const [editingTag, setEditingTag] = useState<string | null>(null);
	const [editDescription, setEditDescription] = useState("");
	const [showNewTagForm, setShowNewTagForm] = useState(false);
	const [newTagKey, setNewTagKey] = useState("");
	const [newTagDescription, setNewTagDescription] = useState("");
	const [submitting, setSubmitting] = useState(false);

	// Handle ESC key to close modal
	useModalKeys({
		enabled: true,
		onClose,
		busy: submitting,
	});

	const filteredGroups = useMemo(() => {
		if (!glossary?.groups) return [];

		const query = searchQuery.toLowerCase();
		return glossary.groups
			.filter((group) => {
				if (selectedType !== "all" && group.type !== selectedType) {
					return false;
				}
				if (!query) return true;

				// Search in group name or description
				if (
					group.name?.toLowerCase().includes(query) ||
					group.description?.toLowerCase().includes(query)
				) {
					return true;
				}

				// Search in tag keys or descriptions
				return (
					group.tags?.some(
						(tag) =>
							tag.key?.toLowerCase().includes(query) ||
							tag.description?.toLowerCase().includes(query),
					) ?? false
				);
			})
			.map((group) => {
				if (!query) return group;

				// Filter tags within group
				const filteredTags =
					group.tags?.filter(
						(tag) =>
							tag.key?.toLowerCase().includes(query) ||
							tag.description?.toLowerCase().includes(query),
					) ?? [];

				return {
					...group,
					tags: filteredTags,
				};
			})
			.filter((group) => (group.tags?.length ?? 0) > 0);
	}, [glossary, searchQuery, selectedType]);

	const tagTypeCounts = useMemo(() => {
		if (!glossary?.groups) return { all: 0, manual: 0, computed: 0, custom: 0 };

		return glossary.groups.reduce(
			(acc, group) => {
				const count = group.tags?.length ?? 0;
				acc.all += count;
				const type = group.type ?? "manual";
				acc[type] = (acc[type] || 0) + count;
				return acc;
			},
			{ all: 0, manual: 0, computed: 0, custom: 0 } as Record<string, number>,
		);
	}, [glossary]);

	const handleStartEdit = (tagKey: string, currentDescription: string) => {
		setEditingTag(tagKey);
		setEditDescription(currentDescription);
	};

	const handleCancelEdit = () => {
		setEditingTag(null);
		setEditDescription("");
	};

	const handleSaveEdit = async (tagKey: string) => {
		if (!editDescription.trim()) return;

		setSubmitting(true);
		try {
			await createTagDefinition(tagKey, editDescription.trim());
			await refresh();
			setEditingTag(null);
			setEditDescription("");
		} catch (err) {
			alert(
				`Failed to save tag definition: ${err instanceof Error ? err.message : String(err)}`,
			);
		} finally {
			setSubmitting(false);
		}
	};

	const handleDelete = async (tagKey: string) => {
		if (!confirm(`Delete custom tag definition for "${tagKey}"?`)) return;

		setSubmitting(true);
		try {
			await deleteTagDefinition(tagKey);
			await refresh();
		} catch (err) {
			alert(
				`Failed to delete tag definition: ${err instanceof Error ? err.message : String(err)}`,
			);
		} finally {
			setSubmitting(false);
		}
	};

	const handleCreateNew = async () => {
		if (!newTagKey.trim() || !newTagDescription.trim()) {
			alert("Both tag key and description are required");
			return;
		}

		setSubmitting(true);
		try {
			await createTagDefinition(newTagKey.trim(), newTagDescription.trim());
			await refresh();
			setShowNewTagForm(false);
			setNewTagKey("");
			setNewTagDescription("");
		} catch (err) {
			alert(
				`Failed to create tag definition: ${err instanceof Error ? err.message : String(err)}`,
			);
		} finally {
			setSubmitting(false);
		}
	};

	const tagKeyId = `${formId}-tag-key`;
	const tagDescriptionId = `${formId}-tag-description`;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: Modal backdrop with click-to-close is a common accessible pattern
		<div
			role="presentation"
			className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
			onClick={(e) => {
				if (e.target === e.currentTarget) onClose();
			}}
		>
			<div className="relative flex h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
				{/* Header */}
				<div className="flex items-center justify-between border-b px-6 py-4">
					<div className="flex items-center gap-3">
						<TagIcon className="h-6 w-6 text-violet-600" />
						<div>
							<h2 className="text-2xl font-semibold">Tag Glossary</h2>
							<p className="text-sm text-gray-600">
								Browse and search all available tags
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="rounded-lg p-2 hover:bg-gray-100"
						title="Close"
					>
						<X className="h-5 w-5" />
					</button>
				</div>

				{/* Controls */}
				<div className="border-b px-6 py-4">
					<div className="mb-3 flex items-center gap-2">
						<div className="relative flex-1">
							<Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								placeholder="Search tags and descriptions..."
								className="w-full rounded-lg border px-10 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
							/>
							{searchQuery && (
								<button
									type="button"
									onClick={() => setSearchQuery("")}
									className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
									title="Clear search"
								>
									<X className="h-4 w-4" />
								</button>
							)}
						</div>
					</div>

					{/* Type filters */}
					<div className="flex items-center justify-between gap-2">
						<div className="flex items-center gap-2">
							<span className="text-sm font-medium text-gray-700">Filter:</span>
							{(["all", "manual", "computed", "custom"] as const).map(
								(type) => (
									<button
										key={type}
										type="button"
										onClick={() => setSelectedType(type)}
										className={`rounded-lg px-3 py-1 text-sm transition-colors ${
											selectedType === type
												? "bg-violet-600 text-white"
												: "bg-gray-100 text-gray-700 hover:bg-gray-200"
										}`}
									>
										{type.charAt(0).toUpperCase() + type.slice(1)}{" "}
										<span className="text-xs opacity-75">
											({tagTypeCounts[type]})
										</span>
									</button>
								),
							)}
						</div>
						<button
							type="button"
							onClick={() => setShowNewTagForm(!showNewTagForm)}
							className="flex items-center gap-1 rounded-lg bg-violet-600 px-3 py-1 text-sm text-white transition-colors hover:bg-violet-700"
							title="Add custom tag definition"
						>
							<Plus className="h-4 w-4" />
							New Custom Tag
						</button>
					</div>
				</div>

				{/* Content */}
				<div className="flex-1 overflow-y-auto px-6 py-4">
					{loading && (
						<div className="flex items-center justify-center py-12">
							<div className="text-gray-500">Loading tag glossary...</div>
						</div>
					)}

					{error && (
						<div className="rounded-lg bg-red-50 p-4 text-red-700">
							<p className="font-medium">Error loading glossary</p>
							<p className="text-sm">{error.message}</p>
						</div>
					)}

					{!loading && !error && filteredGroups.length === 0 && (
						<div className="flex flex-col items-center justify-center py-12 text-gray-500">
							<Search className="mb-3 h-12 w-12 opacity-30" />
							<p className="text-lg font-medium">No tags found</p>
							<p className="text-sm">
								Try adjusting your search or filter criteria
							</p>
						</div>
					)}

					{/* New Custom Tag Form */}
					{showNewTagForm && (
						<div className="mb-4 rounded-lg border border-violet-200 bg-violet-50 p-4">
							<h3 className="mb-3 text-lg font-semibold text-gray-900">
								New Custom Tag
							</h3>
							<div className="space-y-3">
								<div>
									<label
										htmlFor={tagKeyId}
										className="block text-sm font-medium text-gray-700 mb-1"
									>
										Tag Key
									</label>
									<input
										id={tagKeyId}
										type="text"
										value={newTagKey}
										onChange={(e) => setNewTagKey(e.target.value)}
										placeholder="e.g., source:custom_value"
										className="w-full rounded-lg border px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
										disabled={submitting}
									/>
								</div>
								<div>
									<label
										htmlFor={tagDescriptionId}
										className="block text-sm font-medium text-gray-700 mb-1"
									>
										Description
									</label>
									<textarea
										id={tagDescriptionId}
										value={newTagDescription}
										onChange={(e) => setNewTagDescription(e.target.value)}
										placeholder="Description of this tag..."
										rows={3}
										className="w-full rounded-lg border px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
										disabled={submitting}
									/>
								</div>
								<div className="flex gap-2">
									<button
										type="button"
										onClick={handleCreateNew}
										disabled={
											submitting ||
											!newTagKey.trim() ||
											!newTagDescription.trim()
										}
										className="rounded-lg bg-violet-600 px-4 py-2 text-sm text-white transition-colors hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
									>
										{submitting ? "Creating..." : "Create Tag"}
									</button>
									<button
										type="button"
										onClick={() => {
											setShowNewTagForm(false);
											setNewTagKey("");
											setNewTagDescription("");
										}}
										disabled={submitting}
										className="rounded-lg bg-gray-200 px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-300 disabled:opacity-50"
									>
										Cancel
									</button>
								</div>
							</div>
						</div>
					)}

					{!loading && !error && (
						<div className="space-y-6">
							{filteredGroups.map((group) => (
								<div
									key={group.name}
									className="rounded-lg border bg-gray-50 p-4"
								>
									<div className="mb-3 flex items-start justify-between">
										<div>
											<h3 className="text-lg font-semibold text-gray-900">
												{group.name}
											</h3>
											{group.description && (
												<p className="mt-1 text-sm text-gray-600">
													{group.description}
												</p>
											)}
										</div>
										<span
											className={`rounded-full px-2 py-1 text-xs font-medium ${
												group.type === "manual"
													? "bg-blue-100 text-blue-700"
													: group.type === "computed"
														? "bg-green-100 text-green-700"
														: "bg-purple-100 text-purple-700"
											}`}
										>
											{group.type}
										</span>
									</div>

									<div className="space-y-2">
										{group.tags?.map((tag) => {
											const isCustomTag = group.type === "custom";
											const isEditing = editingTag === tag.key;

											return (
												<div
													key={tag.key}
													className="flex items-start gap-3 rounded-lg bg-white p-3 shadow-sm"
												>
													<div className="flex-shrink-0">
														<span className="inline-flex items-center rounded-full bg-violet-100 px-2 py-1 text-xs font-medium text-violet-800">
															{tag.key}
														</span>
													</div>
													<div className="flex-1">
														{isEditing ? (
															<div className="space-y-2">
																<textarea
																	value={editDescription}
																	onChange={(e) =>
																		setEditDescription(e.target.value)
																	}
																	className="w-full rounded border px-2 py-1 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
																	rows={2}
																	disabled={submitting}
																/>
																<div className="flex gap-2">
																	<button
																		type="button"
																		onClick={() => handleSaveEdit(tag.key)}
																		disabled={
																			submitting || !editDescription.trim()
																		}
																		className="rounded bg-violet-600 px-3 py-1 text-xs text-white hover:bg-violet-700 disabled:opacity-50"
																	>
																		Save
																	</button>
																	<button
																		type="button"
																		onClick={handleCancelEdit}
																		disabled={submitting}
																		className="rounded bg-gray-200 px-3 py-1 text-xs text-gray-700 hover:bg-gray-300 disabled:opacity-50"
																	>
																		Cancel
																	</button>
																</div>
															</div>
														) : tag.description ? (
															<p className="text-sm text-gray-700">
																{tag.description}
															</p>
														) : (
															<p className="text-sm italic text-gray-400">
																No description available
															</p>
														)}
													</div>
													{isCustomTag && !isEditing && (
														<div className="flex gap-1">
															<button
																type="button"
																onClick={() =>
																	handleStartEdit(
																		tag.key,
																		tag.description || "",
																	)
																}
																className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-violet-600"
																title="Edit description"
																disabled={submitting}
															>
																<Edit2 className="h-4 w-4" />
															</button>
															<button
																type="button"
																onClick={() => handleDelete(tag.key)}
																className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-red-600"
																title="Delete custom tag"
																disabled={submitting}
															>
																<Trash2 className="h-4 w-4" />
															</button>
														</div>
													)}
												</div>
											);
										}) ?? []}
									</div>
								</div>
							))}
						</div>
					)}
				</div>

				{/* Footer */}
				<div className="border-t px-6 py-3">
					<div className="flex items-center justify-between text-sm text-gray-600">
						<div>
							{glossary && (
								<span>
									Showing{" "}
									{filteredGroups.reduce(
										(sum, g) => sum + (g.tags?.length ?? 0),
										0,
									)}{" "}
									of {tagTypeCounts.all} tags
								</span>
							)}
						</div>
						<div className="text-xs">
							Version: {glossary?.version || "Unknown"}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
