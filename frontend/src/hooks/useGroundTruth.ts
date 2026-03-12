import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiProvider } from "../adapters/apiProvider";
import { isDemoModeIgnored, shouldUseDemoProvider } from "../config/demo";
import type {
	ContextEntry,
	ConversationTurn,
	ExpectedTools,
	GroundTruthItem,
	Reference,
} from "../models/groundTruth";
import {
	getItemReferences,
	withUpdatedReferences,
} from "../models/groundTruth";
import { canApproveCandidate } from "../models/gtHelpers";
import type { Provider } from "../models/provider";

import { addTags } from "../services/tags";
import { logEvent } from "../services/telemetry";
import { invalidateGroundTruthCache } from "./useGroundTruthCache";
import { useReferencesEditor } from "./useReferencesEditor";
import { useReferencesSearch } from "./useReferencesSearch";

type SaveResult =
	| { ok: true; saved: GroundTruthItem; message?: string }
	| { ok: false; error: string };

type ExportResult = { ok: true; json: string } | { ok: false; error: string };

type UseGroundTruth = {
	// Provider (exposed for ExportModal convenience)
	provider: Provider | null;

	// Collection
	items: GroundTruthItem[];
	refreshList: () => Promise<void>;

	// Selection + current editable copy
	selectedId: string | null;
	setSelectedId: (id: string | null) => void;
	selectItem: (
		id: string | null,
		options?: { force?: boolean },
	) => Promise<boolean>;
	current: GroundTruthItem | null;

	// QA change tracking
	qaChanged: boolean;
	// Tags live on current item; expose updater
	updateTags: (tags: string[]) => void;

	// Comments
	updateComment: (v: string) => void;

	// Search (right panel)
	query: string;
	setQuery: (q: string) => void;
	searching: boolean;
	searchResults: Reference[];
	runSearch: () => Promise<void>;
	addReferences: (refs: Reference[]) => void;

	// Reference actions on current
	updateReference: (refId: string, patch: Partial<Reference>) => void;
	removeReferenceWithUndo: (
		refId: string,
		onUndoRegister: (undo: () => void, timeoutMs: number) => void,
	) => void;
	openReference: (ref: Reference) => void; // marks visited; UI decides how to open

	// Edit Q/A
	updateQuestion: (q: string) => void;
	updateAnswer: (a: string) => void;

	// Multi-turn support
	updateHistory: (history: ConversationTurn[]) => void;
	addTurn: (role: string, content: string) => void;
	deleteTurn: (messageIndex: number) => void;
	// Context entries
	updateContextEntries: (entries: ContextEntry[]) => void;

	// Expected tools
	updateExpectedTools: (tools: ExpectedTools) => void;

	// Save + status
	saving: boolean;
	save: (nextStatus?: GroundTruthItem["status"]) => Promise<SaveResult>;
	canApprove: boolean;
	toggleDeletedCurrent: (nextDeleted: boolean) => Promise<SaveResult>;
	toggleDeletedAny: (
		itemId: string,
		nextDeleted: boolean,
	) => Promise<SaveResult>;

	// Duplicate current as rephrase
	duplicateCurrent: () => Promise<
		{ ok: true; created: GroundTruthItem } | { ok: false; error: string }
	>;

	// Export
	exportJson: () => Promise<ExportResult>;

	// UI helpers
	hasUnsaved: boolean;
};

// Pure helper to compute a stable fingerprint for unsaved detection
function stateSignature(it: GroundTruthItem): string {
	const refs = [...getItemReferences(it)]
		.map((r) => ({
			id: r.id,
			title: r.title || "",
			url: r.url,
			snippet: r.snippet || "",
			// visitedAt is intentionally excluded from unsaved signature
			keyParagraph: (r.keyParagraph || "").trim(),
			bonus: !!r.bonus,
			messageIndex: r.messageIndex,
			toolCallId: r.toolCallId,
		}))
		.sort((a, b) => a.id.localeCompare(b.id));
	return JSON.stringify({
		id: it.id,
		providerId: it.providerId,
		question: (it.question || "").trim(),
		answer: (it.answer || "").trim(),
		comment: (it.comment ?? "").trim(),
		history: it.history || [],
		references: refs,
		manualTags: [...(it.manualTags || [])]
			.map((t) => t.trim())
			.filter(Boolean)
			.sort(),
		status: it.status,
		deleted: !!it.deleted,
	});
}

function useGroundTruth(): UseGroundTruth {
	const providerRef = useRef<Provider | null>(null);
	const [items, setItems] = useState<GroundTruthItem[]>([]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [current, setCurrent] = useState<GroundTruthItem | null>(null);

	// QA tracking
	const qaBaseline = useRef<{ q: string; a: string }>({ q: "", a: "" });
	// tags mutate current directly through updateTags

	// Search (delegated to sub-hook)
	const { query, setQuery, searching, searchResults, runSearch, clearResults } =
		useReferencesSearch({ getSeedQuery: () => current?.question });

	// Save idempotency
	const [lastSavedStateFp, setLastSavedStateFp] = useState<string>("");
	const [saving, setSaving] = useState(false);

	// References editor (delegated to sub-hook)
	const {
		updateReference,
		addReferences,
		removeReferenceWithUndo,
		openReference,
	} = useReferencesEditor({ setCurrent });

	// init
	useEffect(() => {
		let cancelled = false;

		(async () => {
			if (isDemoModeIgnored()) {
				try {
					logEvent("demo_mode_ignored_non_dev_build", {
						reason: "DEMO_MODE is only supported in dev builds",
					});
				} catch {}
			}

			let p: Provider;
			if (shouldUseDemoProvider()) {
				const { createDemoProvider } = await import("../models/demoData");
				p = createDemoProvider();
			} else {
				p = new ApiProvider();
			}

			if (cancelled) return;
			providerRef.current = p;

			try {
				const { items } = await p.list();
				if (cancelled) return;

				setItems(items);
				const first = items[0];
				setSelectedId(first?.id ?? null);
				if (first) {
					// Prime the editor immediately so fields populate without waiting for a follow-up get()
					const clone = JSON.parse(JSON.stringify(first)) as GroundTruthItem;
					setCurrent(clone);
					qaBaseline.current = { q: first.question, a: first.answer };
					setLastSavedStateFp(stateSignature(first));
				}
			} catch {
				// Load errors are handled elsewhere via explicit actions.
			}
		})();

		return () => {
			cancelled = true;
		};
	}, []);

	// Internal ref to track if selection change is already in progress
	const selectionChangeInProgress = useRef(false);
	// Internal ref to track ongoing agent generation
	const abortGenerationRef = useRef<(() => void) | null>(null);

	// load selected - now acts as a sync mechanism for setSelectedId
	useEffect(() => {
		const p = providerRef.current;
		if (!p || !selectedId || selectionChangeInProgress.current) return;
		// If we already have the current item matching the selection (primed from list), skip fetch
		if (current?.id === selectedId) return;

		// Selection changed externally (e.g., from initialization), load without warning
		(async () => {
			const it = await p.get(selectedId);
			if (!it) return;
			const clone = JSON.parse(JSON.stringify(it)) as GroundTruthItem;
			setCurrent(clone);
			qaBaseline.current = { q: it.question, a: it.answer };
			clearResults();
			setLastSavedStateFp(stateSignature(it));
		})();
	}, [selectedId, clearResults, current?.id]);

	const qaChanged = useMemo(() => {
		if (!current) return false;
		return (
			current.question !== qaBaseline.current.q ||
			current.answer !== qaBaseline.current.a
		);
	}, [current]);

	// reference actions come from useReferencesEditor

	const refreshList = useCallback(async () => {
		const p = providerRef.current;
		if (!p) return;
		const res = await p.list();
		setItems(res.items);
	}, []);

	const updateQuestion = useCallback((q: string) => {
		setCurrent((prev) => (prev ? { ...prev, question: q } : prev));
	}, []);
	const updateAnswer = useCallback((a: string) => {
		setCurrent((prev) => (prev ? { ...prev, answer: a } : prev));
	}, []);
	const updateComment = useCallback((v: string) => {
		setCurrent((prev) => (prev ? { ...prev, comment: v } : prev));
	}, []);

	const canApprove = useMemo(() => canApproveCandidate(current), [current]);

	const save = useCallback(
		async (nextStatus?: GroundTruthItem["status"]): Promise<SaveResult> => {
			const p = providerRef.current;
			if (!current || !p || saving) return { ok: false, error: "Not ready" };

			const candidate: GroundTruthItem = {
				...current,
				status: nextStatus || current.status,
			};
			const stateFp = stateSignature(candidate);
			if (stateFp === lastSavedStateFp) {
				return { ok: true, saved: current, message: "No changes" };
			}

			if (
				["approved"].includes(candidate.status) &&
				!canApproveCandidate(candidate)
			) {
				return { ok: false, error: "References not complete for approval" };
			}
			// No gating by change category anymore

			setSaving(true);
			const started = Date.now();
			try {
				const prevBeforeSave = current; // capture to merge transient fields
				const saved = await p.save(candidate);
				// SA-232: Backend does not persist visitedAt; reattach any prior visitedAt values by URL.
				const prevRefs = getItemReferences(prevBeforeSave);
				const savedRefs = getItemReferences(saved);
				if (prevRefs.length && savedRefs.length) {
					const visitedByUrl = new Map(
						prevRefs
							.filter((r) => r.visitedAt)
							.map((r) => [r.url, r.visitedAt as string]),
					);
					let changed = false;
					const merged = savedRefs.map((r) => {
						if (!r.visitedAt) {
							const v = visitedByUrl.get(r.url);
							if (v) {
								changed = true;
								return { ...r, visitedAt: v };
							}
						}
						return r;
					});
					if (changed) {
						// Re-write saved item with visitedAt merged
						Object.assign(saved, withUpdatedReferences(saved, merged));
					}
				}
				setItems((arr) => arr.map((i) => (i.id === saved.id ? saved : i)));
				setCurrent(saved);
				setLastSavedStateFp(stateSignature(saved));
				if (qaChanged)
					qaBaseline.current = { q: saved.question, a: saved.answer };

				// FR-002: Invalidate cache after successful save to ensure fresh data on next inspection
				if (saved.datasetName && saved.bucket && saved.id) {
					invalidateGroundTruthCache(saved.datasetName, saved.bucket, saved.id);
				}

				// Persist any new manual tags only after a successful save; fire-and-forget
				try {
					const tags = Array.from(
						new Set(
							(saved.manualTags || [])
								.map((t) => (t || "").trim())
								.filter(Boolean),
						),
					);
					if (tags.length) void addTags(tags).catch(() => {});
				} catch {}
				try {
					const baseProps = {
						providerId: saved.providerId,
						itemId: saved.id,
						status: saved.status,
						selectedRefCount: getItemReferences(saved).length,
						durationMs: Date.now() - started,
					};
					if (nextStatus === "approved" || saved.status === "approved")
						logEvent("gtc.approve", baseProps);
					else logEvent("gtc.save_draft", baseProps);
				} catch {}
				return { ok: true, saved };
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return { ok: false, error: msg };
			} finally {
				setSaving(false);
			}
		},
		[current, saving, lastSavedStateFp, qaChanged],
	);

	// Determine if current item differs from last saved state
	const hasUnsaved = useMemo(() => {
		if (!current) return false;
		return stateSignature(current) !== lastSavedStateFp;
	}, [current, lastSavedStateFp]);

	// Controlled selection with unsaved changes warning
	const selectItem = useCallback(
		async (
			id: string | null,
			options?: { force?: boolean },
		): Promise<boolean> => {
			const p = providerRef.current;
			if (!p || !id) {
				setSelectedId(id);
				return true;
			}

			// If already selected, do nothing
			if (current?.id === id) return true;

			// Check for unsaved changes
			if (!options?.force && current && hasUnsaved) {
				const confirmed = window.confirm(
					"You have unsaved changes. Switching items will discard them. Continue?",
				);
				if (!confirmed) return false;
			}

			// Abort any ongoing agent generation
			if (abortGenerationRef.current) {
				abortGenerationRef.current();
				abortGenerationRef.current = null;
			}

			// Mark selection change in progress to prevent side effects
			selectionChangeInProgress.current = true;

			try {
				// Fetch the item from backend
				const it = await p.get(id);
				if (!it) {
					selectionChangeInProgress.current = false;
					return false;
				}

				const clone = JSON.parse(JSON.stringify(it)) as GroundTruthItem;
				setCurrent(clone);
				qaBaseline.current = { q: it.question, a: it.answer };
				clearResults();
				setLastSavedStateFp(stateSignature(it));
				setSelectedId(id);
				return true;
			} catch (error) {
				console.error("Failed to load item:", error);
				return false;
			} finally {
				selectionChangeInProgress.current = false;
			}
		},
		[current, hasUnsaved, clearResults],
	);

	const exportJson = useCallback(async (): Promise<ExportResult> => {
		const p = providerRef.current;
		if (!p) return { ok: false, error: "No provider" };
		try {
			try {
				logEvent("gtc.export_snapshot_start");
			} catch {}
			const json = await p.export();
			try {
				logEvent("gtc.export_snapshot_complete", { bytes: json.length });
			} catch {}
			return { ok: true, json };
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			try {
				logEvent("gtc.export_snapshot_error", { error: msg });
			} catch {}
			return { ok: false, error: msg };
		}
	}, []);

	const toggleDeletedCurrent = useCallback(
		async (nextDeleted: boolean): Promise<SaveResult> => {
			const p = providerRef.current;
			if (!current || !p) return { ok: false, error: "No current" };
			try {
				const saved = await p.save({ ...current, deleted: nextDeleted });
				setItems((arr) => arr.map((i) => (i.id === saved.id ? saved : i)));
				setCurrent(saved);
				setLastSavedStateFp(stateSignature(saved));
				try {
					logEvent(nextDeleted ? "gtc.soft_delete" : "gtc.restore", {
						providerId: saved.providerId,
						itemId: saved.id,
						status: saved.status,
					});
				} catch {}
				return { ok: true, saved };
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return { ok: false, error: msg };
			}
		},
		[current],
	);

	const toggleDeletedAny = useCallback(
		async (itemId: string, nextDeleted: boolean): Promise<SaveResult> => {
			const p = providerRef.current;
			if (!p) return { ok: false, error: "No provider" };
			const it = items.find((i) => i.id === itemId);
			if (!it) return { ok: false, error: "Item not found" };
			try {
				const saved = await p.save({ ...it, deleted: nextDeleted });
				setItems((arr) => arr.map((i) => (i.id === saved.id ? saved : i)));
				if (current && current.id === saved.id) {
					setCurrent(saved);
					setLastSavedStateFp(stateSignature(saved));
				}
				try {
					logEvent(nextDeleted ? "gtc.soft_delete" : "gtc.restore", {
						providerId: saved.providerId,
						itemId: saved.id,
						status: saved.status,
					});
				} catch {}
				return { ok: true, saved };
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return { ok: false, error: msg };
			}
		},
		[items, current],
	);

	const updateTags = useCallback((manualTags: string[]) => {
		setCurrent((prev) => (prev ? { ...prev, manualTags } : prev));
	}, []);

	const updateHistory = useCallback((history: ConversationTurn[]) => {
		setCurrent((prev) => {
			if (!prev) return prev;

			// Find last user and last non-user (agent) turn in single reverse iteration
			let lastUser: ConversationTurn | undefined;
			let lastAgent: ConversationTurn | undefined;

			for (let i = history.length - 1; i >= 0; i--) {
				const turn = history[i];
				if (turn.role === "user" && !lastUser) {
					lastUser = turn;
				} else if (turn.role !== "user" && !lastAgent) {
					lastAgent = turn;
				}

				// Early exit if both found
				if (lastUser && lastAgent) break;
			}

			return {
				...prev,
				history,
				question: lastUser?.content || prev.question,
				answer: lastAgent?.content || prev.answer,
			};
		});
	}, []);

	const addTurn = useCallback((role: string, content: string) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			const newHistory: ConversationTurn[] = [
				...(prev.history || []),
				{ role, content },
			];
			// Sync to question/answer
			const lastUser = [...newHistory].reverse().find((t) => t.role === "user");
			const lastAgent = [...newHistory]
				.reverse()
				.find((t) => t.role !== "user");
			return {
				...prev,
				history: newHistory,
				question: lastUser?.content || prev.question,
				answer: lastAgent?.content || prev.answer,
			};
		});
	}, []);

	const deleteTurn = useCallback((messageIndex: number) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			const history = prev.history || [];
			if (messageIndex < 0 || messageIndex >= history.length) return prev;

			// Remove the turn at the specified index
			const newHistory = history.filter((_, i) => i !== messageIndex);

			// Re-index references: shift down any references with messageIndex > deleted index
			const currentRefs = getItemReferences(prev);
			const updatedReferences = currentRefs
				.map((ref) => {
					if (typeof ref.messageIndex !== "number") return ref;

					// Remove references for the deleted turn
					if (ref.messageIndex === messageIndex) {
						return null;
					}

					// Shift down references after the deleted turn
					if (ref.messageIndex > messageIndex) {
						return { ...ref, messageIndex: ref.messageIndex - 1 };
					}

					return ref;
				})
				.filter((ref): ref is Reference => ref !== null);

			// Sync last user/non-user turns to question/answer for backward compatibility
			const lastUser = [...newHistory].reverse().find((t) => t.role === "user");
			const lastAgent = [...newHistory]
				.reverse()
				.find((t) => t.role !== "user");

			return withUpdatedReferences(
				{
					...prev,
					history: newHistory,
					question: lastUser?.content || "",
					answer: lastAgent?.content || "",
				},
				updatedReferences,
			);
		});
	}, []);

	const updateContextEntries = useCallback((entries: ContextEntry[]) => {
		setCurrent((prev) => (prev ? { ...prev, contextEntries: entries } : prev));
	}, []);

	const updateExpectedTools = useCallback((tools: ExpectedTools) => {
		setCurrent((prev) => (prev ? { ...prev, expectedTools: tools } : prev));
	}, []);

	const duplicateCurrent = useCallback(async () => {
		const p = providerRef.current;
		if (!current || !p) return { ok: false as const, error: "No current" };
		try {
			const created = await p.duplicate(current);
			// Insert at top of list and select it
			setItems((arr) => [created, ...arr]);
			setSelectedId(created.id);
			setCurrent(JSON.parse(JSON.stringify(created)) as GroundTruthItem);
			qaBaseline.current = { q: created.question, a: created.answer };
			setLastSavedStateFp(stateSignature(created));
			try {
				logEvent("gtc.duplicate_rephrase", {
					originalId: current.id,
					createdId: created.id,
				});
			} catch {}
			return { ok: true as const, created };
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			return { ok: false as const, error: msg };
		}
	}, [current]);

	return {
		provider: providerRef.current,
		items,
		refreshList,
		selectedId,
		setSelectedId,
		selectItem,
		current,
		qaChanged,
		updateTags,
		updateComment,
		query,
		setQuery,
		searching,
		searchResults,
		runSearch,
		addReferences,
		updateReference,
		removeReferenceWithUndo,
		openReference,
		updateQuestion,
		updateAnswer,
		updateHistory,
		addTurn,
		deleteTurn,
		updateContextEntries,
		updateExpectedTools,
		saving,
		save,
		canApprove,
		toggleDeletedCurrent,
		toggleDeletedAny,
		exportJson,
		duplicateCurrent,
		hasUnsaved,
	};
}

export default useGroundTruth;
