import { useEffect, useState } from "react";
import AppHeader from "./components/app/AppHeader";
import InstructionsPane from "./components/app/InstructionsPane";
import CuratePane from "./components/app/pages/CuratePane";
import ReferencesSection from "./components/app/pages/ReferencesSection";
import StatsPage from "./components/app/pages/StatsPage";
import type { QuestionsExplorerItem } from "./components/app/QuestionsExplorer";
import QuestionsExplorer from "./components/app/QuestionsExplorer";
import QueueSidebar from "./components/app/QueueSidebar";
import Toasts from "./components/common/Toasts";
import InspectItemModal from "./components/modals/InspectItemModal";
import TagGlossaryModal from "./components/modals/TagGlossaryModal";
import DEMO_MODE from "./config/demo";
import { runSelfTests } from "./dev/self-tests";
import useGlobalHotkeys from "./hooks/useGlobalHotkeys";
import useGroundTruth from "./hooks/useGroundTruth";
import { useToasts } from "./hooks/useToasts";
import type { Reference } from "./models/groundTruth";
import { cn, normalizeUrl } from "./models/utils";
import {
	assignItem,
	requestAssignmentsSelfServe,
} from "./services/assignments";
import {
	deleteGroundTruth,
	downloadSnapshot,
	restoreGroundTruth,
} from "./services/groundTruths";
import { getCachedConfig, getRuntimeConfig } from "./services/runtimeConfig";
import { fetchTagSchema } from "./services/tags";
import { validateReferenceUrl } from "./utils/urlValidation";

export default function GTAppDemo() {
	const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
	const [inspectItem, setInspectItem] = useState<QuestionsExplorerItem | null>(
		null,
	);
	const [glossaryOpen, setGlossaryOpen] = useState(false);
	const { toasts, showToast, dismiss } = useToasts();
	const [viewMode, setViewMode] = useState<"curate" | "questions" | "stats">(
		"curate",
	);
	const [selfServeBusy, setSelfServeBusy] = useState(false);
	// Track the current editor mode (single-turn or multi-turn)
	const [editorMode, setEditorMode] = useState<"single" | "multi">("single");

	// Feature hook
	const gt = useGroundTruth();

	// Initialize runtime config on app startup
	useEffect(() => {
		getRuntimeConfig().catch((err) => {
			console.warn("Failed to load runtime config:", err);
		});
	}, []);

	// Fetch tag schema on app startup for validation (caches result for later use)
	useEffect(() => {
		fetchTagSchema().catch((err) => {
			console.warn("Failed to load tag schema:", err);
		});
	}, []);

	// Run self-tests only in development
	useEffect(() => {
		if (import.meta.env?.DEV) runSelfTests();
	}, []);

	const toast = (
		kind: "success" | "error" | "info",
		msg: string,
		opts?: { duration?: number; actionLabel?: string; onAction?: () => void },
	) => showToast(kind, msg, opts);

	function onOpenRef(r: Reference) {
		// Validate URL before opening
		if (!validateReferenceUrl(r.url)) {
			toast("error", "Cannot open reference: Invalid or unsafe URL");
			return;
		}

		// Mark visited and open in external tab
		gt.openReference(r);
		const u = normalizeUrl(r.url);
		let w = window.open(u, "_blank", "noopener,noreferrer");
		// Some browsers may block; attempt original if normalized failed, then notify
		if (!w && u !== r.url) {
			w = window.open(r.url, "_blank", "noopener,noreferrer");
		}
		if (!w) {
			toast("info", "Popup blocked. Allow popups or click again.");
		}
	}

	async function onGenerateAgentTurn(messageIndex: number) {
		const result = await gt.generateAgentTurn(messageIndex);
		if (!result.ok) {
			toast("error", result.error);
		}
		return result;
	}

	async function onSave(nextStatus?: "draft" | "approved") {
		const res = await gt.save(nextStatus);
		if (!res.ok) {
			toast("error", res.error);
			return;
		}
		if (!res.message) {
			toast(
				"success",
				`Saved ${res.saved.id}${nextStatus ? ` – ${nextStatus}` : ""}`,
			);
		} else {
			toast("info", res.message);
		}
	}

	// Global hotkeys: Cmd/Ctrl+S (save draft) and Cmd/Ctrl+Enter (approve)
	useGlobalHotkeys({
		onSaveDraft: () => onSave("draft"),
		onApprove: () => onSave("approved"),
		canApprove: !gt.saving && !gt.current?.deleted && gt.canApprove,
		enabled: true,
	});

	async function onExportJson() {
		try {
			const name = await downloadSnapshot();
			toast("success", `Downloading ${name}`);
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			toast("error", msg || "Export failed");
		}
	}

	async function toggleDeletedFlag(nextDeleted: boolean) {
		const res = await gt.toggleDeletedCurrent(nextDeleted);
		if (!res.ok) {
			toast("error", res.error || "Failed to update delete state");
		} else {
			const saved = res.saved;
			toast(
				nextDeleted ? "info" : "success",
				nextDeleted
					? `Marked ${saved.id} as deleted.`
					: `Restored ${saved.id}.`,
			);
		}
	}

	return (
		<div className="flex h-screen w-screen flex-col overflow-hidden bg-gradient-to-b from-violet-50 via-white to-white text-slate-900">
			{/* Top accent bar */}
			<div className="h-1 w-full flex-none bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500" />

			<AppHeader
				demoMode={DEMO_MODE}
				sidebarOpen={sidebarOpen}
				onToggleSidebar={() => setSidebarOpen((v) => !v)}
				viewMode={viewMode}
				onToggleViewMode={() =>
					setViewMode((m) => {
						// Allow toggling between curate and questions from any mode
						if (m === "curate") return "questions";
						if (m === "questions") return "curate";
						// If on stats, go back to curate
						return "curate";
					})
				}
				onOpenStats={() => setViewMode("stats")}
				onOpenGlossary={() => setGlossaryOpen(true)}
				onExportJson={onExportJson}
			/>

			<main className="mx-auto flex w-full max-w-none flex-1 flex-col gap-4 p-4 min-h-0">
				{viewMode === "stats" && (
					<StatsPage
						demoMode={DEMO_MODE}
						items={gt.items}
						onBack={() => setViewMode("curate")}
					/>
				)}

				{viewMode === "questions" && (
					<section className="flex flex-1 flex-col rounded-2xl border bg-white p-4 shadow-sm min-h-0 min-w-0">
						<InstructionsPane
							className="mb-4 flex-none"
							title="Questions Review Instructions"
							markdown={`\n### Reviewing Questions\n\n- Scan for duplicates, out-of-scope, or low-quality questions.\n- Use Delete to soft-delete; you can restore later.\n- Open an item to curate details.\n`}
						/>
						<div className="flex flex-1 min-h-0 min-w-0">
							<QuestionsExplorer
								onAssign={async (item) => {
									try {
										// Validate the item has required information
										if (!item.datasetName || !item.bucket) {
											toast(
												"error",
												"Item missing dataset or bucket information",
											);
											return;
										}

										// Call the assign endpoint
										await assignItem(item.datasetName, item.bucket, item.id);

										// Refresh the list to get the updated item
										await gt.refreshList();

										// Set the item as selected and switch to curate mode
										await gt.selectItem(item.id);
										setViewMode("curate");

										toast("success", `Assigned ${item.id} for curation`);
									} catch (error) {
										const message =
											error instanceof Error
												? error.message
												: "Failed to assign item";
										toast("error", message);
									}
								}}
								onInspect={(item) => {
									// Show the item in the inspect modal
									setInspectItem(item);
								}}
								onDelete={async (item) => {
									try {
										const isDeleted = item.deleted || item.status === "deleted";

										// Validate required metadata
										if (!item.datasetName) {
											throw new Error(
												`Item ${item.id} is missing datasetName metadata`,
											);
										}
										if (!item.bucket) {
											throw new Error(
												`Item ${item.id} is missing bucket metadata`,
											);
										}

										if (isDeleted) {
											// Restore: call the backend API directly
											const itemWithEtag = item as typeof item & {
												_etag?: string;
											};
											await restoreGroundTruth(
												item.datasetName,
												item.bucket,
												item.id,
												itemWithEtag._etag,
											);
											toast("success", `Restored ${item.id} to draft status.`);
										} else {
											// Delete: use DELETE endpoint directly
											await deleteGroundTruth(
												item.datasetName,
												item.bucket,
												item.id,
											);
											toast("info", `Marked ${item.id} as deleted.`);
										}
										await gt.refreshList();
									} catch (error) {
										const message =
											error instanceof Error
												? error.message
												: "Failed to update item";
										toast("error", message);
									}
								}}
							/>
						</div>
					</section>
				)}

				{viewMode === "curate" && (
					<div className="grid grid-cols-1 md:grid-cols-12 gap-4">
						{/* Left: Queue */}
						{sidebarOpen && (
							<QueueSidebar
								className="hidden md:block col-span-1 md:col-span-4 lg:col-span-3"
								items={gt.items}
								selectedId={gt.selectedId}
								onSelect={(id) => {
									void gt.selectItem(id);
								}}
								onRefresh={() => {
									gt.refreshList();
									toast("info", "Refreshed queue.");
								}}
								onCopied={(kind, value) => {
									const label =
										kind === "path" ? "Path" : kind === "id" ? "ID" : "Dataset";
									toast("success", `${label} copied: ${value}`);
								}}
								hasUnsavedId={(id) =>
									Boolean(gt.current && id === gt.current.id && gt.hasUnsaved)
								}
								onSelfServe={async () => {
									try {
										setSelfServeBusy(true);
										const config = getCachedConfig();
										const limit = config?.selfServeLimit ?? 10;
										const res = await requestAssignmentsSelfServe(limit);
										await gt.refreshList();
										const count =
											res?.assignedCount ?? res?.assigned?.length ?? 0;
										if (count > 0) {
											toast("success", `Assigned ${count} item(s) to you.`);
										} else {
											toast("info", "No items available to assign.");
										}
									} catch (e) {
										const msg = e instanceof Error ? e.message : String(e);
										toast("error", msg || "Failed to request assignments");
									} finally {
										setSelfServeBusy(false);
									}
								}}
								selfServeBusy={selfServeBusy}
							/>
						)}

						{/* Center: Editor */}
						<CuratePane
							className={cn(
								"col-span-1", // Mobile: full width
								// In multi-turn mode (no references sidebar), take full remaining width
								editorMode === "multi"
									? sidebarOpen
										? "md:col-span-8 lg:col-span-9"
										: "md:col-span-12"
									: sidebarOpen
										? "md:col-span-8 lg:col-span-5"
										: "md:col-span-12 lg:col-span-7",
							)}
							current={gt.current}
							canApprove={gt.canApprove}
							saving={gt.saving}
							onUpdateQuestion={(v) => gt.updateQuestion(v)}
							onUpdateAnswer={(v) => gt.updateAnswer(v)}
							onUpdateComment={(v) => gt.updateComment(v)}
							onUpdateTags={(tags) => gt.updateTags(tags)}
							onUpdateHistory={(history) => gt.updateHistory(history)}
							onDeleteTurn={(messageIndex) => gt.deleteTurn(messageIndex)}
							onGenerateAgentTurn={onGenerateAgentTurn}
							onEditorModeChange={setEditorMode}
							onSaveDraft={() => onSave("draft")}
							onApprove={() => onSave("approved")}
							onUpdateReference={(refId, partial) =>
								gt.updateReference(refId, partial)
							}
							onRemoveReference={(refId) => {
								// In multi-turn mode, the modal shows its own toasts
								gt.removeReferenceWithUndo(refId, (undo, timeoutMs) => {
									if (editorMode === "single") {
										toast("info", "Reference removed.", {
											duration: timeoutMs,
											actionLabel: "Undo",
											onAction: undo,
										});
									}
								});
							}}
							onOpenReference={onOpenRef}
							onAddReferences={(refs) => {
								gt.addReferences(refs);
								// Toast is shown in the modal for multi-turn context
							}}
							onDuplicate={async () => {
								const res = await gt.duplicateCurrent();
								if (res.ok) {
									toast(
										"success",
										`Created rephrase ${res.created.id} and opened it.`,
									);
								} else {
									toast("error", res.error || "Duplicate failed");
								}
							}}
							onSkip={async () => {
								if (!gt.current) return;
								const r = await gt.save("skipped");
								if (!r.ok) return;
								const idx = gt.items.findIndex((i) => i.id === r.saved.id);
								const next =
									idx >= 0 && idx < gt.items.length - 1
										? gt.items[idx + 1]
										: gt.items[0];
								if (next) void gt.selectItem(next.id, { force: true });
							}}
							onDelete={() => toggleDeletedFlag(true)}
							onRestore={() => toggleDeletedFlag(false)}
						/>

						{/* Right: References (Tabbed) - Only show in single-turn mode */}
						{editorMode === "single" && (
							<div
								className={cn(
									"hidden lg:block col-span-1",
									sidebarOpen ? "lg:col-span-4" : "lg:col-span-5",
								)}
							>
								<ReferencesSection
									query={gt.query}
									setQuery={gt.setQuery}
									searching={gt.searching}
									searchResults={gt.searchResults}
									onRunSearch={gt.runSearch}
									onAddRefs={(refs) => {
										gt.addReferences(refs);
										toast("success", `Added ${refs.length} reference(s)`);
									}}
									references={gt.current?.references || []}
									onUpdateReference={(id, partial) =>
										gt.updateReference(id, partial)
									}
									onRemoveReference={(refId) =>
										gt.removeReferenceWithUndo(refId, (undo, timeoutMs) => {
											toast("info", "Reference removed.", {
												duration: timeoutMs,
												actionLabel: "Undo",
												onAction: undo,
											});
										})
									}
									onOpenReference={onOpenRef}
									isMultiTurn={
										!!(gt.current?.history && gt.current.history.length > 0)
									}
								/>
							</div>
						)}
					</div>
				)}
			</main>

			{/* Inspect Item Modal */}
			<InspectItemModal
				isOpen={!!inspectItem}
				item={inspectItem}
				onClose={() => setInspectItem(null)}
			/>

			{/* Tag Glossary Modal */}
			{glossaryOpen && (
				<TagGlossaryModal onClose={() => setGlossaryOpen(false)} />
			)}

			{/* Toasts */}
			<Toasts
				toasts={toasts}
				onActionClick={(id, action) => {
					action?.();
					dismiss(id);
				}}
			/>
		</div>
	);
}
