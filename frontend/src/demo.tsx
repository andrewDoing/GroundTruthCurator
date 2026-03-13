import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import AppHeader from "./components/app/AppHeader";
import InstructionsPane from "./components/app/InstructionsPane";
import EvidenceDrawer from "./components/app/layout/EvidenceDrawer";
import SplitPaneLayout from "./components/app/layout/SplitPaneLayout";
import CuratePane from "./components/app/pages/CuratePane";
import ReferencesSection from "./components/app/pages/ReferencesSection";
import type { QuestionsExplorerItem } from "./components/app/QuestionsExplorer";
import QueueSidebar from "./components/app/QueueSidebar";
import Toasts from "./components/common/Toasts";
import DEMO_MODE from "./config/demo";
import { runSelfTests } from "./dev/self-tests";
import useGlobalHotkeys from "./hooks/useGlobalHotkeys";
import useGroundTruth from "./hooks/useGroundTruth";
import { invalidateGroundTruthCache } from "./hooks/useGroundTruthCache";
import { useToasts } from "./hooks/useToasts";
import type { Reference } from "./models/groundTruth";
import { getItemReferences } from "./models/groundTruth";
import { normalizeUrl } from "./models/utils";
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

const DESKTOP_CURATE_QUERY = "(min-width: 1024px)";

const StatsPage = lazy(() => import("./components/app/pages/StatsPage"));
const QuestionsExplorer = lazy(
	() => import("./components/app/QuestionsExplorer"),
);
const InspectItemModal = lazy(
	() => import("./components/modals/InspectItemModal"),
);
const TagGlossaryModal = lazy(
	() => import("./components/modals/TagGlossaryModal"),
);

function PageFallback({ label }: { label: string }) {
	return (
		<section className="flex flex-1 items-center justify-center rounded-2xl border bg-white p-4 text-sm text-slate-600 shadow-sm min-h-0 min-w-0">
			{label}
		</section>
	);
}

function PanelFallback({ label }: { label: string }) {
	return (
		<div className="flex flex-1 items-center justify-center rounded-2xl border bg-white p-4 text-sm text-slate-600 shadow-sm min-h-0 min-w-0">
			{label}
		</div>
	);
}

function ModalFallback({ label }: { label: string }) {
	return (
		<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
			<div className="w-full max-w-md rounded-2xl border bg-white p-6 text-sm text-slate-600 shadow-xl">
				{label}
			</div>
		</div>
	);
}

function getMediaQueryMatch(query: string) {
	if (typeof window === "undefined") {
		return false;
	}

	return window.matchMedia(query).matches;
}

function useMediaQuery(query: string) {
	const [matches, setMatches] = useState(() => getMediaQueryMatch(query));

	useEffect(() => {
		if (typeof window === "undefined") {
			return;
		}

		const mediaQueryList = window.matchMedia(query);
		const handleChange = () => {
			setMatches(mediaQueryList.matches);
		};

		handleChange();
		mediaQueryList.addEventListener("change", handleChange);

		return () => {
			mediaQueryList.removeEventListener("change", handleChange);
		};
	}, [query]);

	return matches;
}

export function invalidateInspectCacheForExplorerItem(
	item: Pick<QuestionsExplorerItem, "datasetName" | "bucket" | "id">,
) {
	if (item.datasetName && item.bucket && item.id) {
		invalidateGroundTruthCache(item.datasetName, item.bucket, item.id);
	}
}

export async function resolveExplorerAssignSelection(
	itemId: string,
	selectItem: (itemId: string) => Promise<boolean>,
) {
	const selected = await selectItem(itemId);
	if (!selected) {
		return {
			switchToCurate: false,
			toastKind: "info" as const,
			toastMessage: `Assigned ${itemId}, but opening it in curate was cancelled or failed.`,
		};
	}

	return {
		switchToCurate: true,
		toastKind: "success" as const,
		toastMessage: `Assigned ${itemId} for curation`,
	};
}

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
	const [drawerOpen, setDrawerOpen] = useState(false);
	const closeDrawer = useCallback(() => setDrawerOpen(false), []);
	const isDesktop = useMediaQuery(DESKTOP_CURATE_QUERY);

	// Feature hook
	const gt = useGroundTruth();

	// Warm the runtime-config store on app startup. The service load is cached and
	// idempotent, so this stays safe under StrictMode re-renders.
	useEffect(() => {
		void getRuntimeConfig().catch((err) => {
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

	useEffect(() => {
		if (isDesktop) {
			closeDrawer();
		}
	}, [isDesktop, closeDrawer]);

	const isMultiTurn = Boolean(gt.current?.history?.length);
	const references = gt.current ? getItemReferences(gt.current) : [];

	async function onDuplicate() {
		const res = await gt.duplicateCurrent();
		if (res.ok) {
			toast("success", `Created rephrase ${res.created.id} and opened it.`);
		} else {
			toast("error", res.error || "Duplicate failed");
		}
	}

	async function onSkip() {
		if (!gt.current) return;
		const res = await gt.save("skipped");
		if (!res.ok) return;

		const index = gt.items.findIndex((item) => item.id === res.saved.id);
		const nextItem =
			index >= 0 && index < gt.items.length - 1
				? gt.items[index + 1]
				: gt.items[0];
		if (nextItem) {
			void gt.selectItem(nextItem.id, { force: true });
		}
	}

	function onAddRefs(refs: Reference[]) {
		gt.addReferences(refs);
		toast("success", `Added ${refs.length} reference(s)`);
	}

	function onRemoveReference(refId: string) {
		gt.removeReferenceWithUndo(refId, (undo, timeoutMs) => {
			toast("info", "Reference removed.", {
				duration: timeoutMs,
				actionLabel: "Undo",
				onAction: undo,
			});
		});
	}

	const curatePane = (
		<CuratePane
			className={isDesktop ? "h-full overflow-y-auto" : "min-h-0"}
			current={gt.current}
			canApprove={gt.canApprove}
			saving={gt.saving}
			onUpdateComment={(v) => gt.updateComment(v)}
			onUpdateTags={(tags) => gt.updateTags(tags)}
			onUpdateHistory={(history) => gt.updateHistory(history)}
			onDeleteTurn={(messageIndex) => gt.deleteTurn(messageIndex)}
			onSaveDraft={() => onSave("draft")}
			onApprove={() => onSave("approved")}
			onDuplicate={onDuplicate}
			onSkip={onSkip}
			onDelete={() => toggleDeletedFlag(true)}
			onRestore={() => toggleDeletedFlag(false)}
		/>
	);

	const referencesPane = (
		<ReferencesSection
			item={gt.current}
			query={gt.query}
			setQuery={gt.setQuery}
			searching={gt.searching}
			searchResults={gt.searchResults}
			onRunSearch={gt.runSearch}
			onAddRefs={onAddRefs}
			references={references}
			onUpdateReference={(id, partial) => gt.updateReference(id, partial)}
			onRemoveReference={onRemoveReference}
			onOpenReference={onOpenRef}
			isMultiTurn={isMultiTurn}
			onUpdateContextEntries={gt.updateContextEntries}
			onUpdateExpectedTools={gt.updateExpectedTools}
		/>
	);

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
					<Suspense fallback={<PageFallback label="Loading stats…" />}>
						<StatsPage
							demoMode={DEMO_MODE}
							items={gt.items}
							onBack={() => setViewMode("curate")}
						/>
					</Suspense>
				)}

				{viewMode === "questions" && (
					<section className="flex flex-1 flex-col rounded-2xl border bg-white p-4 shadow-sm min-h-0 min-w-0">
						<InstructionsPane
							className="mb-4 flex-none"
							title="Questions Review Instructions"
							markdown={`\n### Reviewing Questions\n\n- Scan for duplicates, out-of-scope, or low-quality questions.\n- Use Delete to soft-delete; you can restore later.\n- Open an item to curate details.\n`}
						/>
						<div className="flex flex-1 min-h-0 min-w-0">
							<Suspense fallback={<PanelFallback label="Loading questions…" />}>
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

											const selectionResult =
												await resolveExplorerAssignSelection(
													item.id,
													(selectedItemId) => gt.selectItem(selectedItemId),
												);
											if (selectionResult.switchToCurate) {
												setViewMode("curate");
											}
											toast(
												selectionResult.toastKind,
												selectionResult.toastMessage,
											);
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
											const isDeleted =
												item.deleted || item.status === "deleted";

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
												toast(
													"success",
													`Restored ${item.id} to draft status.`,
												);
											} else {
												// Delete: use DELETE endpoint directly
												await deleteGroundTruth(
													item.datasetName,
													item.bucket,
													item.id,
												);
												toast("info", `Marked ${item.id} as deleted.`);
											}
											invalidateInspectCacheForExplorerItem(item);
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
							</Suspense>
						</div>
					</section>
				)}

				{viewMode === "curate" && (
					<div className="flex flex-1 gap-4 min-h-0">
						{/* Left: Queue */}
						{sidebarOpen && (
							<QueueSidebar
								className="hidden md:block flex-none w-64 lg:w-72"
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

						{/* Center + Right: split-pane on desktop, editor + drawer on mobile */}
						<div className="flex-1 min-w-0 min-h-0">
							{isDesktop ? (
								<SplitPaneLayout
									className="h-full w-full"
									left={curatePane}
									right={
										<div className="h-full overflow-y-auto">
											{referencesPane}
										</div>
									}
								/>
							) : (
								<>
									<div className="mb-2 flex justify-end">
										<button
											type="button"
											onClick={() => setDrawerOpen(true)}
											className="inline-flex items-center gap-1.5 rounded-xl border bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-violet-50 hover:text-violet-700 shadow-sm"
										>
											📋 Evidence
										</button>
									</div>
									<div className="min-h-0">{curatePane}</div>
									<EvidenceDrawer open={drawerOpen} onClose={closeDrawer}>
										{referencesPane}
									</EvidenceDrawer>
								</>
							)}
						</div>
					</div>
				)}
			</main>

			{/* Inspect Item Modal */}
			{inspectItem && (
				<Suspense fallback={<ModalFallback label="Loading item inspector…" />}>
					<InspectItemModal
						isOpen={true}
						item={inspectItem}
						onClose={() => setInspectItem(null)}
					/>
				</Suspense>
			)}

			{/* Tag Glossary Modal */}
			{glossaryOpen && (
				<Suspense fallback={<ModalFallback label="Loading tag glossary…" />}>
					<TagGlossaryModal onClose={() => setGlossaryOpen(false)} />
				</Suspense>
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
