import { useState, useMemo } from "react";
import { X, Search, Tag as TagIcon } from "lucide-react";
import { useTagGlossary } from "../../hooks/useTagGlossary";

interface TagGlossaryModalProps {
	onClose: () => void;
}

export default function TagGlossaryModal({ onClose }: TagGlossaryModalProps) {
	const { rawGlossary: glossary, loading, error } = useTagGlossary();
	const [searchQuery, setSearchQuery] = useState("");
	const [selectedType, setSelectedType] = useState<string>("all");

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
				return group.tags?.some(
					(tag) =>
						tag.key?.toLowerCase().includes(query) ||
						tag.description?.toLowerCase().includes(query)
				) ?? false;
			})
			.map((group) => {
				if (!query) return group;

				// Filter tags within group
				const filteredTags = group.tags?.filter(
					(tag) =>
						tag.key?.toLowerCase().includes(query) ||
						tag.description?.toLowerCase().includes(query)
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
			{ all: 0, manual: 0, computed: 0, custom: 0 } as Record<string, number>
		);
	}, [glossary]);

	return (
		<div
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
					<div className="flex items-center gap-2">
						<span className="text-sm font-medium text-gray-700">Filter:</span>
						{(["all", "manual", "computed", "custom"] as const).map((type) => (
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
						))}
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
										{group.tags?.map((tag) => (
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
													{tag.description ? (
														<p className="text-sm text-gray-700">
															{tag.description}
														</p>
													) : (
														<p className="text-sm italic text-gray-400">
															No description available
														</p>
													)}
												</div>
											</div>
										)) ?? []}
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
									Showing {filteredGroups.reduce((sum, g) => sum + (g.tags?.length ?? 0), 0)}{" "}
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
